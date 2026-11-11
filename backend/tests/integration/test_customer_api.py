import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.order import Customer


@pytest.fixture
def customer_setup(db_session: Session):
    c1 = Customer(
        customer_code="CUST-INT-01",
        name="Nexus Logistics India",
        email="ops@nexus.in",
        phone="+91-80-2345-6789",
        address_line="100 Feet Ring Road",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560085",
        latitude=12.92,
        longitude=77.56,
        is_active=True,
    )
    c2 = Customer(
        customer_code="CUST-INT-02",
        name="Metro Fasteners Hub",
        email="supplies@metro.com",
        phone="+91-80-3456-7890",
        address_line="Peenya 1st Stage",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560058",
        latitude=13.02,
        longitude=77.51,
        is_active=False,
    )
    db_session.add_all([c1, c2])
    db_session.commit()
    return {"c1_id": c1.id, "c2_id": c2.id}


def test_list_customers_and_search(client: TestClient, customer_setup, analyst_headers):
    # Unauthenticated rejected
    assert client.get("/api/v1/customers").status_code == 401

    # List all
    res = client.get("/api/v1/customers", headers=analyst_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # Search by name
    res_search = client.get("/api/v1/customers?search=Nexus", headers=analyst_headers)
    assert res_search.status_code == 200
    assert res_search.json()["total"] == 1
    assert res_search.json()["items"][0]["customer_code"] == "CUST-INT-01"

    # Filter active
    res_active = client.get("/api/v1/customers?is_active=false", headers=analyst_headers)
    assert res_active.status_code == 200
    assert res_active.json()["total"] == 1
    assert res_active.json()["items"][0]["customer_code"] == "CUST-INT-02"


def test_create_customer_and_validations(client: TestClient, admin_headers):
    payload = {
        "customer_code": "CUST-NEW-99",
        "name": "Titan Retail",
        "email": "titan@retail.in",
        "phone": "+91-80-9999-8888",
        "address_line": "Outer Ring Road, Bellandur",
        "city": "Bengaluru",
        "state": "Karnataka",
        "postal_code": "560103",
        "latitude": 12.926,
        "longitude": 77.676,
        "is_active": True,
    }
    res = client.post("/api/v1/customers", json=payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["customer_code"] == "CUST-NEW-99"
    assert data["coordinates"] == [77.676, 12.926]

    # Duplicate code rejected
    res_dup = client.post("/api/v1/customers", json=payload, headers=admin_headers)
    assert res_dup.status_code == 409


def test_get_customer_by_id_and_patch(client: TestClient, customer_setup, admin_headers):
    c1_id = customer_setup["c1_id"]
    res = client.get(f"/api/v1/customers/{c1_id}", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["name"] == "Nexus Logistics India"

    # 404 check
    assert client.get("/api/v1/customers/missing-id", headers=admin_headers).status_code == 404

    # Patch
    res_patch = client.patch(
        f"/api/v1/customers/{c1_id}",
        json={"phone": "+91-80-0000-1111", "city": "Bengaluru Urban"},
        headers=admin_headers,
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["phone"] == "+91-80-0000-1111"
    assert res_patch.json()["city"] == "Bengaluru Urban"


def test_customer_rbac_permissions(
    client: TestClient,
    customer_setup,
    admin_headers,
    warehouse_manager_headers,
    fleet_manager_headers,
    analyst_headers,
):
    c1_id = customer_setup["c1_id"]

    # Analyst cannot create (403)
    res_analyst = client.post(
        "/api/v1/customers",
        json={"customer_code": "FORBID-CUST", "name": "Fail", "phone": "123", "address_line": "A", "city": "B", "state": "C", "postal_code": "123", "latitude": 12.0, "longitude": 77.0},
        headers=analyst_headers,
    )
    assert res_analyst.status_code == 403

    # Warehouse manager cannot patch (403)
    res_wh = client.patch(
        f"/api/v1/customers/{c1_id}",
        json={"name": "Hacked"},
        headers=warehouse_manager_headers,
    )
    assert res_wh.status_code == 403

    # Fleet manager cannot patch (403)
    res_fm = client.patch(
        f"/api/v1/customers/{c1_id}",
        json={"name": "Hacked"},
        headers=fleet_manager_headers,
    )
    assert res_fm.status_code == 403


def test_customer_patch_coordinates_and_phone(client: TestClient, customer_setup, admin_headers):
    c1_id = customer_setup["c1_id"]
    res = client.patch(
        f"/api/v1/customers/{c1_id}",
        json={"latitude": 13.05, "longitude": 77.60},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["coordinates"] == [77.60, 13.05]


def test_customer_patch_invalid_email_rejected(client: TestClient, customer_setup, admin_headers):
    c1_id = customer_setup["c1_id"]
    res = client.patch(
        f"/api/v1/customers/{c1_id}",
        json={"email": "invalid-email-not-valid"},
        headers=admin_headers,
    )
    assert res.status_code == 422

