"""CRISP-DM · Fase 3 — Preparación de los datos (limpieza + tratamiento de calidad).

Aplica, de forma explícita y auditable, las condiciones de calidad que pide la
guía oficial: duplicados/retransmisiones, variantes de unidad, valores
implausibles y trazabilidad de qué se tocó. Nada se descarta en silencio: lo
implausible se recorta (winsoriza) para el cálculo de features pero el valor
crudo queda disponible en `value_raw` para auditoría.

No aplica todavía la regla temporal de disponibilidad (`available_datetime`)
— eso depende de un `decision_datetime` por paciente y vive en
`modelado.py`/`despliegue.py`, que es donde realmente importa evitar mirar
al futuro.
"""

from __future__ import annotations

import pandas as pd

from pipeline.comprension_datos import RawSources
from pipeline.config import VITAL_CODE_TO_KEY


def _unit_conversion(units_catalog: pd.DataFrame) -> dict[str, tuple[float, float, str]]:
    return {
        row.unit_code: (float(row.conversion_factor), float(row.conversion_offset), row.canonical_unit)
        for row in units_catalog.itertuples()
    }


def _to_canonical(df: pd.DataFrame, value_col: str, unit_col: str, conv: dict) -> pd.DataFrame:
    """Convierte value/unit a la unidad canónica del catálogo (p. ej. degF -> degC)."""
    factors = df[unit_col].map(lambda u: conv.get(u, (1.0, 0.0, u))[0])
    offsets = df[unit_col].map(lambda u: conv.get(u, (1.0, 0.0, u))[1])
    canonical_unit = df[unit_col].map(lambda u: conv.get(u, (1.0, 0.0, u))[2])
    out = df.copy()
    out[value_col] = pd.to_numeric(out[value_col], errors="coerce") * factors + offsets
    out[unit_col] = canonical_unit
    return out


def clean_vital_signs(raw: RawSources) -> tuple[pd.DataFrame, dict]:
    """Deduplica, normaliza unidad y trata implausibles de `vital_signs`."""
    conv = _unit_conversion(raw.units_catalog)
    df = raw.vital_signs.copy()
    before = len(df)

    # RETRANSMITTED / duplicados exactos: se queda la última lectura del mismo
    # (paciente, variable, timestamp) — la retransmisión es la corrección.
    df = df.sort_values("timestamp").drop_duplicates(subset=["patient_id", "variable_code", "timestamp"], keep="last")
    duplicates_removed = before - len(df)

    df = _to_canonical(df, "value", "unit", conv)

    bounds = raw.variable_catalog.set_index("variable_code")[["plausibility_min", "plausibility_max"]]
    df = df.join(bounds, on="variable_code")
    df["value_raw"] = df["value"]
    implausible = (df["value"] < df["plausibility_min"]) | (df["value"] > df["plausibility_max"])
    implausible &= df["plausibility_min"].notna()
    df["is_plausible"] = ~implausible
    df.loc[implausible, "value"] = df.loc[implausible, "value"].clip(
        lower=df.loc[implausible, "plausibility_min"], upper=df.loc[implausible, "plausibility_max"]
    )
    df = df.drop(columns=["plausibility_min", "plausibility_max"])

    report = {
        "rows_in": before,
        "duplicates_removed": int(duplicates_removed),
        "implausible_clipped": int(implausible.sum()),
        "quality_flag_counts": df["quality_flag"].value_counts().to_dict(),
    }
    return df, report


def pivot_vitals_wide(clean_vitals: pd.DataFrame) -> pd.DataFrame:
    """Formato ancho por (paciente, timestamp): una columna por variable vital.

    No se rellena hacia adelante (ffill): cada celda vacía es una medición que
    RISA no tomó en ese instante, no un dato faltante que haya que inventar.
    """
    wide = clean_vitals.pivot_table(
        index=["patient_id", "timestamp"], columns="variable_code", values="value", aggfunc="first"
    ).reset_index()
    wide = wide.rename(columns=VITAL_CODE_TO_KEY)
    for key in VITAL_CODE_TO_KEY.values():
        if key not in wide.columns:
            wide[key] = pd.NA
    return wide.sort_values(["patient_id", "timestamp"])


def clean_laboratory_results(raw: RawSources) -> tuple[pd.DataFrame, dict]:
    """Deduplica y normaliza unidad de `laboratory_results`; conserva sample/result por separado."""
    conv = _unit_conversion(raw.units_catalog)
    df = raw.laboratory_results.copy()
    before = len(df)
    df = df.sort_values("result_datetime").drop_duplicates(
        subset=["patient_id", "test_code", "sample_datetime"], keep="last"
    )
    duplicates_removed = before - len(df)
    df = _to_canonical(df, "result_value", "unit", conv)

    bounds = raw.variable_catalog.set_index("variable_code")[["plausibility_min", "plausibility_max"]]
    df = df.join(bounds, on="test_code")
    df["result_value_raw"] = df["result_value"]
    implausible = (df["result_value"] < df["plausibility_min"]) | (df["result_value"] > df["plausibility_max"])
    implausible &= df["plausibility_min"].notna()
    df.loc[implausible, "result_value"] = df.loc[implausible, "result_value"].clip(
        lower=df.loc[implausible, "plausibility_min"], upper=df.loc[implausible, "plausibility_max"]
    )
    df = df.drop(columns=["plausibility_min", "plausibility_max"])

    report = {
        "rows_in": before,
        "duplicates_removed": int(duplicates_removed),
        "implausible_clipped": int(implausible.sum()),
        "quality_flag_counts": df["quality_flag"].value_counts().to_dict(),
    }
    return df, report


def labs_long_for_dataset(clean_labs: pd.DataFrame) -> pd.DataFrame:
    """Vista larga anclada en `result_datetime` (cuándo el laboratorio quedó DISPONIBLE, no cuándo se tomó).

    Cualquier consumidor que use esta tabla (gráficos, chat, tools) respeta
    automáticamente la regla temporal de la guía oficial: nunca ve un valor
    antes de que existiera en RISA.
    """
    out = clean_labs.rename(columns={"result_datetime": "timestamp", "test_code": "analyte", "result_value": "value"})
    return out[["patient_id", "timestamp", "analyte", "value", "unit"]].assign(source="laboratory").sort_values(
        ["patient_id", "timestamp"]
    )


def clean_wearables(raw: RawSources) -> pd.DataFrame:
    df = raw.wearable_observations.copy()
    return df.sort_values("timestamp").drop_duplicates(subset=["patient_id", "variable_code", "timestamp"], keep="last")
