import pytest
from fastapi.testclient import TestClient

from app.models.report import ReportType


def test_get_report_types_endpoint(client: TestClient, analyst_headers: dict):
    res = client.get("/api/v1/reports/types", headers=analyst_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 7
    assert len(data["report_types"]) == 7


@pytest.mark.parametrize("report_type", [rt.value for rt in ReportType])
def test_generate_and_download_all_report_types_via_api(
    client: TestClient, analyst_headers: dict, report_type: str
):
    gen_res = client.post(
        "/api/v1/reports/generate",
        headers=analyst_headers,
        json={
            "report_type": report_type,
            "title": f"Integration Test {report_type}",
            "include_simulations": True,
        },
    )
    assert gen_res.status_code == 201
    meta = gen_res.json()
    assert meta["report_type"] == report_type
    assert meta["status"] == "COMPLETED"
    assert meta["file_size"] > 500
    report_id = meta["id"]

    # Get metadata by ID
    meta_res = client.get(f"/api/v1/reports/{report_id}", headers=analyst_headers)
    assert meta_res.status_code == 200
    assert meta_res.json()["report_code"] == meta["report_code"]

    # Download PDF and verify %PDF magic bytes
    dl_res = client.get(f"/api/v1/reports/{report_id}/download", headers=analyst_headers)
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/pdf"
    assert dl_res.content.startswith(b"%PDF")
    assert len(dl_res.content) == meta["file_size"]


def test_list_reports_pagination_and_filtering(client: TestClient, ops_headers: dict):
    client.post(
        "/api/v1/reports/generate",
        headers=ops_headers,
        json={"report_type": "EXECUTIVE_SUMMARY"},
    )
    client.post(
        "/api/v1/reports/generate",
        headers=ops_headers,
        json={"report_type": "FLEET_PERFORMANCE"},
    )

    list_res = client.get(
        "/api/v1/reports?report_type=EXECUTIVE_SUMMARY&status=COMPLETED&skip=0&limit=10",
        headers=ops_headers,
    )
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["total"] >= 1
    assert all(it["report_type"] == "EXECUTIVE_SUMMARY" for it in data["items"])


def test_report_invalid_date_range_and_not_found(client: TestClient, admin_headers: dict):
    bad_res = client.post(
        "/api/v1/reports/generate",
        headers=admin_headers,
        json={
            "report_type": "EXECUTIVE_SUMMARY",
            "start_date": "2026-12-10T00:00:00Z",
            "end_date": "2026-12-01T00:00:00Z",
        },
    )
    assert bad_res.status_code == 400

    nf_meta = client.get("/api/v1/reports/missing-report-id", headers=admin_headers)
    assert nf_meta.status_code == 404

    nf_dl = client.get("/api/v1/reports/missing-report-id/download", headers=admin_headers)
    assert nf_dl.status_code == 404


def test_reports_rbac_enforcement(
    client: TestClient,
    fleet_manager_headers: dict,
    warehouse_manager_headers: dict,
):
    # Unauthenticated -> 401
    assert client.get("/api/v1/reports").status_code == 401

    # Fleet manager and Warehouse manager are forbidden from generating or listing reports
    for hdrs in (fleet_manager_headers, warehouse_manager_headers):
        assert client.get("/api/v1/reports", headers=hdrs).status_code == 403
        assert client.get("/api/v1/reports/types", headers=hdrs).status_code == 403
        assert (
            client.post(
                "/api/v1/reports/generate",
                headers=hdrs,
                json={"report_type": "EXECUTIVE_SUMMARY"},
            ).status_code
            == 403
        )

