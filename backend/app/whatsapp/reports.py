from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, Any

from app.whatsapp.labels import clinical_label

if TYPE_CHECKING:
    from app.state import AppState


def build_patient_report(app: AppState, patient_id: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Informe RISA {patient_id}",
    )
    styles = getSampleStyleSheet()
    story: list[Any] = [
        Paragraph("Informe de seguimiento RISA", styles["Title"]),
        Paragraph(f"Paciente: {patient_id}", styles["Heading2"]),
        Paragraph(f"Fuente: {app.dataset.origin}", styles["Normal"]),
        Spacer(1, 12),
    ]
    profile = app.dataset.patients
    selected = profile[profile["patient_id"] == patient_id]
    if not selected.empty:
        row = selected.iloc[0].to_dict()
        story.extend(
            [
                Paragraph("Perfil", styles["Heading2"]),
                _table(
                    [
                        ["Edad", row.get("age_years", "—")],
                        ["Grupo de edad", row.get("age_group", "—")],
                        ["Programa", clinical_label(row.get("care_program", "—"))],
                    ],
                    Table,
                    TableStyle,
                    colors,
                ),
                Spacer(1, 12),
            ]
        )
    alerts = app.alerts_for_patient(patient_id)
    story.append(Paragraph("Alertas activas", styles["Heading2"]))
    alert_rows = [["Nivel", "Prioridad", "Hallazgo"]]
    alert_rows.extend(
        [
            [
                clinical_label(alert.get("level")),
                clinical_label(alert.get("priority_level")),
                clinical_label(alert.get("pattern")),
            ]
            for alert in alerts[:5]
        ]
    )
    if len(alert_rows) == 1:
        alert_rows.append(["Sin alertas", "—", "—"])
    story.extend([_table(alert_rows, Table, TableStyle, colors), Spacer(1, 12)])

    vitals = app.dataset.vitals_for(patient_id)
    if not vitals.empty:
        latest = vitals.sort_values("timestamp").iloc[-1].to_dict()
        rows = [["Constante", "Último valor"]]
        for key in ("heart_rate", "spo2", "resp_rate", "sbp", "dbp", "temp"):
            if key in latest and latest[key] is not None:
                rows.append([clinical_label(key), f"{float(latest[key]):.2f}"])
        story.extend(
            [
                Paragraph("Constantes recientes", styles["Heading2"]),
                _table(rows, Table, TableStyle, colors),
                Spacer(1, 12),
            ]
        )

    labs = app.dataset.labs_for(patient_id)
    if not labs.empty:
        rows = [["Laboratorio", "Valor", "Fecha"]]
        for _, item in labs.sort_values("timestamp").tail(8).iterrows():
            rows.append(
                [
                    clinical_label(item.get("analyte")),
                    str(item.get("value", "—")),
                    str(item.get("timestamp", "—"))[:19],
                ]
            )
        story.extend(
            [
                Paragraph("Laboratorios recientes", styles["Heading2"]),
                _table(rows, Table, TableStyle, colors),
                Spacer(1, 12),
            ]
        )

    story.extend(
        [
            Paragraph("Procedencia y límites", styles["Heading2"]),
            Paragraph(
                "Generado desde RISA Data V1.0 y los modelos registrados por el pipeline. "
                "Documento informativo para seguimiento; no constituye diagnóstico, "
                "prescripción ni reemplaza atención de emergencia.",
                styles["Normal"],
            ),
        ]
    )
    document.build(story)
    return output.getvalue()


def _table(rows, table_cls, style_cls, colors):
    table = table_cls(rows, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        style_cls(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9F1FB")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17324D")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C4CE")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
            ]
        )
    )
    return table
