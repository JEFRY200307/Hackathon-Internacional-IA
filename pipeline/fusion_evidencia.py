"""Evidence Fusion (`docs/Negocio.md` 1.4.5): combina evidencia primaria, de
soporte, contextual y de calidad en una representación única por señal — los
cuatro roles que exige el contrato oficial de `evidence.csv`
(`evidence_role`: `PRIMARY | SUPPORTING | CONTEXT | QUALITY`, Documento
Técnico Maestro V2 sección 11).

Este módulo no genera evidencia nueva: etiqueta la que ya produjo
`modelado.score_patient` (`AlertDraft.evidence`, una lista de
`EvidenceItem`) según el patrón detectado, para que `results/evidence.csv`
distinga qué registro *sustenta* la señal de cuál solo la *contextualiza* o
*matiza su confianza*.
"""

from __future__ import annotations

from dataclasses import dataclass

from pipeline.modelado import AlertDraft, EvidenceItem

EVIDENCE_ROLES = ("PRIMARY", "SUPPORTING", "CONTEXT", "QUALITY")


@dataclass
class FusedEvidence:
    item: EvidenceItem
    role: str


def assign_evidence_roles(draft: AlertDraft) -> list[FusedEvidence]:
    """Regla de asignación por patrón (no por variable): el patrón ya codifica
    si la evidencia sustenta, contextualiza o cuestiona la calidad de la señal."""
    pattern = draft.pattern

    if pattern == "LOW_QUALITY":
        return [FusedEvidence(e, "QUALITY") for e in draft.evidence]
    if pattern == "CONTEXTUAL":
        return [FusedEvidence(e, "CONTEXT") for e in draft.evidence]
    if pattern == "MISSING_SOURCE":
        return [FusedEvidence(e, "QUALITY") for e in draft.evidence]

    fused: list[FusedEvidence] = []
    primary_used = False
    for e in draft.evidence:
        if e.source == "laboratory" and "no hay registros" in e.detail.lower():
            fused.append(FusedEvidence(e, "QUALITY"))
        elif not primary_used:
            fused.append(FusedEvidence(e, "PRIMARY"))
            primary_used = True
        else:
            fused.append(FusedEvidence(e, "SUPPORTING"))
    return fused
