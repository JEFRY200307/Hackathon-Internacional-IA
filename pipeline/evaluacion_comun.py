"""Utilidades compartidas por `deteccion_anomalias.py`, `modelado_patrones.py` y
`evaluacion.py`: split por paciente, etiqueta débil, vector de features y
métricas (incluida matriz de confusión). Vive aparte para que ninguno de los
tres importe de otro y se generen ciclos.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score

from pipeline.modelado import AlertDraft

POSITIVE_PATTERNS = {"PROGRESSIVE_MULTISOURCE", "EARLY_SIGNAL"}
LABELS_SOURCE = "proxy/weak — RISA Data V1.0 no incluye Gold Standard (ver 02_KIT_ENTREGA)"

FEATURE_KEYS = [
    "hr_mean", "hr_slope", "spo2_min", "spo2_slope", "rr_slope",
    "sbp_last", "sbp_slope", "temp_mean", "missing_lab", "activity_frac",
    "quality_median", "lab_rise_max_frac", "sleep_frac",
]


def split_patients(patient_ids: list[str], seed: int = 42, ratios: tuple[float, float, float] = (0.7, 0.15, 0.15)) -> dict[str, list[str]]:
    """Split por paciente (no por fila) para no filtrar información entre conjuntos."""
    ids = sorted(patient_ids)
    random.Random(seed).shuffle(ids)
    n = len(ids)
    n_train = int(n * ratios[0])
    n_val = int(n * ratios[1])
    return {
        "train": ids[:n_train],
        "val": ids[n_train : n_train + n_val],
        "test": ids[n_train + n_val :],
    }


def weak_labels(drafts: list[AlertDraft]) -> dict[str, int]:
    return {d.patient_id: int(d.pattern in POSITIVE_PATTERNS and d.level != "DESCARTADO") for d in drafts}


def feature_matrix(drafts: list[AlertDraft], patient_ids: list[str]) -> tuple[np.ndarray, list[str]]:
    by_id = {d.patient_id: d for d in drafts}
    ids = [pid for pid in patient_ids if pid in by_id]
    rows = [[float(by_id[pid].features.get(k) or 0.0) for k in FEATURE_KEYS] for pid in ids]
    return np.array(rows, dtype=float), ids


@dataclass
class CandidateMetrics:
    precision: float
    recall: float
    f1: float
    roc_auc: float | None
    confusion_matrix: dict[str, int]
    n: int
    positives: int


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_score: np.ndarray | None = None) -> CandidateMetrics:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    auc = None
    if y_score is not None and len(set(y_true.tolist())) > 1:
        try:
            auc = round(float(roc_auc_score(y_true, y_score)), 3)
        except ValueError:
            auc = None
    return CandidateMetrics(
        precision=round(float(precision_score(y_true, y_pred, zero_division=0)), 3),
        recall=round(float(recall_score(y_true, y_pred, zero_division=0)), 3),
        f1=round(float(f1_score(y_true, y_pred, zero_division=0)), 3),
        roc_auc=auc,
        confusion_matrix={"tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn)},
        n=int(len(y_true)),
        positives=int(y_true.sum()),
    )


def effective_splits(n_splits: int, y_dev: np.ndarray) -> int:
    n_pos, n_neg = int(y_dev.sum()), int(len(y_dev) - y_dev.sum())
    return max(2, min(n_splits, n_pos or 1, n_neg or 1))
