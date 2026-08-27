"""Rutas y constantes compartidas por todas las fases CRISP-DM del pipeline.

Estructura de datos por capas (`Documento Técnico Maestro V2`, sección 12 —
"Separar RAW, CLEAN/PROCESSED, FEATURES, MODEL y RESULTS"):

    pipeline/data/
    ├── raw/       # RISA Data V1.0 oficial, inmutable — nunca se escribe aquí
    ├── clean/     # salida de preparacion_datos.py (parquet, regenerable)
    ├── features/  # vectores de features por paciente (parquet, regenerable)
    ├── model/     # modelo ganador persistido (.joblib) + metadata — versionado
    ├── results/   # signals.csv + evidence.csv, el entregable oficial
    └── cache/     # PipelineResult serializado completo — regenerable, no versionado
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_ROOT = Path(__file__).resolve().parent
DATA_ROOT = PIPELINE_ROOT / "data"

RISA_ROOT = DATA_ROOT / "raw"
CLEAN_DIR = DATA_ROOT / "clean"
FEATURES_DIR = DATA_ROOT / "features"
MODEL_DIR = DATA_ROOT / "model"
RESULTS_DIR = DATA_ROOT / "results"
CACHE_DIR = DATA_ROOT / "cache"
CACHE_PATH = CACHE_DIR / "dataset.pkl"

MODEL_VERSION = "risa-signal-pipeline-1.1.0"

# Variables observacionales (05_metadata/variable_catalog.csv) mapeadas a las
# claves internas en snake_case que consumen backend y frontend.
VITAL_CODE_TO_KEY = {
    "HR": "heart_rate",
    "RR": "resp_rate",
    "SpO2": "spo2",
    "TEMP": "temp",
    "SBP": "sbp",
    "DBP": "dbp",
}
LAB_CODES = ("LAB_A", "LAB_B", "LAB_C", "LAB_D")

# Nivel interno (español, 5 niveles, usado por la UI) -> priority_level oficial
# exigido por el contrato de entrega (LOW/MEDIUM/HIGH/CRITICAL, Documento
# Técnico Maestro V2 sección 11).
LEVEL_TO_OFFICIAL_PRIORITY = {
    "CRITICO": "CRITICAL",
    "ALTO": "HIGH",
    "MEDIO": "MEDIUM",
    "BAJO": "LOW",
    "DESCARTADO": "LOW",
}

RISA_AVAILABLE = RISA_ROOT.exists() and (RISA_ROOT / "01_master" / "patients.csv").exists()


class RisaDataNotFoundError(RuntimeError):
    """RISA Data V1.0 no está disponible.

    El pipeline no genera ni sustituye datos: es la única fuente de verdad
    permitida por la guía oficial del reto. No hay fallback sintético — si
    esto se lanza, el backend debe fallar visiblemente, no degradar en
    silencio a datos inventados.
    """

    def __init__(self) -> None:
        super().__init__(
            "RISA Data V1.0 no encontrado en "
            f"'{RISA_ROOT}'. Este proyecto solo opera sobre el dataset oficial "
            "del reto (pipeline/data/raw/) — no existe ni se permite un dataset "
            "sintético de reemplazo. Verificá que la carpeta 'pipeline/data/raw/' "
            "esté presente en el repositorio."
        )
