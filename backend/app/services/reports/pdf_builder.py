from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Sequence, Tuple

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class NumberedReportCanvas(canvas.Canvas):
    """Custom ReportLab canvas that renders headers and 'Page X of Y' footers."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: List[Dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def _draw_page_decorations(self, page_count: int) -> None:
        self.saveState()
        width, height = A4
        # Top banner bar
        self.setStrokeColor(colors.HexColor("#1E3A8A"))
        self.setLineWidth(1.5)
        self.line(18 * mm, height - 15 * mm, width - 18 * mm, height - 15 * mm)

        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#1E3A8A"))
        self.drawString(18 * mm, height - 13 * mm, "LOGIPULSE — AI LOGISTICS CONTROL TOWER & DIGITAL TWIN")

        # Bottom footer
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)

        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#475569"))
        self.drawString(
            18 * mm,
            10 * mm,
            "Confidential Operational Analytics Report — Computed from Actual Database Records",
        )
        page_label = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(width - 18 * mm, 10 * mm, page_label)
        self.restoreState()


class PDFReportBuilder:
    """Helper class to assemble structured ReportLab PDF documents."""

    def __init__(
        self,
        title: str,
        report_code: str,
        report_type: str,
        generated_at: datetime,
        filter_summary: Dict[str, Any],
    ) -> None:
        self.title = title
        self.report_code = report_code
        self.report_type = report_type
        self.generated_at = generated_at
        self.filter_summary = filter_summary
        self.styles = getSampleStyleSheet()
        self._init_custom_styles()
        self.elements: List[Any] = []
        self._add_cover_header()

    def _init_custom_styles(self) -> None:
        self.title_style = ParagraphStyle(
            "ReportTitle",
            parent=self.styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=6,
        )
        self.subtitle_style = ParagraphStyle(
            "ReportSubtitle",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#475569"),
            spaceAfter=10,
        )
        self.section_style = ParagraphStyle(
            "SectionHeading",
            parent=self.styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#1E3A8A"),
            spaceBefore=12,
            spaceAfter=6,
        )
        self.body_style = ParagraphStyle(
            "ReportBody",
            parent=self.styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#1E293B"),
            spaceAfter=6,
        )
        self.note_style = ParagraphStyle(
            "ReportNote",
            parent=self.styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#334155"),
            spaceAfter=4,
        )

    def _add_cover_header(self) -> None:
        self.elements.append(Paragraph(self.title, self.title_style))
        meta_parts = [
            f"<b>Report Code:</b> {self.report_code}",
            f"<b>Type:</b> {self.report_type}",
            f"<b>Generated At (UTC):</b> {self.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"<b>Data Scope:</b> {self.filter_summary.get('data_scope', 'OPERATIONAL')}",
        ]
        if self.filter_summary.get("start_date"):
            meta_parts.append(f"<b>Start Date:</b> {self.filter_summary['start_date']}")
        if self.filter_summary.get("end_date"):
            meta_parts.append(f"<b>End Date:</b> {self.filter_summary['end_date']}")
        if self.filter_summary.get("simulation_id"):
            meta_parts.append(f"<b>Simulation ID:</b> {self.filter_summary['simulation_id']}")

        self.elements.append(Paragraph(" &nbsp;|&nbsp; ".join(meta_parts), self.subtitle_style))
        self.elements.append(Spacer(1, 4 * mm))

    def add_section_heading(self, heading: str) -> None:
        self.elements.append(Paragraph(heading, self.section_style))

    def add_paragraph(self, text: str) -> None:
        self.elements.append(Paragraph(text, self.body_style))

    def add_kpi_table(
        self,
        headers: Sequence[str],
        rows: Sequence[Sequence[Any]],
        col_widths: Optional[Sequence[float]] = None,
    ) -> None:
        data = [list(headers)] + [[str(cell) if cell is not None else "N/A (Unavailable)" for cell in row] for row in rows]
        table = Table(data, colWidths=col_widths, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                    ("TOPPADDING", (0, 0), (-1, 0), 6),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), 8.5),
                    ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#0F172A")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        self.elements.append(table)
        self.elements.append(Spacer(1, 4 * mm))

    def add_bar_chart(
        self,
        chart_title: str,
        categories: List[str],
        values: List[float],
    ) -> None:
        drawing = Drawing(450, 165)
        drawing.add(
            Rect(0, 0, 450, 165, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#CBD5E1"))
        )
        drawing.add(
            String(15, 148, chart_title, fontName="Helvetica-Bold", fontSize=10, fillColor=colors.HexColor("#1E3A8A"))
        )

        if not categories or not values or all(v == 0 for v in values):
            drawing.add(
                String(
                    15,
                    80,
                    "No non-zero records available in this scope to plot bar chart.",
                    fontName="Helvetica-Oblique",
                    fontSize=9,
                    fillColor=colors.HexColor("#64748B"),
                )
            )
            self.elements.append(drawing)
            self.elements.append(Spacer(1, 4 * mm))
            return

        bc = VerticalBarChart()
        bc.x = 45
        bc.y = 28
        bc.height = 105
        bc.width = 380
        bc.data = [values]
        bc.strokeColor = colors.HexColor("#CBD5E1")
        bc.valueAxis.valueMin = 0
        max_val = max(values)
        bc.valueAxis.valueMax = max_val * 1.2 if max_val > 0 else 10
        bc.valueAxis.valueStep = max(1, round((max_val * 1.2) / 4, 1)) if max_val > 0 else 2
        bc.categoryAxis.labels.boxAnchor = "ne"
        bc.categoryAxis.labels.dx = 0
        bc.categoryAxis.labels.dy = -2
        bc.categoryAxis.labels.angle = 15
        bc.categoryAxis.labels.fontName = "Helvetica"
        bc.categoryAxis.labels.fontSize = 7.5
        bc.categoryAxis.categoryNames = [c[:18] for c in categories]
        bc.bars[0].fillColor = colors.HexColor("#2563EB")
        drawing.add(bc)

        self.elements.append(drawing)
        self.elements.append(Spacer(1, 4 * mm))

    def add_notes_section(self, notes: Sequence[str], unavailable_metrics: Sequence[str]) -> None:
        self.add_section_heading("Data Integrity, Estimations & Limitations")
        self.add_paragraph(
            "All metrics in this report are computed directly from persisted LOGIPULSE database records. "
            "No operational or historical values are fabricated."
        )
        for note in notes:
            self.elements.append(Paragraph(f"• {note}", self.note_style))
        if unavailable_metrics:
            unavail_str = ", ".join(sorted(set(unavailable_metrics)))
            self.elements.append(
                Paragraph(
                    f"• <b>Unavailable Metrics (insufficient persisted records):</b> {unavail_str}",
                    self.note_style,
                )
            )
        else:
            self.elements.append(
                Paragraph(
                    "• All primary domain metrics had sufficient persisted records for calculation.",
                    self.note_style,
                )
            )

    def build_pdf_bytes(self) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=22 * mm,
            bottomMargin=22 * mm,
            title=self.title,
            author="LOGIPULSE Control Tower",
        )
        doc.build(self.elements, canvasmaker=NumberedReportCanvas)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

