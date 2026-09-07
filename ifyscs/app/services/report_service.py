import io
from datetime import date

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart

from app.services import progress_service

NAVY = colors.HexColor("#1A2744")
GOLD = colors.HexColor("#C9952A")


def build_progress_report_pdf(projects):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.8 * inch, bottomMargin=0.8 * inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ReportTitle", parent=styles["Title"], textColor=NAVY)
    sub_style = ParagraphStyle("ReportSub", parent=styles["Normal"], textColor=colors.HexColor("#8C909A"))

    story = [
        Paragraph("Scholaris Department Progress Report", title_style),
        Paragraph(f"Generated {date.today().strftime('%B %d, %Y')}", sub_style),
        Spacer(1, 0.3 * inch),
    ]

    rows = []
    for p in projects:
        rows.append({
            "student": p.student.full_name,
            "supervisor": p.supervisor.full_name,
            "stage": p.current_stage,
            "percent": progress_service.project_progress_percent(p),
        })
    rows.sort(key=lambda r: r["student"])

    if rows:
        chart_drawing = Drawing(440, 200)
        chart = VerticalBarChart()
        chart.x, chart.y = 30, 20
        chart.width, chart.height = 380, 160
        chart.data = [[r["percent"] for r in rows]]
        chart.categoryAxis.categoryNames = [r["student"].split(" ")[0] for r in rows]
        chart.categoryAxis.labels.angle = 30
        chart.categoryAxis.labels.fontSize = 7
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = 100
        chart.bars[0].fillColor = GOLD
        chart_drawing.add(chart)
        story.append(Paragraph("Completion by student (%)", styles["Heading3"]))
        story.append(chart_drawing)
        story.append(Spacer(1, 0.3 * inch))

    table_data = [["Student", "Supervisor", "Current Stage", "Progress"]]
    for r in rows:
        table_data.append([r["student"], r["supervisor"], r["stage"], f"{r['percent']}%"])

    table = Table(table_data, colWidths=[150, 150, 110, 60])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F1EA")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(Paragraph("Department Roster", styles["Heading3"]))
    story.append(table)

    doc.build(story)
    return buffer.getvalue()
