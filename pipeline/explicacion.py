"""Explanation (`docs/Negocio.md` 1.4.7 / 1.5.7): redacta la explicación de
`results/signals.csv` a partir exclusivamente de la evidencia ya fusionada
(`fusion_evidencia.FusedEvidence`) — nunca inventa una variable o un hecho
que no esté en `AlertDraft.evidence`.

Sigue la estructura de siete preguntas que exige Negocio.md 1.5.7: qué
ocurrió, cuándo, qué cambió, qué variables participaron, qué contexto
existía, qué calidad tenían los datos y por qué se asignó la prioridad.
"""

from __future__ import annotations

from pipeline.fusion_evidencia import FusedEvidence
from pipeline.modelado import AlertDraft


def build_explanation(draft: AlertDraft, fused: list[FusedEvidence], risk_score: float, priority_level: str, model_version: str) -> str:
    variables = ", ".join(sorted({f.item.variable for f in fused})) or "sin variables asociadas"
    quality_notes = [f.item.detail for f in fused if f.role == "QUALITY"]
    context_notes = [f.item.detail for f in fused if f.role == "CONTEXT"]

    parts = [
        f"Qué: {draft.title} (patrón {draft.pattern}).",
        f"Variables: {variables}.",
    ]
    if context_notes:
        parts.append(f"Contexto: {' '.join(context_notes)}")
    if quality_notes:
        parts.append(f"Calidad: {' '.join(quality_notes)}")
    parts.append(f"Por qué: risk_score={risk_score} -> priority_level={priority_level} (score de reglas {draft.score}/100, modelo {model_version}).")
    return " ".join(parts)
