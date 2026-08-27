"""CRISP-DM · Fase 5 — Evaluación: orquesta la comparación del Anomaly Model
(`deteccion_anomalias.py`) y del Pattern Model (`modelado_patrones.py`)
descritos en `docs/Negocio.md` 1.4.2/1.4.3, sobre el mismo split y el mismo
vector de features.

La guía oficial es explícita: **no se entrega Gold Standard** con RISA Data
V1.0 (`02_KIT_ENTREGA/README_SUBMISSION_KIT.md`). Por eso se usa una
**etiqueta débil (proxy)**: "caso relevante" es todo paciente cuyo patrón fue
corroborado por ≥2 fuentes de forma temporal (`PROGRESSIVE_MULTISOURCE`,
`EARLY_SIGNAL`); el resto es "no relevante". Mide consistencia entre
enfoques, no precisión clínica real (`ADR-0009`).

El split es por paciente, 85 % / 15 %: el 85 % ("train+val" combinados,
"dev") se usa para **validación cruzada de k folds** (evita elegir el
ganador con un único split de validación pequeño y ruidoso — con ~1000
pacientes y una etiqueta positiva minoritaria, un solo split de 150 puede
tener 3-4 positivos), y el 15 % restante ("test") queda intocado hasta el
chequeo final. El ganador de cada familia (Anomaly Model / Pattern Model) se
reentrena sobre todo `dev` y se **persiste en disco**
(`pipeline/data/model/`) para que el backend los cargue y los use como score
secundario en cada alerta — no se entrenan de nuevo en cada request.
"""

from __future__ import annotations

import json
from dataclasses import asdict

import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import joblib

from pipeline import deteccion_anomalias, modelado_patrones
from pipeline.config import MODEL_DIR
from pipeline.evaluacion_comun import FEATURE_KEYS, LABELS_SOURCE, effective_splits, feature_matrix, split_patients, weak_labels
from pipeline.modelado import AlertDraft

ANOMALY_MODEL_PATH = MODEL_DIR / "anomaly_model_best.joblib"
ANOMALY_METADATA_PATH = MODEL_DIR / "anomaly_model_metadata.json"
PATTERN_MODEL_PATH = MODEL_DIR / "pattern_model_best.joblib"
PATTERN_METADATA_PATH = MODEL_DIR / "pattern_model_metadata.json"


class ModelComparisonResult:
    def __init__(self, anomaly, pattern, seed: int, n_splits_eff: int) -> None:
        self.anomaly_candidates, self.anomaly_chosen, self.anomaly_estimator = anomaly
        self.pattern_candidates, self.pattern_chosen, self.pattern_estimator = pattern
        self.seed = seed
        self.n_splits_eff = n_splits_eff


def compare_models(drafts: list[AlertDraft], seed: int = 42, n_splits: int = 5) -> ModelComparisonResult:
    labels = weak_labels(drafts)
    splits = split_patients([d.patient_id for d in drafts], seed=seed)
    dev_ids = splits["train"] + splits["val"]

    X_dev, ids_dev = feature_matrix(drafts, dev_ids)
    X_test, ids_test = feature_matrix(drafts, splits["test"])
    y_dev = _labels_array(labels, ids_dev)
    y_test = _labels_array(labels, ids_test)

    scaler = StandardScaler().fit(X_dev)
    Xd, Xte = scaler.transform(X_dev), scaler.transform(X_test)

    anomaly_candidates, anomaly_chosen, anomaly_model = deteccion_anomalias.compare_anomaly_models(Xd, y_dev, Xte, y_test, seed=seed, n_splits=n_splits)
    pattern_candidates, pattern_chosen, pattern_model = modelado_patrones.compare_pattern_models(Xd, y_dev, Xte, y_test, seed=seed, n_splits=n_splits)

    result = ModelComparisonResult(
        anomaly=(anomaly_candidates, anomaly_chosen, Pipeline([("scaler", scaler), ("model", anomaly_model)])),
        pattern=(pattern_candidates, pattern_chosen, Pipeline([("scaler", scaler), ("model", pattern_model)])),
        seed=seed,
        n_splits_eff=effective_splits(n_splits, y_dev),
    )
    return result


def _labels_array(labels: dict[str, int], ids: list[str]) -> np.ndarray:
    return np.array([labels[i] for i in ids])


def score_all(comparison: ModelComparisonResult, drafts: list[AlertDraft]) -> tuple[dict[str, float], dict[str, float]]:
    """Aplica ambos modelos ganadores (ya entrenados) a todos los pacientes — no reentrena."""
    X_all, ids_all = feature_matrix(drafts, [d.patient_id for d in drafts])

    anomaly_scaler = comparison.anomaly_estimator.named_steps["scaler"]
    anomaly_scores = deteccion_anomalias.score_all(anomaly_scaler, comparison.anomaly_estimator.named_steps["model"], comparison.anomaly_chosen, X_all)

    pattern_scaler = comparison.pattern_estimator.named_steps["scaler"]
    pattern_scores = modelado_patrones.score_all(pattern_scaler, comparison.pattern_estimator.named_steps["model"], X_all)

    return (
        {pid: float(s) for pid, s in zip(ids_all, anomaly_scores)},
        {pid: float(s) for pid, s in zip(ids_all, pattern_scores)},
    )


def _selection_rule(family: str, models: tuple[str, ...], n_splits_eff: int) -> str:
    return (
        f"Mayor F1 promedio en validación cruzada de {n_splits_eff} folds sobre train+val "
        f"combinados entre los candidatos del {family} {models} (desempate: precisión). "
        "El modelo ganador se reentrena sobre todo train+val y se evalúa una sola vez sobre "
        "test, nunca usado en la selección."
    )


def persist_best_models(comparison: ModelComparisonResult) -> None:
    """Guarda ambos modelos ganadores como artefactos reales (`.joblib`), no solo en memoria."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(comparison.anomaly_estimator, ANOMALY_MODEL_PATH)
    joblib.dump(comparison.pattern_estimator, PATTERN_MODEL_PATH)

    ANOMALY_METADATA_PATH.write_text(
        json.dumps(
            {
                "family": "Anomaly Model (Negocio.md 1.4.2)",
                "chosen_model": comparison.anomaly_chosen,
                "feature_keys": FEATURE_KEYS,
                "labels_source": LABELS_SOURCE,
                "selection_rule": _selection_rule("Anomaly Model", deteccion_anomalias.ANOMALY_MODELS, comparison.n_splits_eff),
                "metrics": _serialize_candidates(comparison.anomaly_candidates),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    PATTERN_METADATA_PATH.write_text(
        json.dumps(
            {
                "family": "Pattern Model (Negocio.md 1.4.3)",
                "chosen_model": comparison.pattern_chosen,
                "feature_keys": FEATURE_KEYS,
                "labels_source": LABELS_SOURCE,
                "selection_rule": _selection_rule("Pattern Model", modelado_patrones.PATTERN_MODELS, comparison.n_splits_eff),
                "metrics": _serialize_candidates(comparison.pattern_candidates),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def load_best_models() -> tuple[tuple[object, dict], tuple[object, dict]]:
    """Carga ambos modelos ya entrenados y persistidos — para reutilizarlos sin volver a entrenar."""
    anomaly = joblib.load(ANOMALY_MODEL_PATH), json.loads(ANOMALY_METADATA_PATH.read_text(encoding="utf-8"))
    pattern = joblib.load(PATTERN_MODEL_PATH), json.loads(PATTERN_METADATA_PATH.read_text(encoding="utf-8"))
    return anomaly, pattern


def _serialize_candidates(candidates: dict) -> dict:
    return {name: {split: asdict(m) for split, m in splits.items()} for name, splits in candidates.items()}


def comparison_report(comparison: ModelComparisonResult) -> dict:
    """Vista serializable (sin los estimadores) para `GET /api/pipeline/report`."""
    return {
        "labels_source": LABELS_SOURCE,
        "feature_keys": FEATURE_KEYS,
        "anomaly_model": {
            "chosen_model": comparison.anomaly_chosen,
            "selection_rule": _selection_rule("Anomaly Model", deteccion_anomalias.ANOMALY_MODELS, comparison.n_splits_eff),
            "candidates": _serialize_candidates(comparison.anomaly_candidates),
        },
        "pattern_model": {
            "chosen_model": comparison.pattern_chosen,
            "selection_rule": _selection_rule("Pattern Model", modelado_patrones.PATTERN_MODELS, comparison.n_splits_eff),
            "candidates": _serialize_candidates(comparison.pattern_candidates),
        },
    }
