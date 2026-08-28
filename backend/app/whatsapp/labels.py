from __future__ import annotations

LEVEL_LABELS = {
    "CRITICO": "Crítico",
    "ALTO": "Alto",
    "MEDIO": "Medio",
    "BAJO": "Bajo",
    "DESCARTADO": "Descartado",
}
PRIORITY_LABELS = {
    "CRITICAL": "Crítica",
    "HIGH": "Alta",
    "MEDIUM": "Media",
    "LOW": "Baja",
}
VARIABLE_LABELS = {
    "heart_rate": "Frecuencia cardíaca",
    "HR": "Frecuencia cardíaca",
    "spo2": "Saturación de oxígeno",
    "SpO2": "Saturación de oxígeno",
    "resp_rate": "Frecuencia respiratoria",
    "RR": "Frecuencia respiratoria",
    "sbp": "Presión sistólica",
    "SBP": "Presión sistólica",
    "dbp": "Presión diastólica",
    "DBP": "Presión diastólica",
    "temp": "Temperatura",
    "TEMP": "Temperatura",
    "LAB_A": "Marcador de laboratorio A",
    "LAB_B": "Marcador de laboratorio B",
    "LAB_C": "Marcador de laboratorio C",
    "LAB_D": "Marcador de laboratorio D",
}
PATTERN_LABELS = {
    "PROGRESSIVE_MULTISOURCE": "Tendencia progresiva en múltiples fuentes",
    "EARLY_SIGNAL": "Señal temprana",
    "TRANSIENT": "Cambio transitorio",
    "CONTEXTUAL": "Cambio asociado al contexto",
    "STABLE": "Comportamiento estable",
}


def clinical_label(value: object) -> str:
    text = str(value or "")
    return (
        LEVEL_LABELS.get(text)
        or PRIORITY_LABELS.get(text)
        or VARIABLE_LABELS.get(text)
        or PATTERN_LABELS.get(text)
        or text.replace("_", " ").strip().capitalize()
    )


def semaphore(level: str) -> str:
    return {
        "CRITICO": "🔴",
        "ALTO": "🟠",
        "MEDIO": "🟡",
        "BAJO": "🟢",
        "DESCARTADO": "⚪",
    }.get(level, "🔵")
