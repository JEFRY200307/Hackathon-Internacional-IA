"""Anomaly Model (`docs/Negocio.md` 1.4.2): ¿esta observación (o vector de
features de un paciente) es inusual respecto al comportamiento esperado de
la población? Anomalía no es lo mismo que riesgo (Negocio.md 1.2.3-C) — este
módulo solo produce el score/flag de anomalía; `motor_riesgo.py` decide qué
tanto pesa junto con el resto de la evidencia.

Tres familias de candidatos, comparadas objetivamente con el mismo criterio
que `modelado_patrones.py` (matriz de confusión + precisión/recall/F1/ROC-AUC
sobre validación cruzada + test), tal como pide "La selección final no estará
predeterminada" (Negocio.md 1.4.2):

1. **Estadística** — Z-score, MAD (median absolute deviation), IQR: sobre el
   mismo vector de features que los modelos de ML, no sobre un valor aislado.
2. **ML** — `IsolationForest`, `LocalOutlierFactor`.
3. **DL (ligero)** — un autoencoder (`MLPRegressor` con cuello de botella,
   error de reconstrucción como score de anomalía). No se usa PyTorch/TensorFlow:
   con ~1000 pacientes y un vector de 13 features, una red totalmente conectada
   pequeña ya cubre la familia "DL" sin la sobrecarga de un framework de deep
   learning completo — ver `pipeline/comprension_negocio.md` para la justificación.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import StratifiedKFold
from sklearn.neighbors import LocalOutlierFactor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

from pipeline.evaluacion_comun import CandidateMetrics, compute_metrics, effective_splits

ANOMALY_MODELS = ("zscore", "mad", "iqr", "isolation_forest", "local_outlier_factor", "autoencoder_mlp")


def _zscore_score(X: np.ndarray) -> np.ndarray:
    mu, sigma = X.mean(axis=0), X.std(axis=0)
    sigma = np.where(sigma < 1e-9, 1e-9, sigma)
    return np.abs((X - mu) / sigma).mean(axis=1)


def _mad_score(X: np.ndarray) -> np.ndarray:
    median = np.median(X, axis=0)
    mad = np.median(np.abs(X - median), axis=0)
    mad = np.where(mad < 1e-9, 1e-9, mad)
    return np.abs(0.6745 * (X - median) / mad).mean(axis=1)


def _iqr_score(X: np.ndarray) -> np.ndarray:
    q1, q3 = np.percentile(X, [25, 75], axis=0)
    iqr = np.where((q3 - q1) < 1e-9, 1e-9, q3 - q1)
    below, above = (q1 - 1.5 * iqr) - X, X - (q3 + 1.5 * iqr)
    excess = np.maximum(below, above)
    return np.maximum(excess, 0).mean(axis=1) / (iqr.mean())


class _StatisticalDetector:
    """Adaptador stateless (Z-score/MAD/IQR) con la misma interfaz `fit`/`predict`/`score` que sklearn."""

    def __init__(self, score_fn, threshold_percentile: float = 90.0):
        self._score_fn = score_fn
        self._threshold_percentile = threshold_percentile
        self._threshold = 0.0

    def fit(self, X: np.ndarray) -> "_StatisticalDetector":
        self._threshold = float(np.percentile(self._score_fn(X), self._threshold_percentile))
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        return self._score_fn(X)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (self.score(X) > self._threshold).astype(int)


def _autoencoder(seed: int) -> MLPRegressor:
    return MLPRegressor(
        hidden_layer_sizes=(8, 3, 8),
        activation="relu",
        max_iter=2000,
        early_stopping=True,
        random_state=seed,
    )


_BUILDERS = {
    "zscore": lambda seed: _StatisticalDetector(_zscore_score),
    "mad": lambda seed: _StatisticalDetector(_mad_score),
    "iqr": lambda seed: _StatisticalDetector(_iqr_score),
    "isolation_forest": lambda seed: IsolationForest(random_state=seed, contamination=0.1, n_estimators=200),
    "local_outlier_factor": lambda seed: LocalOutlierFactor(n_neighbors=20, contamination=0.1, novelty=True),
    "autoencoder_mlp": lambda seed: _autoencoder(seed),
}


def _fit_predict(name: str, model, X_train: np.ndarray, X_eval: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if name == "autoencoder_mlp":
        model.fit(X_train, X_train)
        recon_error = ((model.predict(X_eval) - X_eval) ** 2).mean(axis=1)
        train_error = ((model.predict(X_train) - X_train) ** 2).mean(axis=1)
        threshold = float(np.percentile(train_error, 90))
        return (recon_error > threshold).astype(int), recon_error
    if name in {"zscore", "mad", "iqr"}:
        model.fit(X_train)
        return model.predict(X_eval), model.score(X_eval)
    model.fit(X_train)
    return (model.predict(X_eval) == -1).astype(int), -model.decision_function(X_eval)


def compare_anomaly_models(
    X_dev: np.ndarray, y_dev: np.ndarray, X_test: np.ndarray, y_test: np.ndarray, seed: int = 42, n_splits: int = 5
) -> tuple[dict[str, dict[str, CandidateMetrics]], str, object]:
    """Compara los 6 candidatos del Anomaly Model. Devuelve (métricas, nombre elegido, estimador reentrenado sobre todo `dev`)."""
    n_splits_eff = effective_splits(n_splits, y_dev)
    cv = StratifiedKFold(n_splits=n_splits_eff, shuffle=True, random_state=seed)

    candidates: dict[str, dict[str, CandidateMetrics]] = {}
    fitted: dict[str, object] = {}

    for name, build_fn in _BUILDERS.items():
        preds, scores = np.zeros(len(y_dev), dtype=int), np.zeros(len(y_dev), dtype=float)
        for train_idx, val_idx in cv.split(X_dev, y_dev):
            fold_model = build_fn(seed)
            preds[val_idx], scores[val_idx] = _fit_predict(name, fold_model, X_dev[train_idx], X_dev[val_idx])
        cv_metrics = compute_metrics(y_dev, preds, scores)

        final_model = build_fn(seed)
        pt, st = _fit_predict(name, final_model, X_dev, X_test)
        fitted[name] = final_model
        candidates[name] = {"cv": cv_metrics, "test": compute_metrics(y_test, pt, st)}

    chosen_name = max(ANOMALY_MODELS, key=lambda n: (candidates[n]["cv"].f1, candidates[n]["cv"].precision))
    return candidates, chosen_name, fitted[chosen_name]


def score_all(scaler: StandardScaler, model, name: str, X_all: np.ndarray) -> np.ndarray:
    """Score de anomalía normalizado 0-1 para todos los pacientes, con el modelo elegido ya entrenado."""
    Xs = scaler.transform(X_all)
    if name == "autoencoder_mlp":
        raw = ((model.predict(Xs) - Xs) ** 2).mean(axis=1)
    elif name in {"zscore", "mad", "iqr"}:
        raw = model.score(Xs)
    else:
        raw = -model.decision_function(Xs)
    lo, hi = float(raw.min()), float(raw.max())
    return (raw - lo) / (hi - lo + 1e-9)
