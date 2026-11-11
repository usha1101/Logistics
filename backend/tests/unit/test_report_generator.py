from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from app.models.report import ReportStatus, ReportType
from app.schemas.report import ReportGenerateRequest
from app.services.analytics import InvalidDateRangeError, ReportNotFoundError
from app.services.reports import (
    PDFReportBuilder,
    generate_pdf_report,
    get_report_by_id,
    get_report_types_catalog,
    list_reports,
    resolve_safe_report_path,
    sanitize_filename,
)


def test_sanitize_filename_removes_unsafe_characters():
    assert sanitize_filename("../../etc/passwd") == "etc_passwd.pdf"
    assert sanitize_filename("my report #1!!.pdf") == "my_report_1_.pdf"
    assert sanitize_filename("...") == "logipulse_report.pdf"


def test_resolve_safe_report_path_blocks_traversal():
    with pytest.raises(ReportNotFoundError):
        resolve_safe_report_path("../secret.pdf")
    with pytest.raises(ReportNotFoundError):
        resolve_safe_report_path("subdir/report.pdf")
    with pytest.raises(ReportNotFoundError):
        resolve_safe_report_path("..\\secret.pdf")

    valid_path = resolve_safe_report_path("RPT-20261111-TEST.pdf")
    assert valid_path.name == "RPT-20261111-TEST.pdf"


def test_report_types_catalog_contains_all_seven_types():
    catalog = get_report_types_catalog()
    assert catalog.total == 7
    returned_types = {t.report_type for t in catalog.report_types}
    expected_types = {rt.value for rt in ReportType}
    assert returned_types == expected_types


def test_pdf_report_builder_renders_valid_pdf_bytes():
    builder = PDFReportBuilder(
        title="Unit Test Report",
        report_code="RPT-UNIT-001",
        report_type=ReportType.EXECUTIVE_SUMMARY.value,
        generated_at=datetime.now(timezone.utc),
        filter_summary={"data_scope": "OPERATIONAL"},
    )
    builder.add_section_heading("Summary KPIs")
    builder.add_paragraph("Testing PDF generation with ReportLab.")
    builder.add_kpi_table(["KPI", "Value"], [["Orders", 10], ["Delay", None]])
    builder.add_bar_chart("Sample Bar Chart", ["DELIVERED", "IN_TRANSIT"], [8.0, 2.0])
    builder.add_bar_chart("Empty Bar Chart", ["A", "B"], [0.0, 0.0])
    builder.add_notes_section(["Sample note"], ["average_delivery_duration_minutes"])

    pdf_bytes = builder.build_pdf_bytes()
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


@pytest.mark.parametrize("report_type", list(ReportType))
def test_generate_all_seven_report_types(db_session: Session, report_type: ReportType):
    req = ReportGenerateRequest(
        report_type=report_type,
        title=f"Automated {report_type.value} Report",
        include_simulations=True,
    )
    meta = generate_pdf_report(db=db_session, req=req, user_id=None)
    assert meta.id is not None
    assert meta.report_type == report_type.value
    assert meta.status == ReportStatus.COMPLETED.value
    assert meta.file_reference is not None
    assert meta.file_size is not None and meta.file_size > 500

    pdf_path = resolve_safe_report_path(meta.file_reference)
    assert pdf_path.exists()
    content = pdf_path.read_bytes()
    assert content.startswith(b"%PDF")


def test_list_and_get_reports_service(db_session: Session):
    req = ReportGenerateRequest(report_type=ReportType.EXECUTIVE_SUMMARY)
    created = generate_pdf_report(db=db_session, req=req)

    items, total = list_reports(
        db=db_session,
        skip=0,
        limit=10,
        report_type=ReportType.EXECUTIVE_SUMMARY.value,
        status=ReportStatus.COMPLETED.value,
    )
    assert total >= 1
    assert any(r.id == created.id for r in items)

    fetched = get_report_by_id(db=db_session, report_id=created.id)
    assert fetched.report_code == created.report_code

    with pytest.raises(ReportNotFoundError):
        get_report_by_id(db=db_session, report_id="non-existent-report-id")
