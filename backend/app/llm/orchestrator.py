from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from app.charts import turno_risa_ui
from app.config import settings
from app.llm.prompts import SYSTEM_PROMPT
from app.llm.tools import TOOLS, run_tool

if TYPE_CHECKING:
    from app.state import AppState

_PID = re.compile(r"PAT-[\dA-Z]{2,8}", re.I)


def _patient_in(text: str, default: str | None = None) -> str | None:
    found = _PID.search(text)
    return found.group(0).upper() if found else default


def _collect(result: Any, bag: dict[str, Any]) -> None:
    if not isinstance(result, dict):
        return
    if "risa_ui" in result:
        bag["risa_ui"] = result["risa_ui"]
    if "chart" in result:
        bag["charts"].append(result["chart"])
    if isinstance(result, list) and result and isinstance(result[0], dict) and "source_id" in result[0]:
        bag["citations"].extend(result)
    if isinstance(result, dict) and result.get("kind") in {"alert", "rule", "variable", "patient"}:
        bag["citations"].append(result)


async def handle_chat(messages: list[dict[str, str]], app: AppState) -> dict[str, Any]:
    last = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    bag: dict[str, Any] = {
        "risa_ui": None,
        "charts": [],
        "citations": [],
        "tool_trace": [],
        "degraded": False,
        "model": None,
    }

    if settings.openai_api_key:
        try:
            text = await _openai_loop(messages, app, bag)
            bag["model"] = settings.llm_model
            if bag["citations"] == [] and last:
                bag["citations"] = app.rag.search(last, k=3)
            return {"content": text, **bag}
        except Exception as exc:  # noqa: BLE001
            bag["tool_trace"].append({"tool": "llm", "ok": False, "detail": str(exc)})

    bag["degraded"] = True
    bag["model"] = "mock"
    text = await _mock_loop(last, app, bag)
    if not bag["citations"]:
        bag["citations"] = app.rag.search(last or "alertas prioridad", k=3)
    return {"content": text, **bag}


async def _openai_loop(messages: list[dict[str, str]], app: AppState, bag: dict[str, Any]) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    oai_messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in messages[-12:]:
        oai_messages.append({"role": m["role"], "content": m["content"]})

    last_text = ""
    for _ in range(4):
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=oai_messages,
            tools=TOOLS,
            temperature=0.2,
        )
        choice = response.choices[0].message
        last_text = choice.content or last_text
        if not choice.tool_calls:
            return last_text or "No pude completar la respuesta."
        oai_messages.append(
            {
                "role": "assistant",
                "content": choice.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in choice.tool_calls
                ],
            }
        )
        for tc in choice.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            result = await run_tool(tc.function.name, args, app)
            _collect(result, bag)
            if tc.function.name == "retrieve_evidence" and isinstance(result, list):
                bag["citations"].extend(result)
            bag["tool_trace"].append({"tool": tc.function.name, "ok": True, "args": args})
            oai_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str)[:8000],
                }
            )
    return last_text or "Listo. Revisá el panel: usé las herramientas sobre el dataset."


def _mock_dashboard_args(text: str, patient_id: str) -> dict[str, Any]:
    levels = []
    for keywords, value in (
        (("crític", "critic"), "CRITICO"),
        (("alt",), "ALTO"),
        (("medi",), "MEDIO"),
        (("baj",), "BAJO"),
        (("descart",), "DESCARTADO"),
    ):
        if any(keyword in text for keyword in keywords):
            levels.append(value)
    patient_requested = bool(_PID.search(text))
    if not levels and not patient_requested and not any(key in text for key in ("spo2", "laboratorio", "lab_", "resp")):
        return {"use_turno_template": True}

    widgets: list[dict[str, Any]] = []
    for level in levels:
        widgets.extend(
            [
                {
                    "type": "kpi",
                    "id": f"{level.lower()}-count",
                    "title": f"Alertas {level}",
                    "metric": "alert_count",
                    "filters": {"level": level},
                },
                {
                    "type": "alert_list",
                    "id": f"{level.lower()}-alerts",
                    "title": f"Cola {level}",
                    "level": level,
                    "limit": 10,
                    "on_select": {"action": "select_alert"},
                },
            ]
        )
    variables = ["heart_rate"]
    if "spo2" in text or "satur" in text:
        variables.append("spo2")
    if "resp" in text:
        variables.append("resp_rate")
    if "laboratorio" in text or "lab_" in text:
        variables = ["LAB_A", "LAB_B", "LAB_C", "LAB_D"]
    if patient_requested or len(variables) > 1 or variables[0].startswith("LAB_"):
        widgets.extend(
            [
                {
                    "type": "chart",
                    "id": "patient-series",
                    "title": f"Series de {patient_id}",
                    "chart": {"patient_id": patient_id, "variables": variables[:4], "kind": "line"},
                },
                {
                    "type": "evidence",
                    "id": "patient-evidence",
                    "title": f"Evidencia de {patient_id}",
                    "patient_id": patient_id,
                },
            ]
        )
    if not widgets:
        return {"use_turno_template": True}
    widgets.append(
        {
            "type": "markdown",
            "id": "scope-note",
            "title": "Alcance",
            "text": "Dashboard hidratado por el backend con RISA Data V1.0; apoyo a revisión, no diagnóstico.",
        }
    )
    return {
        "title": "Dashboard solicitado — RISA Signal",
        "subtitle": "Composición dinámica en modo MockLLM",
        "widgets": widgets[:6],
    }


async def _mock_loop(text: str, app: AppState, bag: dict[str, Any]) -> str:
    low = (text or "").lower()
    default_pid = app.dataset.patients["patient_id"].iloc[0] if len(app.dataset.patients) else "PAT-0001"
    pid = _patient_in(text, default_pid)
    planned: list[tuple[str, dict]] = []

    if any(k in low for k in ("dashboard", "tablero", "risa ui", "panel")):
        planned.append(("get_dashboard_context", {}))
        planned.append(("emit_risa_ui", _mock_dashboard_args(low, pid)))
    if any(k in low for k in ("gráf", "graf", "chart", "plot", "serie", "fc", "spo2", "lab_a", "lab_b", "lab_c", "lab_d", "laboratorio")):
        variables = ["heart_rate"]
        if "spo2" in low or "sat" in low:
            variables.append("spo2")
        if "lab" in low or "laboratorio" in low:
            variables = ["LAB_A", "LAB_B", "LAB_C", "LAB_D"]
        if "fr" in low or "resp" in low:
            variables.append("resp_rate")
        planned.append(("emit_chart", {"patient_id": pid, "variables": variables, "kind": "line"}))
    if any(k in low for k in ("modelo", "preentren", "predict", "isolation")):
        planned.append(("call_pretrained_model", {"patient_id": pid}))
    if any(k in low for k in ("alerta", "riesgo", "prioridad", "ranking", "quién", "quien", "revisar")):
        planned.append(("list_alerts", {}))
    planned.append(("retrieve_evidence", {"query": text or "prioridad alertas", "k": 4}))

    snippets = []
    for name, args in planned:
        result = await run_tool(name, args, app)
        _collect(result, bag)
        if name == "retrieve_evidence" and isinstance(result, list):
            bag["citations"].extend(result)
        bag["tool_trace"].append({"tool": name, "ok": True, "args": args})
        snippets.append(f"- `{name}`")

    if bag["risa_ui"] is None and any(k in low for k in ("dashboard", "tablero")):
        bag["risa_ui"] = turno_risa_ui(app)

    top = [a for a in app.alerts if a["level"] in {"CRITICO", "ALTO"}]
    discarded = [a for a in app.alerts if a["level"] == "DESCARTADO"]
    lines = [
        f"Modo degradado (MockLLM): no hay `OPENAI_API_KEY`, pero las herramientas corrieron sobre {app.dataset.origin}.",
        "",
        "**Esto no es un diagnóstico.** Es prioridad de revisión con evidencia.",
        "",
        "Casos a revisar primero: " + (", ".join(f"{a['patient_id']} ({a['level']}, {a['pattern']})" for a in top[:3]) or "ninguno en ALTO/CRITICO en esta ventana"),
        f"Descartados con motivo (de {len(discarded)} totales, visibles): " + ", ".join(f"{a['patient_id']} ({a['pattern']})" for a in discarded[:3]),
        "",
        "Herramientas usadas:\n" + "\n".join(snippets),
        "",
        f"Pedí un *dashboard del turno*, un *gráfico de FC de {pid}* o *por qué {pid} está en {top[0]['level'] if top else 'BAJO'}* para ver RISA UI, Plotly y citas RAG.",
    ]
    return "\n".join(lines)
