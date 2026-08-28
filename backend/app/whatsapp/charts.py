from __future__ import annotations

from io import BytesIO
from typing import Any

from app.whatsapp.labels import clinical_label

LEVEL_COLORS = {
    "CRITICO": "#d03b3b",
    "ALTO": "#ec835a",
    "MEDIO": "#fab219",
    "BAJO": "#64748b",
    "DESCARTADO": "#0ca30c",
}
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#4a3aa7"]


def response_charts(response: dict[str, Any], limit: int = 2) -> list[dict[str, Any]]:
    charts = [chart for chart in response.get("charts") or [] if chart.get("data")]
    for widget in (response.get("risa_ui") or {}).get("widgets") or []:
        plotly = widget.get("plotly")
        if plotly and plotly.get("data"):
            charts.append(plotly)
    return charts[:limit]


def render_chart_png(spec: dict[str, Any]) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(8, 4.5), dpi=130)
    for index, trace in enumerate(spec.get("data") or []):
        trace_type = trace.get("type") or "scatter"
        x = trace.get("x") or []
        y = trace.get("y") or []
        label = str(trace.get("name") or f"serie {index + 1}")
        color = SERIES_COLORS[index % len(SERIES_COLORS)]
        if trace_type == "bar":
            colors = [LEVEL_COLORS.get(str(value).upper(), color) for value in x]
            axis.bar([clinical_label(value) for value in x], y, label=clinical_label(label), color=colors)
        elif trace_type == "histogram":
            axis.hist(x, bins=min(12, max(3, len(x) // 3)), label=label, color=color)
        else:
            mode = str(trace.get("mode") or "lines")
            if "lines" in mode:
                axis.plot(x, y, label=clinical_label(label), color=color, marker="o" if "markers" in mode else None)
            else:
                axis.scatter(x, y, label=clinical_label(label), color=color)
    layout = spec.get("layout") or {}
    title = layout.get("title") or "RISA Signal"
    if isinstance(title, dict):
        title = title.get("text") or "RISA Signal"
    axis.set_title(str(title))
    axis.set_xlabel(_axis_title(layout.get("xaxis")))
    axis.set_ylabel(_axis_title(layout.get("yaxis")))
    axis.grid(alpha=0.22)
    if len(spec.get("data") or []) > 1:
        axis.legend()
    figure.autofmt_xdate()
    figure.tight_layout()
    output = BytesIO()
    figure.savefig(output, format="png", metadata={"Software": "RISA Signal"})
    plt.close(figure)
    content = output.getvalue()
    if len(content) > 5 * 1024 * 1024:
        raise ValueError("el gráfico supera el límite de 5 MB de WhatsApp")
    return content


def _axis_title(axis: Any) -> str:
    if not isinstance(axis, dict):
        return ""
    title = axis.get("title") or ""
    return str(title.get("text") or "") if isinstance(title, dict) else str(title)
