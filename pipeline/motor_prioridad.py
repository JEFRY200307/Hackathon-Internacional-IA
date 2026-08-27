"""Priority Engine (`docs/Negocio.md` 1.4.6): transforma el `risk_score` y el
nivel interno del motor de reglas en el `priority_level` oficial
(`LOW | MEDIUM | HIGH | CRITICAL`, Documento Técnico Maestro V2 sección 11).

La fuente principal es el nivel del motor de reglas (interpretable, con
evidencia asociada); el `risk_score` fusionado actúa como red de seguridad
que puede escalar —nunca degradar— la prioridad cuando el Anomaly/Pattern
Model coinciden en una lectura mucho más alta que las reglas solas.
"""

from __future__ import annotations

from pipeline.config import LEVEL_TO_OFFICIAL_PRIORITY

ESCALATION_THRESHOLD = 0.85


def assign_priority(level: str, risk_score: float) -> str:
    base = LEVEL_TO_OFFICIAL_PRIORITY.get(level, "LOW")
    if level != "DESCARTADO" and risk_score >= ESCALATION_THRESHOLD and base != "CRITICAL":
        return "CRITICAL"
    return base
