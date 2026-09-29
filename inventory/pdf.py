import io
from datetime import datetime

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def generate_summary_pdf(products):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle", parent=styles["Title"], fontSize=20, spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        "SubtitleStyle", parent=styles["Normal"], fontSize=10, textColor=colors.grey
    )
    section_style = ParagraphStyle(
        "SectionStyle", parent=styles["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=6
    )

    elements = []
    elements.append(Paragraph("Inventory Summary", title_style))
    generated_str = timezone.localtime().strftime("%d %B %Y, %I:%M %p")
    elements.append(Paragraph(f"Generated: {generated_str}", subtitle_style))
    elements.append(Spacer(1, 10 * mm))

    total_products = products.count() if hasattr(products, "count") else len(products)
    total_available = sum(p.quantity for p in products)
    total_sold = sum(p.quantity_sold for p in products)

    totals_data = [
        ["Total Products", "Total Units Available", "Total Units Sold"],
        [str(total_products), str(total_available), str(total_sold)],
    ]
    totals_table = Table(totals_data, colWidths=[55 * mm] * 3)
    totals_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, 1), 16),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 1), (-1, 1), 10),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f3f4f6")),
            ]
        )
    )
    elements.append(totals_table)

    elements.append(Paragraph("Detailed Inventory", section_style))

    table_data = [["Item", "Available", "Sold"]]
    for p in products:
        table_data.append([p.name, str(p.quantity), str(p.quantity_sold)])

    if len(table_data) == 1:
        table_data.append(["No products yet", "-", "-"])

    detail_table = Table(table_data, colWidths=[90 * mm, 40 * mm, 40 * mm], repeatRows=1)
    detail_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#374151")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(detail_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.read()
