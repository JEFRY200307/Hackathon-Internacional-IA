"""CRISP-DM · Fase 6 — Despliegue.

Orquesta las fases 2-5 (comprensión de datos, preparación, Anomaly/Pattern/
Context Engine, evaluación) en un único `PipelineResult` listo para servir:
es el único punto que el backend importa (`from pipeline.despliegue import
...`) para exponer todo por API REST, y el mismo objeto alimenta la
exportación oficial `results/signals.csv` + `results/evidence.csv`.

Persiste las capas RAW → CLEAN → FEATURES → MODEL → RESULTS que pide el
Documento Técnico Maestro V2 (sección 12) bajo `pipeline/data/` — `RAW` es
inmutable (`pipeline/data/raw/`, nunca se escribe aquí); todo lo demás es
derivado y regenerable.
"""

from __future__ import annotations

import csv
import pickle
from dataclasses import dataclass
from datetime import timedelta

import pandas as pd

from pipeline import evaluacion, motor_contexto, motor_prioridad, motor_riesgo
from pipeline.comprension_datos import RawSources, load_raw_sources, profile_sources
from pipeline.config import (
    CACHE_PATH,
    CLEAN_DIR,
    FEATURES_DIR,
    LAB_CODES,
    MODEL_VERSION,
    RESULTS_DIR,
    RISA_AVAILABLE,
    RisaDataNotFoundError,
)
from pipeline.evaluacion_comun import FEATURE_KEYS
from pipeline.explicacion import build_explanation
from pipeline.fusion_evidencia import assign_evidence_roles
from pipeline.modelado import AlertDraft, calibrate_thresholds, extract_features, score_patient
from pipeline.preparacion_datos import (
    clean_laboratory_results,
    clean_vital_signs,
    clean_wearables,
    labs_long_for_dataset,
    pivot_vitals_wide,
)

WINDOW_HOURS = 120  # ventana de análisis anclada al último dato disponible por paciente (~5 días)


@dataclass
class PipelineResult:
    origin: str
    patients: pd.DataFrame
    vitals_wide: pd.DataFrame
    labs_long: pd.DataFrame
    alert_drafts: list[AlertDraft]
    anomaly_scores: dict[str, float]
    pattern_scores: dict[str, float]
    risk_scores: dict[str, float]
    priority_levels: dict[str, str]
    quality_report: dict
    evaluation: dict
    model_version: str = MODEL_VERSION

    def vitals_for(self, patient_id: str) -> pd.DataFrame:
        return self.vitals_wide[self.vitals_wide["patient_id"] == patient_id].sort_values("timestamp")

    def labs_for(self, patient_id: str) -> pd.DataFrame:
        return self.labs_long[self.labs_long["patient_id"] == patient_id].sort_values("timestamp")


def _attach_context_and_quality(vitals_wide: pd.DataFrame, raw: RawSources) -> pd.DataFrame:
    """Context Engine (actividad + sueño, `motor_contexto.py`) + calidad técnica del dispositivo."""
    wearables = clean_wearables(raw)
    out = motor_contexto.attach_activity(vitals_wide, wearables)
    out = motor_contexto.attach_sleep(out, raw.patient_context)

    devices = raw.device_observations.copy()
    devices["value"] = pd.to_numeric(devices["value"], errors="coerce")
    quality = (
        devices[devices["variable_code"] == "SIGNAL_QUALITY_INDEX"][["patient_id", "timestamp", "value"]]
        .rename(columns={"value": "signal_quality"})
        .sort_values("timestamp")
    )
    out = out.sort_values("timestamp")
    out = pd.merge_asof(out, quality, on="timestamp", by="patient_id", direction="nearest", tolerance=timedelta(hours=6))
    return out.sort_values(["patient_id", "timestamp"])


def _windowed(sub: pd.DataFrame, hours: int = WINDOW_HOURS) -> pd.DataFrame:
    """Recorta un sub-DataFrame de un solo paciente a la ventana de análisis (ancla: su último dato)."""
    if sub.empty:
        return sub
    decision = sub["timestamp"].max()
    return sub[sub["timestamp"] >= decision - timedelta(hours=hours)]


def _group_by_patient(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Agrupa una sola vez en vez de filtrar la tabla completa por paciente en un loop O(n·pacientes)."""
    return {pid: g for pid, g in df.groupby("patient_id", sort=False)}


def _persist_clean_layer(vitals_wide: pd.DataFrame, labs_long: pd.DataFrame, patients: pd.DataFrame) -> None:
    """Capa CLEAN del Documento Técnico Maestro V2: datos ya limpios/normalizados, como Parquet reutilizable."""
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    vitals_wide.to_parquet(CLEAN_DIR / "vitals_wide.parquet", index=False)
    labs_long.to_parquet(CLEAN_DIR / "labs_long.parquet", index=False)
    patients.to_parquet(CLEAN_DIR / "patients.parquet", index=False)


def _persist_features_layer(drafts: list[AlertDraft]) -> None:
    """Capa FEATURES del Documento Técnico Maestro V2: el vector por paciente que consumen Anomaly/Pattern Model."""
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    rows = [{"patient_id": d.patient_id, "pattern": d.pattern, "level": d.level, **{k: d.features.get(k) for k in FEATURE_KEYS}} for d in drafts]
    pd.DataFrame(rows).to_parquet(FEATURES_DIR / "patient_features.parquet", index=False)


def build_dataset(max_patients: int | None = None) -> PipelineResult:
    """Ejecuta comprensión + preparación + modelado + evaluación sobre RISA Data V1.0.

    No hay dataset sintético de reemplazo: si RISA Data V1.0 no está
    disponible, esto falla con `RisaDataNotFoundError` en vez de inventar
    datos (ver `pipeline/comprension_negocio.md`).
    """
    if not RISA_AVAILABLE:
        raise RisaDataNotFoundError()

    raw = load_raw_sources(max_patients=max_patients)
    quality_report = profile_sources(raw)

    clean_vitals, vitals_report = clean_vital_signs(raw)
    vitals_wide = pivot_vitals_wide(clean_vitals)
    vitals_wide = _attach_context_and_quality(vitals_wide, raw)

    clean_labs, labs_report = clean_laboratory_results(raw)
    labs_long = labs_long_for_dataset(clean_labs)

    quality_report["vital_signs_cleaning"] = vitals_report
    quality_report["laboratory_cleaning"] = labs_report
    quality_report["analysis_window_hours"] = WINDOW_HOURS

    _persist_clean_layer(vitals_wide, labs_long, raw.patients)

    vitals_by_patient = _group_by_patient(vitals_wide)
    labs_by_patient = _group_by_patient(labs_long)
    empty_vitals = vitals_wide.iloc[0:0]
    empty_labs = labs_long.iloc[0:0]

    # Paso 1: features crudas por paciente. Paso 2: se calibran los umbrales
    # de "cambio significativo" contra la población completa (no son
    # constantes fijas). Paso 3: cada paciente se puntúa con esos umbrales
    # (motor de reglas + Context Engine, `modelado.py`).
    all_features = []
    for pid in raw.patients["patient_id"].tolist():
        window_vitals = _windowed(vitals_by_patient.get(pid, empty_vitals))
        window_labs = _windowed(labs_by_patient.get(pid, empty_labs))
        all_features.append((pid, extract_features(pid, window_vitals, window_labs)))

    thresholds = calibrate_thresholds([f for _, f in all_features if f is not None])
    drafts: list[AlertDraft] = [
        score_patient(f, thresholds)
        if f is not None
        else AlertDraft(pid, 15, "MEDIO", "MISSING_SOURCE", "Sin lecturas de frecuencia cardíaca en la ventana", [], ["vital_signs:HR"], {})
        for pid, f in all_features
    ]
    _persist_features_layer(drafts)

    # Fase 5: Anomaly Model + Pattern Model, cada uno comparando varios
    # candidatos con matriz de confusión + precisión/recall/F1/ROC-AUC sobre
    # validación cruzada + test (ver `evaluacion.py` para el criterio de
    # selección de cada familia). Ambos ganadores se persisten en
    # `pipeline/data/model/`.
    comparison = evaluacion.compare_models(drafts)
    evaluacion.persist_best_models(comparison)
    anomaly_scores, pattern_scores = evaluacion.score_all(comparison, drafts)
    evaluation = evaluacion.comparison_report(comparison)

    # Risk Engine + Priority Engine: fusionan reglas + Anomaly Model +
    # Pattern Model en un risk_score/priority_level únicos por paciente.
    by_id = {d.patient_id: d for d in drafts}
    risk_scores = {
        pid: motor_riesgo.compute_risk_score(d, anomaly_scores.get(pid, 0.0), pattern_scores.get(pid, 0.0))
        for pid, d in by_id.items()
    }
    priority_levels = {pid: motor_prioridad.assign_priority(d.level, risk_scores[pid]) for pid, d in by_id.items()}

    return PipelineResult(
        origin="RISA_DATA_V1.0",
        patients=raw.patients,
        vitals_wide=vitals_wide,
        labs_long=labs_long,
        alert_drafts=drafts,
        anomaly_scores=anomaly_scores,
        pattern_scores=pattern_scores,
        risk_scores=risk_scores,
        priority_levels=priority_levels,
        quality_report=quality_report,
        evaluation=evaluation,
    )


def load_or_build(force: bool = False) -> PipelineResult:
    """Despliegue con caché: procesar ~250 MB de CSV en cada arranque del backend
    no es razonable, así que el resultado completo se serializa una vez.

    El caché no se invalida automáticamente: si `pipeline/` o los datos
    cambian, correr con `force=True` (o `python -m pipeline.run_pipeline
    --rebuild`).
    """
    if not force and CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    result = build_dataset()
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "wb") as f:
        pickle.dump(result, f)
    return result


def variable_catalog() -> list[dict]:
    names = {
        "heart_rate": ("Frecuencia cardíaca", "bpm", "vital_signs"),
        "resp_rate": ("Frecuencia respiratoria", "rpm", "vital_signs"),
        "spo2": ("Saturación de oxígeno", "%", "vital_signs"),
        "sbp": ("Presión sistólica", "mmHg", "vital_signs"),
        "dbp": ("Presión diastólica", "mmHg", "vital_signs"),
        "temp": ("Temperatura", "degC", "vital_signs"),
    }
    catalog = [{"key": k, "name": n, "unit": u, "source": s} for k, (n, u, s) in names.items()]
    for code in LAB_CODES:
        catalog.append({"key": code, "name": f"Marcador sintético de laboratorio {code[-1]}", "unit": f"u{code[-1]}", "source": "laboratory"})
    return catalog


def export_submission(result: PipelineResult, out_dir=RESULTS_DIR) -> tuple[int, int]:
    """Escribe signals.csv y evidence.csv (capa RESULTS) en el formato oficial del reto."""
    out_dir.mkdir(parents=True, exist_ok=True)
    signals_path = out_dir / "signals.csv"
    evidence_path = out_dir / "evidence.csv"

    signal_rows = []
    evidence_rows = []
    for i, draft in enumerate(result.alert_drafts, start=1):
        window = result.vitals_for(draft.patient_id)
        if window.empty:
            continue
        decision_dt = window["timestamp"].max()
        evidence_start = window["timestamp"].min()
        signal_id = f"SIG-{i:04d}"
        quality_median = draft.features.get("quality_median", 1.0) if draft.features else 1.0
        confidence = round(max(0.0, min(1.0, 0.6 + 0.4 * float(quality_median))), 3)
        risk_score = result.risk_scores.get(draft.patient_id, 0.0)
        priority_level = result.priority_levels.get(draft.patient_id, "LOW")
        fused = assign_evidence_roles(draft)
        explanation = build_explanation(draft, fused, risk_score, priority_level, result.model_version)

        signal_rows.append(
            {
                "signal_id": signal_id,
                "patient_id": draft.patient_id,
                "decision_datetime": decision_dt.isoformat(),
                "risk_score": risk_score,
                "priority_level": priority_level,
                "confidence_score": confidence,
                "evidence_start": evidence_start.isoformat(),
                "evidence_end": decision_dt.isoformat(),
                "explanation": explanation,
                "model_version": result.model_version,
            }
        )
        for rank, fe in enumerate(fused):
            e = fe.item
            evidence_rows.append(
                {
                    "signal_id": signal_id,
                    "source_file": "vital_signs.csv" if e.source.startswith("vital") else ("laboratory_results.csv" if e.source == "laboratory" else e.source + ".csv"),
                    "record_id": f"{draft.patient_id}:{e.variable}",
                    "variable_code": e.variable,
                    "event_datetime": evidence_start.isoformat(),
                    "available_datetime": decision_dt.isoformat(),
                    "evidence_role": fe.role,
                    "contribution": round(draft.score / max(1, len(draft.evidence)) / 100.0, 3),
                }
            )

    _write_csv(signals_path, signal_rows, [
        "signal_id", "patient_id", "decision_datetime", "risk_score", "priority_level",
        "confidence_score", "evidence_start", "evidence_end", "explanation", "model_version",
    ])
    _write_csv(evidence_path, evidence_rows, [
        "signal_id", "source_file", "record_id", "variable_code", "event_datetime",
        "available_datetime", "evidence_role", "contribution",
    ])
    return len(signal_rows), len(evidence_rows)


def _write_csv(path, rows: list[dict], fieldnames: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
