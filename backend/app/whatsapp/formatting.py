from __future__ import annotations

import re
from typing import Any

from app.whatsapp.labels import (
    LEVEL_LABELS,
    PATTERN_LABELS,
    PRIORITY_LABELS,
    VARIABLE_LABELS,
    clinical_label,
    semaphore,
)

_HEADING = re.compile(r"^\s*#{1,6}\s*", re.MULTILINE)
_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_BULLET = re.compile(r"^\s*[-*]\s+", re.MULTILINE)
_INLINE_CODE = re.compile(r"`([^`]+)`")


def clean_whatsapp_text(text: str, limit: int = 1200) -> str:
    value = _CODE_FENCE.sub("", text)
    value = _HEADING.sub("", value)
    value = _BOLD.sub(r"*\1*", value)
    value = _BULLET.sub("• ", value)
    value = _INLINE_CODE.sub(r"\1", value)
    lines = []
    for line in value.splitlines():
        if "|" in line:
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            line = "• " + " · ".join(cell for cell in cells if cell)
        lines.append(line)
    value = "\n".join(lines)
    for raw, label in {
        **LEVEL_LABELS,
        **PRIORITY_LABELS,
        **VARIABLE_LABELS,
        **PATTERN_LABELS,
    }.items():
        value = re.sub(rf"\b{re.escape(raw)}\b", label, value)
    value = re.sub(r"\n{3,}", "\n\n", value).strip()
    if len(value) > limit:
        value = value[: limit - 34].rsplit(" ", 1)[0] + "\n\n• Usa el menú para ver más detalles."
    return value


def alert_summary(patient_id: str, alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return (
            "*Resumen actual*\n"
            "🟢 No hay alertas activas disponibles en este momento.\n\n"
            "_Si presentas síntomas o una emergencia, utiliza los canales de atención habituales._"
        )
    alert = alerts[0]
    level = str(alert.get("level") or "")
    return (
        f"{semaphore(level)} *Alerta {clinical_label(level)}*\n"
        f"• Paciente: {patient_id}\n"
        f"• Prioridad: {clinical_label(alert.get('priority_level'))}\n"
        f"• Hallazgo: {clinical_label(alert.get('pattern'))}\n\n"
        "_Esta información apoya la revisión y no constituye un diagnóstico._"
    )


def alert_detail(alert: dict[str, Any]) -> str:
    evidence = alert.get("evidence") or []
    lines = [
        "*Detalle de la alerta*",
        f"• Nivel: {clinical_label(alert.get('level'))}",
        f"• Prioridad: {clinical_label(alert.get('priority_level'))}",
        f"• Patrón: {clinical_label(alert.get('pattern'))}",
    ]
    for item in evidence[:4]:
        variable = clinical_label(item.get("variable"))
        value = item.get("value")
        unit = item.get("unit") or ""
        lines.append(f"• {variable}: {value} {unit}".rstrip())
    lines.append("\n_Revisa estos datos con el equipo clínico._")
    return "\n".join(lines)


def agent_summary(response: dict[str, Any]) -> str:
    text = clean_whatsapp_text(str(response.get("content") or ""))
    if not text:
        return "No pude generar un resumen. Usa el menú para elegir otra opción."
    return text
