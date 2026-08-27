"""Risk Engine (`docs/Negocio.md` 1.4.6): combina el score del motor de
reglas (`AlertDraft.score`, explicable, genera la evidencia) con los scores
del Anomaly Model y el Pattern Model (`deteccion_anomalias`,
`modelado_patrones`) en un `risk_score` único en [0, 1] — el formato que
exige `results/signals.csv`.

El objetivo explícito no es maximizar cuántas alertas se generan, sino la
pertinencia de las que sí se generan (Negocio.md 1.4.6): por eso un patrón
`DESCARTADO` nunca puede llegar a un risk_score alto, sin importar qué tan
alto puntúen los modelos de ML sobre esos mismos features — las reglas ya
determinaron, con evidencia, que la variación es esperada.
"""

from __future__ import annotations

from pipeline.modelado import AlertDraft

DISCARDED_RISK_CAP = 0.15
RULE_WEIGHT, ANOMALY_WEIGHT, PATTERN_WEIGHT = 0.5, 0.25, 0.25


def compute_risk_score(draft: AlertDraft, anomaly_score: float = 0.0, pattern_score: float = 0.0) -> float:
    rule_component = min(1.0, draft.score / 100.0)
    if draft.level == "DESCARTADO":
        return round(min(rule_component, DISCARDED_RISK_CAP), 3)
    blended = RULE_WEIGHT * rule_component + ANOMALY_WEIGHT * float(anomaly_score or 0.0) + PATTERN_WEIGHT * float(pattern_score or 0.0)
    return round(min(1.0, blended), 3)
