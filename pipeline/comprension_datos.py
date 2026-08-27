"""CRISP-DM · Fase 2 — Comprensión de los datos (Data Understanding).

Carga cruda de las fuentes oficiales de RISA Data V1.0 y perfilado básico
(cobertura, completitud, rangos de fecha) que documenta qué llegó y con qué
calidad, antes de tocar nada. No limpia ni transforma: eso es la fase 3
(`preparacion_datos.py`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from pipeline.config import RISA_ROOT


@dataclass
class RawSources:
    patients: pd.DataFrame
    vital_signs: pd.DataFrame
    laboratory_results: pd.DataFrame
    wearable_observations: pd.DataFrame
    device_observations: pd.DataFrame
    patient_context: pd.DataFrame
    conditions: pd.DataFrame
    variable_catalog: pd.DataFrame
    units_catalog: pd.DataFrame
    patient_ids: list[str] = field(init=False)

    def __post_init__(self) -> None:
        self.patient_ids = self.patients["patient_id"].tolist()


def _read(name: str, usecols: list[str] | None = None, parse_dates: list[str] | None = None) -> pd.DataFrame:
    path = next(RISA_ROOT.rglob(name))
    df = pd.read_csv(path, usecols=usecols)
    # `read_csv(parse_dates=...)` combinado con `usecols` puede degradar en
    # silencio a texto plano en archivos grandes; se convierte explícitamente.
    for col in parse_dates or []:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def load_raw_sources(max_patients: int | None = None) -> RawSources:
    """Carga las tablas oficiales de RISA Data V1.0 tal cual llegan (fase Data Understanding)."""
    patients = _read("patients.csv")
    if max_patients:
        patients = patients.head(max_patients)
    keep = set(patients["patient_id"])

    vitals = _read(
        "vital_signs.csv",
        usecols=["patient_id", "timestamp", "variable_code", "value", "unit", "quality_flag"],
        parse_dates=["timestamp"],
    )
    labs = _read(
        "laboratory_results.csv",
        usecols=[
            "patient_id",
            "test_code",
            "result_value",
            "unit",
            "reference_low",
            "reference_high",
            "sample_datetime",
            "result_datetime",
            "quality_flag",
        ],
        parse_dates=["sample_datetime", "result_datetime"],
    )
    wearables = _read(
        "wearable_observations.csv",
        usecols=["patient_id", "timestamp", "variable_code", "value", "measurement_quality", "sync_datetime"],
        parse_dates=["timestamp", "sync_datetime"],
    )
    devices = _read(
        "device_observations.csv",
        usecols=["patient_id", "timestamp", "variable_code", "value", "signal_quality"],
        parse_dates=["timestamp"],
    )
    context = _read(
        "patient_context.csv",
        usecols=["patient_id", "start_datetime", "end_datetime", "context_type", "context_value", "confidence"],
        parse_dates=["start_datetime", "end_datetime"],
    )
    conditions = _read(
        "conditions.csv",
        usecols=["patient_id", "condition_category", "onset_date", "status", "recorded_datetime"],
        parse_dates=["onset_date", "recorded_datetime"],
    )
    variable_catalog = _read("variable_catalog.csv")
    units_catalog = _read("units_catalog.csv")

    if max_patients:
        vitals = vitals[vitals["patient_id"].isin(keep)]
        labs = labs[labs["patient_id"].isin(keep)]
        wearables = wearables[wearables["patient_id"].isin(keep)]
        devices = devices[devices["patient_id"].isin(keep)]
        context = context[context["patient_id"].isin(keep)]
        conditions = conditions[conditions["patient_id"].isin(keep)]

    return RawSources(
        patients=patients,
        vital_signs=vitals,
        laboratory_results=labs,
        wearable_observations=wearables,
        device_observations=devices,
        patient_context=context,
        conditions=conditions,
        variable_catalog=variable_catalog,
        units_catalog=units_catalog,
    )


def profile_sources(raw: RawSources) -> dict:
    """Reporte de comprensión de datos: volumen, cobertura de pacientes y calidad declarada por fuente."""

    def _quality(df: pd.DataFrame) -> dict:
        if "quality_flag" in df.columns:
            return df["quality_flag"].value_counts().to_dict()
        if "measurement_quality" in df.columns:
            return df["measurement_quality"].value_counts().to_dict()
        return {}

    tables = {
        "patients": raw.patients,
        "vital_signs": raw.vital_signs,
        "laboratory_results": raw.laboratory_results,
        "wearable_observations": raw.wearable_observations,
        "device_observations": raw.device_observations,
        "patient_context": raw.patient_context,
        "conditions": raw.conditions,
    }
    report = {}
    for name, df in tables.items():
        row = {"rows": int(len(df))}
        if "patient_id" in df.columns:
            row["patients_covered"] = int(df["patient_id"].nunique())
            row["patient_coverage_pct"] = round(100 * row["patients_covered"] / max(1, len(raw.patients)), 1)
        quality = _quality(df)
        if quality:
            row["quality_flags"] = quality
        report[name] = row
    return report
