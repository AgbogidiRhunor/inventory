"""
Generates the inventory summary PDF on demand. Nothing is persisted to
disk — the PDF is built entirely in memory and streamed to the client.
"""

import io
from xml.sax.saxutils import escape

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _money(value):
    return f"{settings.CURRENCY_SYMBOL}{value:,.2f}"


def generate_summary_pdf(data):
    """
    `data` is the dict built by views._summary_data():
    products (each with .revenue), total_products, total_available,
    total_sold, total_revenue.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleStyle", parent=styles["Title"], fontSize=20, spaceAfter=4)
    subtitle_style = ParagraphStyle(
        "SubtitleStyle", parent=styles["Normal"], fontSize=10, textColor=colors.grey
    )
    section_style = ParagraphStyle(
        "SectionStyle", parent=styles["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=6
    )
    cell_style = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=9.5, leading=12)

    elements = [Paragraph("Inventory Summary", title_style)]
    generated_str = timezone.localtime().strftime("%d %B %Y, %I:%M %p")
    elements.append(Paragraph(f"Generated: {generated_str}", subtitle_style))
    elements.append(Spacer(1, 10 * mm))

    # --- Totals -------------------------------------------------------
    totals_data = [
        ["Total Products", "Units Available", "Units Sold", "Total Revenue"],
        [
            str(data["total_products"]),
            str(data["total_available"]),
            str(data["total_sold"]),
            _money(data["total_revenue"]),
        ],
    ]
    totals_table = Table(totals_data, colWidths=[45 * mm] * 4)
    totals_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTSIZE", (0, 1), (-1, 1), 14),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 1), (-1, 1), 10),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f3f4f6")),
            ]
        )
    )
    elements.append(totals_table)

    # --- Detail table -------------------------------------------------
    elements.append(Paragraph("Detailed Inventory", section_style))

    table_data = [["Item", "Price", "Available", "Sold", "Revenue"]]
    for p in data["products"]:
        table_data.append(
            [
                Paragraph(escape(p.name), cell_style),
                _money(p.price),
                str(p.quantity),
                str(p.quantity_sold),
                _money(p.revenue),
            ]
        )
    if len(table_data) == 1:
        table_data.append(["No products yet", "-", "-", "-", "-"])

    detail_table = Table(
        table_data,
        colWidths=[62 * mm, 28 * mm, 24 * mm, 20 * mm, 36 * mm],
        repeatRows=1,
    )
    detail_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#374151")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, -1), 9.5),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("ALIGN", (2, 0), (3, -1), "CENTER"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(detail_table)

    elements.append(Spacer(1, 6 * mm))
    elements.append(
        Paragraph(
            "Revenue is the sum of the prices each unit was actually sold for. "
            "Price is the item's initial price.",
            subtitle_style,
        )
    )

    doc.build(elements)
    buffer.seek(0)
    return buffer.read()
