from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.adapters.pretrained import model_status, predict_risk
from app.alerts.service import counts_by_level
from app.charts import build_chart, turno_dashboard
from app.config import settings
from app.data.loader import variable_catalog
from app.llm.orchestrator import handle_chat
from app.state import state

app = FastAPI(title="RISA Signal API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ReviewRequest(BaseModel):
    status: str = Field(pattern="^(abierta|revisada|confirmada|descartada)$")


class ChartRequest(BaseModel):
    patient_id: str | None = None
    variables: list[str] = ["heart_rate"]
    kind: str = "line"
    title: str | None = None


class PredictRequest(BaseModel):
    patient_id: str


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "dataset": state.dataset.origin,
        "patients": int(len(state.dataset.patients)),
        "alerts": len(state.alerts),
        "llm": "openai" if settings.openai_api_key else "mock",
        "model": settings.llm_model if settings.openai_api_key else "mock",
        "pretrained": model_status(),
    }


@app.get("/api/patients")
def patients() -> dict[str, Any]:
    return {"origin": state.dataset.origin, "items": state.dataset.patients.to_dict(orient="records")}


@app.get("/api/variables")
def variables() -> dict[str, Any]:
    return {"items": variable_catalog()}


@app.get("/api/pipeline/report")
def pipeline_report() -> dict[str, Any]:
    """Comprensión de datos + comparación de modelos (fases 2 y 5 del pipeline CRISP-DM).

    `evaluation` trae, por candidato, matriz de confusión + precisión/recall/
    F1/ROC-AUC en validación cruzada (`cv`) y en el test final nunca usado
    para elegir el modelo, más `chosen_model` y la regla de selección
    (`pipeline/evaluacion.py`, `ADR-0009`).
    """
    return {
        "origin": state.dataset.origin,
        "model_version": state.dataset.model_version,
        "data_quality": state.dataset.quality_report,
        "evaluation": state.dataset.evaluation,
    }


@app.get("/api/alerts")
def alerts(level: str | None = None) -> dict[str, Any]:
    items = state.alerts if not level else [a for a in state.alerts if a["level"] == level]
    return {"items": items, "counts": counts_by_level(state.alerts), "origin": state.dataset.origin}


@app.get("/api/alerts/{alert_id}")
def alert_detail(alert_id: str) -> dict[str, Any]:
    found = state.alert_by_id(alert_id)
    if not found:
        raise HTTPException(404, "alerta no encontrada")
    return found


@app.post("/api/alerts/{alert_id}/review")
def review_alert(alert_id: str, body: ReviewRequest) -> dict[str, Any]:
    found = state.alert_by_id(alert_id)
    if not found:
        raise HTTPException(404, "alerta no encontrada")
    found["review_status"] = body.status
    state.rebuild_rag()
    return found


@app.get("/api/rag/search")
def rag_search(q: str, k: int = 4) -> dict[str, Any]:
    return {"query": q, "hits": state.rag.search(q, k=k)}


@app.get("/api/model/status")
def pretrained_status() -> dict[str, Any]:
    return model_status()


@app.post("/api/model/predict")
async def pretrained_predict(body: PredictRequest) -> dict[str, Any]:
    alert = next((a for a in state.alerts if a["patient_id"] == body.patient_id), None)
    if not alert:
        raise HTTPException(404, "paciente sin features")
    return await predict_risk(body.patient_id, alert["features"])


@app.post("/api/charts")
def charts(body: ChartRequest) -> dict[str, Any]:
    return build_chart(state.dataset, body.kind, body.patient_id, body.variables, body.title)


@app.get("/api/dashboards/turno")
def dashboard_turno() -> dict[str, Any]:
    return turno_dashboard(state)


@app.post("/api/chat")
async def chat(body: ChatRequest) -> dict[str, Any]:
    payload = [m.model_dump() for m in body.messages]
    result = await handle_chat(payload, state)
    return {"message": result}
