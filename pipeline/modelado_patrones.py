"""Pattern Model (`docs/Negocio.md` 1.4.3): ¿existe un patrón temporal o
multivariable —no un valor aislado— que justifique una señal? A diferencia
del Anomaly Model (no supervisado), estos candidatos se entrenan contra la
etiqueta débil (`evaluacion_comun.weak_labels`).

Candidatos evaluados, tal como pide "XGBoost y GRU serán candidatos, no
supuestos de diseño" (Negocio.md 1.4.3):

1. **Baseline** — regresión logística.
2. **ML** — Random Forest, XGBoost, LightGBM.
3. **DL** — GRU/LSTM/Transformer temporal: **evaluados y descartados sin
   entrenar**, no omitidos por descuido. Con ~1000 pacientes y ~30 positivos
   en la etiqueta débil, un modelo secuencial profundo no tiene datos
   suficientes para aprender nada que no sea ruido — necesitaría cientos de
   positivos por clase para generalizar. Además, nuestro vector de entrada ya
   es un resumen por ventana (pendientes, medias), no una secuencia cruda:
   meter un GRU/Transformer encima sería modelar profundamente sobre 13
   números agregados, no sobre una serie real. La propia guía lo permite
   ("la selección no está predeterminada... según disponibilidad y
   características de los datos" — Negocio.md 1.4.3): esta es esa decisión,
   documentada en vez de simulada con un modelo de juguete.
"""

from __future__ import annotations

import numpy as np
from lightgbm import LGBMClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from xgboost import XGBClassifier

from pipeline.evaluacion_comun import CandidateMetrics, compute_metrics, effective_splits

PATTERN_MODELS = ("logistic_regression", "random_forest", "xgboost", "lightgbm")

_BUILDERS = {
    "logistic_regression": lambda seed: LogisticRegression(class_weight="balanced", max_iter=1000, random_state=seed),
    "random_forest": lambda seed: RandomForestClassifier(class_weight="balanced", n_estimators=300, max_depth=6, random_state=seed),
    "xgboost": lambda seed: XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.1, eval_metric="logloss", random_state=seed),
    "lightgbm": lambda seed: LGBMClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.1, random_state=seed, verbosity=-1, min_child_samples=5, class_weight="balanced"
    ),
}


def _fit_with_class_weight(name: str, model, X: np.ndarray, y: np.ndarray):
    if name == "xgboost":
        n_pos, n_neg = max(1, int(y.sum())), max(1, int(len(y) - y.sum()))
        model.scale_pos_weight = n_neg / n_pos
    model.fit(X, y)
    return model


def compare_pattern_models(
    X_dev: np.ndarray, y_dev: np.ndarray, X_test: np.ndarray, y_test: np.ndarray, seed: int = 42, n_splits: int = 5
) -> tuple[dict[str, dict[str, CandidateMetrics]], str, object]:
    """Compara los 4 candidatos entrenables del Pattern Model (GRU/LSTM/Transformer: ver docstring del módulo)."""
    n_splits_eff = effective_splits(n_splits, y_dev)
    cv = StratifiedKFold(n_splits=n_splits_eff, shuffle=True, random_state=seed)

    candidates: dict[str, dict[str, CandidateMetrics]] = {}
    fitted: dict[str, object] = {}

    for name, build_fn in _BUILDERS.items():
        preds, scores = np.zeros(len(y_dev), dtype=int), np.zeros(len(y_dev), dtype=float)
        for train_idx, val_idx in cv.split(X_dev, y_dev):
            fold_model = _fit_with_class_weight(name, build_fn(seed), X_dev[train_idx], y_dev[train_idx])
            preds[val_idx] = fold_model.predict(X_dev[val_idx])
            scores[val_idx] = fold_model.predict_proba(X_dev[val_idx])[:, 1]
        cv_metrics = compute_metrics(y_dev, preds, scores)

        final_model = _fit_with_class_weight(name, build_fn(seed), X_dev, y_dev)
        pt, st = final_model.predict(X_test), final_model.predict_proba(X_test)[:, 1]
        fitted[name] = final_model
        candidates[name] = {"cv": cv_metrics, "test": compute_metrics(y_test, pt, st)}

    chosen_name = max(PATTERN_MODELS, key=lambda n: (candidates[n]["cv"].f1, candidates[n]["cv"].precision))
    return candidates, chosen_name, fitted[chosen_name]


def score_all(scaler, model, X_all: np.ndarray) -> np.ndarray:
    return model.predict_proba(scaler.transform(X_all))[:, 1]
