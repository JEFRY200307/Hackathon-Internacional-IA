"""CRISP-DM · Fase 4 — Modelado.

Dos mecanismos complementarios, tal como fija `ADR-0002`:

1. Reglas dinámicas (`analyze_patient`): combinan ≥2 fuentes y su evolución
   temporal (pendientes, medias, deltas relativos) para detectar patrones —
   nunca un umbral estático de una sola variable. Los umbrales de "cambio
   significativo" no son constantes clínicas inventadas: se calibran contra
   la distribución real de las ~1000 series de RISA Data V1.0 en cada corrida
   (`calibrate_thresholds`, percentil 90/10 de cada pendiente). Es la fuente
   de la `explicación` y la `evidencia` que exige el reto.
2. Anomaly Model + Pattern Model (`deteccion_anomalias.py`, `modelado_patrones.py`):
   varios modelos entrenados y comparados sobre el mismo vector de features,
   con matriz de confusión y precisión/recall/F1/ROC-AUC — no una selección
   automática sin comparar, sino una comparación explícita con un criterio de
   elección documentado (orquestada desde `evaluacion.py`, fase 5).

Este módulo solo se ocupa de (1): features y reglas — es, en el lenguaje de
`docs/Negocio.md`, el motor de reglas que corrobora el Pattern Model y que
siempre corre para producir la evidencia trazable de cada alerta. La
interpretación de contexto (actividad/sueño) vive en `motor_contexto.py`;
este módulo la consulta, no la recalcula.

Los códigos de laboratorio (`LAB_A`..`LAB_D`) son marcadores sintéticos sin
significado clínico real (ver guía oficial): las reglas los tratan de forma
genérica como "evidencia multifuente que sube", no como creatinina/lactato.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from pipeline.config import LAB_CODES
from pipeline.motor_contexto import is_activity_explained

LEVELS = ("CRITICO", "ALTO", "MEDIO", "BAJO", "DESCARTADO")
LEVEL_ORDER = {level: i for i, level in enumerate(LEVELS)}

QUALITY_LOW_THRESHOLD = 0.55  # índice 0-1, umbral absoluto: por debajo, el fabricante ya lo marca poco confiable
CALIBRATION_PCT = 90  # percentil poblacional para "cambio significativo" (10 = cola opuesta para caídas)


def _slope(series: pd.Series) -> float:
    """Pendiente por muestra de una serie temporal, robusta a NaN y series cortas."""
    s = series.dropna()
    if len(s) < 4:
        return 0.0
    y = s.astype(float).to_numpy()
    x = np.arange(len(y), dtype=float)
    return float(np.polyfit(x, y, 1)[0])


def _level(score: int, discarded: bool) -> str:
    if discarded:
        return "DESCARTADO"
    if score >= 80:
        return "CRITICO"
    if score >= 55:
        return "ALTO"
    if score >= 30:
        return "MEDIO"
    return "BAJO"


@dataclass
class EvidenceItem:
    variable: str
    source: str
    window: str
    detail: str
    values: dict = field(default_factory=dict)


@dataclass
class AlertDraft:
    patient_id: str
    score: int
    level: str
    pattern: str
    title: str
    evidence: list[EvidenceItem]
    missing_sources: list[str]
    features: dict


@dataclass
class PopulationThresholds:
    """Calibrados sobre la población completa analizada en la corrida (no constantes fijas)."""

    hr_slope_up: float
    spo2_slope_down: float
    rr_slope_up: float
    sbp_slope_down: float
    lab_rise_frac: float
    hr_mean_high: float
    temp_mean_high: float


def _lab_series(labs: pd.DataFrame, analyte: str) -> pd.Series:
    if labs.empty:
        return pd.Series(dtype=float)
    sub = labs[labs["analyte"] == analyte].sort_values("timestamp")
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.set_index("timestamp")["value"].dropna().astype(float)


def _max_lab_rise(labs: pd.DataFrame) -> tuple[str | None, float]:
    """Mayor variación relativa (>=2 lecturas) entre los marcadores LAB_A..D presentes."""
    best_code, best_frac = None, 0.0
    for code in LAB_CODES:
        series = _lab_series(labs, code)
        if len(series) < 2:
            continue
        delta = float(series.iloc[-1] - series.iloc[0])
        base = max(abs(float(series.iloc[0])), 1e-6)
        frac = delta / base
        if frac > best_frac:
            best_code, best_frac = code, frac
    return best_code, best_frac


def extract_features(patient_id: str, vitals: pd.DataFrame, labs: pd.DataFrame) -> dict | None:
    """Primer paso del modelado: features crudas por paciente, sin decidir todavía patrón/score.

    Devuelve `None` cuando no hay frecuencia cardíaca en la ventana — ese caso
    se resuelve directamente como `MISSING_SOURCE` en `analyze_patient`.
    """
    if vitals.empty or "heart_rate" not in vitals:
        return None
    hr = vitals["heart_rate"].dropna().astype(float)
    if hr.empty:
        return None

    spo2 = vitals["spo2"].dropna().astype(float)
    rr = vitals["resp_rate"].dropna().astype(float)
    sbp = vitals["sbp"].dropna().astype(float)
    temp = vitals["temp"].dropna().astype(float)
    ctx = vitals.get("context", pd.Series(dtype=str)).fillna("rest")
    quality = vitals.get("signal_quality", pd.Series(dtype=float)).dropna()
    sleep_state = vitals.get("sleep_state", pd.Series(dtype=str))

    hr_activity = hr[ctx.reindex(hr.index, fill_value="rest") == "activity"]
    hr_rest = hr[ctx.reindex(hr.index, fill_value="rest") != "activity"]
    sleep_frac = float((sleep_state == "SLEEP").mean()) if len(sleep_state) else 0.0
    lab_code, lab_rise_frac = _max_lab_rise(labs)
    lab_series_by_code = {code: _lab_series(labs, code) for code in LAB_CODES}

    return {
        "patient_id": patient_id,
        "hr": hr,
        "spo2": spo2,
        "rr": rr,
        "sbp": sbp,
        "temp": temp,
        "hr_activity": hr_activity,
        "hr_rest": hr_rest,
        "sleep_frac": sleep_frac,
        "missing_lab": labs.empty,
        "lab_code": lab_code,
        "lab_rise_frac": lab_rise_frac,
        "lab_series_by_code": lab_series_by_code,
        "hr_slope": _slope(hr),
        "spo2_slope": _slope(spo2),
        "rr_slope": _slope(rr),
        "sbp_slope": _slope(sbp),
        "hr_mean": float(hr.mean()),
        "temp_mean": float(temp.mean()) if len(temp) else None,
        "quality_median": float(quality.median()) if len(quality) else 1.0,
        "quality_n": int(len(quality)),
    }


def calibrate_thresholds(features_list: list[dict], pct: int = CALIBRATION_PCT) -> PopulationThresholds:
    """Segundo paso: percentiles poblacionales de "cambio significativo" — no umbrales fijos inventados."""

    def _pct(key: str, p: float, default: float = 0.0) -> float:
        values = [f[key] for f in features_list if f is not None and f.get(key) is not None]
        return float(np.percentile(values, p)) if values else default

    return PopulationThresholds(
        hr_slope_up=max(_pct("hr_slope", pct), 1e-4),
        spo2_slope_down=min(_pct("spo2_slope", 100 - pct), -1e-4),
        rr_slope_up=max(_pct("rr_slope", pct), 1e-4),
        sbp_slope_down=min(_pct("sbp_slope", 100 - pct), -1e-3),
        lab_rise_frac=max(_pct("lab_rise_frac", pct), 0.15),
        hr_mean_high=_pct("hr_mean", pct, default=100.0),
        temp_mean_high=_pct("temp_mean", 95, default=38.0),
    )


def score_patient(feats: dict, th: PopulationThresholds) -> AlertDraft:
    """Tercer paso: decide patrón, score y evidencia usando los umbrales calibrados en el paso 2."""
    pid = feats["patient_id"]
    hr, spo2, sbp, temp = feats["hr"], feats["spo2"], feats["sbp"], feats["temp"]
    hr_activity, hr_rest = feats["hr_activity"], feats["hr_rest"]
    hr_slope, spo2_slope, rr_slope, sbp_slope = feats["hr_slope"], feats["spo2_slope"], feats["rr_slope"], feats["sbp_slope"]
    lab_code, lab_rise_frac = feats["lab_code"], feats["lab_rise_frac"]
    quality_median = feats["quality_median"]

    evidence: list[EvidenceItem] = []
    missing: list[str] = ["laboratory"] if feats["missing_lab"] else []
    score = 0
    pattern, title, discarded = "STABLE", "Sin patrón relevante", False
    window = "ventana disponible"

    if quality_median < QUALITY_LOW_THRESHOLD and feats["quality_n"] >= 3:
        discarded, pattern = True, "LOW_QUALITY"
        title = "Señal técnica de baja calidad — no se prioriza sin corroborar"
        evidence.append(EvidenceItem("signal_quality_index", "device_observations", window,
                                      "Índice de calidad de señal por debajo de lo confiable en la mayoría de lecturas del dispositivo.",
                                      {"quality_median": round(quality_median, 2), "n": feats["quality_n"]}))

    if not discarded and is_activity_explained(hr_activity, hr_rest):
        discarded, pattern = True, "CONTEXTUAL"
        title = "Taquicardia explicada por contexto de actividad"
        evidence.append(EvidenceItem("heart_rate", "vital_signs + wearable_observations", window,
                                      "FC alta solo coincide con ACTIVITY_LEVEL alto; en reposo la FC es la esperada para este paciente.",
                                      {"hr_activity_mean": round(float(hr_activity.mean()), 1), "hr_rest_mean": round(float(hr_rest.mean()), 1)}))

    if not discarded:
        median = float(hr.median())
        outliers = hr[hr > median + 3 * hr.std(ddof=0)] if hr.std(ddof=0) > 0 else hr[hr > median + 20]
        if 0 < len(outliers) <= 2 and abs(hr_slope) < th.hr_slope_up:
            discarded, pattern = True, "TRANSIENT"
            title = "Outlier transitorio de FC que se normaliza"
            evidence.append(EvidenceItem("heart_rate", "vital_signs", window,
                                          "Pico aislado; el resto de la serie vuelve a la mediana sin tendencia sostenida.",
                                          {"median": round(median, 1), "peak": round(float(hr.max()), 1), "n_outliers": int(len(outliers))}))

    if not discarded and hr_slope >= th.hr_slope_up and lab_code and lab_rise_frac >= th.lab_rise_frac:
        score += 55
        pattern, title = "PROGRESSIVE_MULTISOURCE", f"Evolución conjunta de FC y {lab_code} (poco frecuente en la población)"
        series = feats["lab_series_by_code"][lab_code]
        evidence.append(EvidenceItem("heart_rate", "vital_signs", window, "Tendencia ascendente de FC por encima del percentil poblacional calibrado.",
                                      {"slope": round(hr_slope, 5), "p90_poblacional": round(th.hr_slope_up, 5), "last": round(float(hr.iloc[-1]), 1)}))
        evidence.append(EvidenceItem(lab_code, "laboratory", window, f"{lab_code} en escalada (no un valor aislado).",
                                      {"first": round(float(series.iloc[0]), 3), "last": round(float(series.iloc[-1]), 3), "delta_frac": round(lab_rise_frac, 2)}))

    if not discarded and spo2_slope <= th.spo2_slope_down and rr_slope >= th.rr_slope_up:
        score += 40
        if pattern == "STABLE":
            pattern, title = "EARLY_SIGNAL", "Caída de SpO2 con aumento de FR (ambas fuera de lo esperado)"
        evidence.append(EvidenceItem("spo2", "vital_signs", window, "SpO2 con pendiente negativa por debajo del percentil poblacional calibrado.",
                                      {"slope": round(spo2_slope, 5), "p10_poblacional": round(th.spo2_slope_down, 5)}))
        evidence.append(EvidenceItem("resp_rate", "vital_signs", window, "FR en aumento por encima del percentil poblacional calibrado, misma ventana.",
                                      {"slope": round(rr_slope, 5), "p90_poblacional": round(th.rr_slope_up, 5)}))

    if not discarded and sbp_slope <= th.sbp_slope_down and lab_code and lab_rise_frac >= th.lab_rise_frac:
        score += 50
        pattern, title = "PROGRESSIVE_MULTISOURCE", f"Hipotensión progresiva + {lab_code} en alza"
        series = feats["lab_series_by_code"][lab_code]
        evidence.append(EvidenceItem("sbp", "vital_signs", window, "Presión sistólica en descenso, por debajo del percentil poblacional calibrado.",
                                      {"slope": round(sbp_slope, 5), "p10_poblacional": round(th.sbp_slope_down, 5)}))
        evidence.append(EvidenceItem(lab_code, "laboratory", window, f"{lab_code} aumenta en la misma ventana (segunda fuente).",
                                      {"first": round(float(series.iloc[0]), 3), "last": round(float(series.iloc[-1]), 3)}))

    if not discarded and len(temp) and feats["temp_mean"] and feats["temp_mean"] >= th.temp_mean_high and feats["hr_mean"] >= th.hr_mean_high:
        score += 32
        if pattern == "STABLE":
            pattern, title = "EARLY_SIGNAL", "Temperatura y FC medias ambas en el extremo alto de la población (combinación, no un único pico)"
        evidence.append(EvidenceItem("temp", "vital_signs", window, "Temperatura media dentro del 5% más alto de la población en la ventana.", {"mean": round(feats["temp_mean"], 2), "p95_poblacional": round(th.temp_mean_high, 2)}))
        evidence.append(EvidenceItem("heart_rate", "vital_signs", window, "FC media dentro del rango alto de la población en la misma ventana.", {"mean": round(feats["hr_mean"], 1), "p90_poblacional": round(th.hr_mean_high, 1)}))

    if missing and not discarded:
        score += 18
        if pattern == "STABLE":
            pattern, title = "MISSING_SOURCE", "Fuente de laboratorio ausente; solo vitales"
        evidence.append(EvidenceItem("laboratory", "laboratory", window, "No hay registros de laboratorio disponibles para este paciente en la ventana.", {}))

    if not evidence and not discarded:
        title, pattern, score = "Variación dentro de lo esperado para la población", "STABLE", 8
        evidence.append(EvidenceItem("heart_rate", "vital_signs", window, "Serie sin tendencia relevante ni combinación con laboratorio, comparada contra la población.",
                                      {"mean": round(feats["hr_mean"], 1), "slope": round(hr_slope, 5)}))

    features_out = {
        "hr_mean": feats["hr_mean"],
        "hr_slope": hr_slope,
        "spo2_min": float(spo2.min()) if len(spo2) else 100.0,
        "spo2_slope": spo2_slope,
        "rr_slope": rr_slope,
        "sbp_last": float(sbp.iloc[-1]) if len(sbp) else None,
        "sbp_slope": sbp_slope,
        "temp_mean": feats["temp_mean"],
        "missing_lab": 1.0 if missing else 0.0,
        "activity_frac": float(len(hr_activity)) / max(1, len(hr)),
        "sleep_frac": feats["sleep_frac"],
        "quality_median": quality_median,
        "lab_rise_max_frac": lab_rise_frac,
        "lab_marker": lab_code,
    }
    return AlertDraft(pid, score, _level(score, discarded), pattern, title, evidence, missing, features_out)


def analyze_patient(patient_id: str, vitals: pd.DataFrame, labs: pd.DataFrame, thresholds: PopulationThresholds | None = None) -> AlertDraft:
    """Conveniencia de un solo paciente (usa umbrales por defecto si no se calibró población)."""
    feats = extract_features(patient_id, vitals, labs)
    if feats is None:
        return AlertDraft(patient_id, 15, "MEDIO", "MISSING_SOURCE", "Sin lecturas de frecuencia cardíaca en la ventana", [], ["vital_signs:HR"], {})
    th = thresholds or calibrate_thresholds([feats])
    return score_patient(feats, th)
