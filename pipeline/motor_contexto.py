"""Context Engine (`docs/Negocio.md` 1.4.4): reglas sobre actividad
(`ACTIVITY_LEVEL`, wearable) y sueño (`SLEEP_STATE`, `patient_context.csv`)
para interpretar una variación fisiológica según el contexto en que ocurrió.

El mismo cambio de FC no significa lo mismo en reposo, en actividad física o
dormido (Negocio.md, sección 1.2.3-E). Este módulo solo produce el contexto
—no decide si algo es una señal—; quien decide es `modelado.score_patient`,
que consulta `is_activity_explained` en vez de comparar medias a mano.

`SLEEP_STATE` es un intervalo (`start_datetime`/`end_datetime`), no un punto:
se asocia por pertenencia temporal, no solo por `patient_id` (Documento
Técnico Maestro V2, secciones 4 y 9) — antes de esto, `patient_context.csv`
no se usaba en absoluto en el pipeline.
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd


def activity_flag(activity_level: str | float | None) -> str:
    """REST/LIGHT -> 'rest'; MODERATE/HIGH -> 'activity'."""
    if not isinstance(activity_level, str):
        return "rest"
    return "activity" if activity_level.upper() in {"MODERATE", "HIGH"} else "rest"


def attach_activity(vitals_wide: pd.DataFrame, wearables: pd.DataFrame) -> pd.DataFrame:
    """Une `ACTIVITY_LEVEL` del wearable a cada fila de vitales por cercanía temporal (±2h)."""
    activity = (
        wearables[wearables["variable_code"] == "ACTIVITY_LEVEL"][["patient_id", "timestamp", "value"]]
        .rename(columns={"value": "activity_level"})
        .sort_values("timestamp")
    )
    out = vitals_wide.sort_values("timestamp")
    out = pd.merge_asof(out, activity, on="timestamp", by="patient_id", direction="nearest", tolerance=timedelta(hours=2))
    out["context"] = out["activity_level"].map(activity_flag)
    return out.drop(columns=["activity_level"])


def attach_sleep(vitals_wide: pd.DataFrame, patient_context: pd.DataFrame) -> pd.DataFrame:
    """Une `SLEEP_STATE` (intervalo) por pertenencia temporal: `start <= timestamp <= end`."""
    sleep = (
        patient_context[patient_context["context_type"] == "SLEEP_STATE"][
            ["patient_id", "start_datetime", "end_datetime", "context_value"]
        ]
        .sort_values("start_datetime")
    )
    out = vitals_wide.sort_values("timestamp")
    out = pd.merge_asof(
        out,
        sleep.rename(columns={"start_datetime": "timestamp"}),
        on="timestamp",
        by="patient_id",
        direction="backward",
    )
    outside_interval = out["end_datetime"].notna() & (out["timestamp"] > out["end_datetime"])
    out.loc[outside_interval, "context_value"] = None
    out = out.rename(columns={"context_value": "sleep_state"}).drop(columns=["end_datetime"])
    out["sleep_state"] = out["sleep_state"].fillna("AWAKE")
    return out.sort_values(["patient_id", "timestamp"])


def is_activity_explained(hr_activity: pd.Series, hr_rest: pd.Series, min_n: int = 3, delta: float = 20.0) -> bool:
    """Taquicardia explicada por contexto: FC alta solo coincide con ventanas de actividad."""
    return len(hr_activity) >= min_n and len(hr_rest) >= min_n and hr_activity.mean() > hr_rest.mean() + delta
