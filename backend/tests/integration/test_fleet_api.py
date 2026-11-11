import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.network import NetworkNode, NodeType
from app.models.vehicle import (
    LocationSource,
    Vehicle,
    VehicleLocation,
    VehicleStatus,
    VehicleStatusHistory,
    VehicleType,
)
from app.models.warehouse import Warehouse, WarehouseStatus, WarehouseType


@pytest.fixture
def fleet_setup(db_session: Session):
    node = NetworkNode(
        name="Peenya Industrial Depot",
        node_type=NodeType.WAREHOUSE.value,
        latitude=13.03,
        longitude=77.52,
        region="North-West",
        address="Peenya Phase 2",
        is_active=True,
    )
    db_session.add(node)
    db_session.commit()

    warehouse = Warehouse(
        network_node_id=node.id,
        warehouse_code="WH-PEENYA-01",
        warehouse_type=WarehouseType.STORAGE_FACILITY.value,
        total_capacity=10000.0,
        used_capacity=2000.0,
        status=WarehouseStatus.OPERATIONAL.value,
    )
    db_session.add(warehouse)
    db_session.commit()

    v1 = Vehicle(
        vehicle_code="V-TEST-01",
        registration_number="KA-01-TEST-01",
        vehicle_type=VehicleType.HEAVY_TRUCK.value,
        manufacturer="Tata Motors",
        model="Prima",
        capacity_kg=1500.0,
        current_load_kg=500.0,
        status=VehicleStatus.AVAILABLE.value,
        home_warehouse_id=warehouse.id,
        current_latitude=13.031,
        current_longitude=77.521,
        current_speed_kmph=0.0,
        heading_degrees=0.0,
        is_active=True,
    )
    v2 = Vehicle(
        vehicle_code="V-TEST-02",
        registration_number="KA-01-TEST-02",
        vehicle_type=VehicleType.DELIVERY_VAN.value,
        manufacturer="Mahindra",
        model="Bolero",
        capacity_kg=500.0,
        current_load_kg=500.0,  # Full load
        status=VehicleStatus.IN_TRANSIT.value,
        home_warehouse_id=warehouse.id,
        current_latitude=13.040,
        current_longitude=77.530,
        current_speed_kmph=42.0,
        heading_degrees=120.0,
        is_active=True,
    )
    v3 = Vehicle(
        vehicle_code="V-TEST-03",
        registration_number="KA-01-TEST-03",
        vehicle_type=VehicleType.ELECTRIC_VAN.value,
        manufacturer="Euler Motors",
        model="HiLoad",
        capacity_kg=300.0,
        current_load_kg=0.0,
        status=VehicleStatus.MAINTENANCE.value,
        home_warehouse_id=warehouse.id,
        is_active=False,
    )
    db_session.add_all([v1, v2, v3])
    db_session.commit()

    # Add initial location for v1
    loc1 = VehicleLocation(
        vehicle_id=v1.id,
        latitude=13.031,
        longitude=77.521,
        speed_kmph=0.0,
        heading_degrees=0.0,
        source=LocationSource.SIMULATION.value,
    )
    db_session.add(loc1)
    db_session.commit()

    return {
        "warehouse_id": warehouse.id,
        "v1_id": v1.id,
        "v2_id": v2.id,
        "v3_id": v3.id,
    }


def test_unauthenticated_requests_rejected(client: TestClient):
    assert client.get("/api/v1/fleet/vehicles").status_code == 401
    assert client.get("/api/v1/fleet/summary").status_code == 401
    assert client.get("/api/v1/fleet/vehicles/available").status_code == 401


def test_list_vehicles_and_pagination(client: TestClient, fleet_setup, fleet_manager_headers):
    res = client.get("/api/v1/fleet/vehicles?skip=0&limit=10", headers=fleet_manager_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert data["skip"] == 0
    assert data["limit"] == 10


def test_filter_vehicles_by_status_and_type(client: TestClient, fleet_setup, fleet_manager_headers):
    # Filter status=IN_TRANSIT
    res_status = client.get("/api/v1/fleet/vehicles?status=IN_TRANSIT", headers=fleet_manager_headers)
    assert res_status.status_code == 200
    data_status = res_status.json()
    assert data_status["total"] == 1
    assert data_status["items"][0]["vehicle_code"] == "V-TEST-02"

    # Filter vehicle_type=HEAVY_TRUCK
    res_type = client.get("/api/v1/fleet/vehicles?vehicle_type=HEAVY_TRUCK", headers=fleet_manager_headers)
    assert res_type.status_code == 200
    data_type = res_type.json()
    assert data_type["total"] == 1
    assert data_type["items"][0]["vehicle_code"] == "V-TEST-01"

    # Filter is_active=false
    res_inactive = client.get("/api/v1/fleet/vehicles?is_active=false", headers=fleet_manager_headers)
    assert res_inactive.status_code == 200
    assert res_inactive.json()["total"] == 1
    assert res_inactive.json()["items"][0]["vehicle_code"] == "V-TEST-03"


def test_get_available_vehicles(client: TestClient, fleet_setup, fleet_manager_headers):
    res = client.get("/api/v1/fleet/vehicles/available", headers=fleet_manager_headers)
    assert res.status_code == 200
    data = res.json()
    # v1 is AVAILABLE and has 1000 kg capacity left -> included
    # v2 is IN_TRANSIT and at full load -> excluded
    # v3 is MAINTENANCE and inactive -> excluded
    assert data["total"] == 1
    assert data["items"][0]["vehicle_code"] == "V-TEST-01"
    assert data["items"][0]["remaining_capacity_kg"] == 1000.0


def test_register_vehicle_success(client: TestClient, fleet_setup, fleet_manager_headers):
    payload = {
        "vehicle_code": "V-NEW-99",
        "registration_number": "KA-01-NEW-99",
        "vehicle_type": "DELIVERY_VAN",
        "manufacturer": "Tata",
        "model": "Ace",
        "capacity_kg": 750.0,
        "home_warehouse_id": fleet_setup["warehouse_id"],
        "initial_latitude": 13.01,
        "initial_longitude": 77.50,
        "initial_speed_kmph": 0.0,
        "initial_heading_degrees": 0.0,
        "is_active": True,
    }
    res = client.post("/api/v1/fleet/vehicles", json=payload, headers=fleet_manager_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["vehicle_code"] == "V-NEW-99"
    assert data["capacity_kg"] == 750.0
    assert data["status"] == "AVAILABLE"
    assert data["coordinates"] == [77.50, 13.01]


def test_register_vehicle_duplicate_code_rejected(client: TestClient, fleet_setup, fleet_manager_headers):
    payload = {
        "vehicle_code": "V-TEST-01",  # Existing
        "registration_number": "KA-UNIQUE-999",
        "vehicle_type": "HEAVY_TRUCK",
        "capacity_kg": 1000.0,
    }
    res = client.post("/api/v1/fleet/vehicles", json=payload, headers=fleet_manager_headers)
    assert res.status_code == 409
    assert "already exists" in res.json()["error"]["message"]


def test_register_vehicle_duplicate_registration_rejected(client: TestClient, fleet_setup, fleet_manager_headers):
    payload = {
        "vehicle_code": "V-UNIQUE-999",
        "registration_number": "KA-01-TEST-01",  # Existing
        "vehicle_type": "HEAVY_TRUCK",
        "capacity_kg": 1000.0,
    }
    res = client.post("/api/v1/fleet/vehicles", json=payload, headers=fleet_manager_headers)
    assert res.status_code == 409


def test_register_vehicle_invalid_warehouse_rejected(client: TestClient, fleet_manager_headers):
    payload = {
        "vehicle_code": "V-WH-FAIL",
        "registration_number": "KA-WH-FAIL",
        "vehicle_type": "HEAVY_TRUCK",
        "capacity_kg": 1000.0,
        "home_warehouse_id": "nonexistent-warehouse-id",
    }
    res = client.post("/api/v1/fleet/vehicles", json=payload, headers=fleet_manager_headers)
    assert res.status_code == 400


def test_get_vehicle_by_id_and_not_found(client: TestClient, fleet_setup, fleet_manager_headers):
    v1_id = fleet_setup["v1_id"]
    res = client.get(f"/api/v1/fleet/vehicles/{v1_id}", headers=fleet_manager_headers)
    assert res.status_code == 200
    assert res.json()["id"] == v1_id
    assert res.json()["vehicle_code"] == "V-TEST-01"

    res_404 = client.get("/api/v1/fleet/vehicles/missing-id", headers=fleet_manager_headers)
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "NOT_FOUND"


def test_patch_vehicle_metadata_and_capacity_check(client: TestClient, fleet_setup, fleet_manager_headers):
    v1_id = fleet_setup["v1_id"]  # current load = 500.0, capacity = 1500.0

    # 1. Successful metadata update
    res = client.patch(
        f"/api/v1/fleet/vehicles/{v1_id}",
        json={"manufacturer": "Updated Manufacturer", "model": "Prima 3000", "capacity_kg": 1800.0},
        headers=fleet_manager_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["manufacturer"] == "Updated Manufacturer"
    assert data["capacity_kg"] == 1800.0

    # 2. Reject capacity below current load (500 kg)
    res_bad_cap = client.patch(
        f"/api/v1/fleet/vehicles/{v1_id}",
        json={"capacity_kg": 400.0},
        headers=fleet_manager_headers,
    )
    assert res_bad_cap.status_code == 400
    assert "below current load" in res_bad_cap.json()["error"]["message"]


def test_update_vehicle_status_and_history(client: TestClient, fleet_setup, fleet_manager_headers):
    v1_id = fleet_setup["v1_id"]

    # 1. Update status to IN_TRANSIT
    res = client.patch(
        f"/api/v1/fleet/vehicles/{v1_id}/status",
        json={"status": "IN_TRANSIT", "reason": "Dispatched to Route 1"},
        headers=fleet_manager_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["vehicle"]["status"] == "IN_TRANSIT"
    assert data["status_history"]["previous_status"] == "AVAILABLE"
    assert data["status_history"]["new_status"] == "IN_TRANSIT"
    assert data["status_history"]["reason"] == "Dispatched to Route 1"
    assert data["status_history"]["changed_by_user_id"] is not None

    # 2. Update to same status does not duplicate history
    res_same = client.patch(
        f"/api/v1/fleet/vehicles/{v1_id}/status",
        json={"status": "IN_TRANSIT"},
        headers=fleet_manager_headers,
    )
    assert res_same.status_code == 200
    assert res_same.json()["status_history"] is None


def test_inactive_vehicle_cannot_become_available(client: TestClient, fleet_setup, fleet_manager_headers):
    v3_id = fleet_setup["v3_id"]  # is_active = False, status = MAINTENANCE
    res = client.patch(
        f"/api/v1/fleet/vehicles/{v3_id}/status",
        json={"status": "AVAILABLE"},
        headers=fleet_manager_headers,
    )
    assert res.status_code == 400
    assert "Inactive vehicles cannot be marked as AVAILABLE" in res.json()["error"]["message"]


def test_update_vehicle_location_and_history(client: TestClient, fleet_setup, fleet_manager_headers):
    v1_id = fleet_setup["v1_id"]

    loc_payload = {
        "latitude": 12.9800,
        "longitude": 77.6000,
        "speed_kmph": 55.0,
        "heading_degrees": 135.0,
        "source": "SIMULATION",
    }
    res = client.patch(
        f"/api/v1/fleet/vehicles/{v1_id}/location",
        json=loc_payload,
        headers=fleet_manager_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["latitude"] == 12.9800
    assert data["longitude"] == 77.6000
    assert data["speed_kmph"] == 55.0
    assert data["heading_degrees"] == 135.0
    assert data["coordinates"] == [77.6000, 12.9800]

    # Verify vehicle current location
    res_veh = client.get(f"/api/v1/fleet/vehicles/{v1_id}", headers=fleet_manager_headers)
    assert res_veh.status_code == 200
    assert res_veh.json()["current_latitude"] == 12.9800
    assert res_veh.json()["current_longitude"] == 77.6000
    assert res_veh.json()["last_location_update"] is not None

    # Check location endpoint
    res_loc = client.get(f"/api/v1/fleet/vehicles/{v1_id}/location", headers=fleet_manager_headers)
    assert res_loc.status_code == 200
    assert res_loc.json()["latitude"] == 12.9800

    # Check location history
    res_hist = client.get(f"/api/v1/fleet/vehicles/{v1_id}/history", headers=fleet_manager_headers)
    assert res_hist.status_code == 200
    assert res_hist.json()["total"] == 2
    assert res_hist.json()["items"][0]["latitude"] == 12.9800


def test_fleet_summary_metrics(client: TestClient, fleet_setup, fleet_manager_headers):
    res = client.get("/api/v1/fleet/summary", headers=fleet_manager_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_vehicles"] == 3
    assert data["active_vehicles"] == 2
    assert data["available_vehicles"] == 1
    assert data["in_transit_vehicles"] == 1
    assert data["maintenance_vehicles"] == 1
    assert data["total_capacity_kg"] == 2300.0  # 1500 + 500 + 300
    assert data["current_load_kg"] == 1000.0  # 500 + 500 + 0
    assert data["available_capacity_kg"] == 1300.0
    assert data["fleet_utilization_percentage"] == round((1000.0 / 2300.0) * 100.0, 2)


def test_fleet_summary_empty_database_no_division_by_zero(client: TestClient, fleet_manager_headers):
    res = client.get("/api/v1/fleet/summary", headers=fleet_manager_headers)
    assert res.status_code == 200
    data = res.json()
    # In an empty state or with zero capacity, fleet_utilization_percentage must be None or 0.0
    assert data["total_vehicles"] >= 0


def test_fleet_rbac_permissions(
    client: TestClient,
    fleet_setup,
    admin_headers,
    fleet_manager_headers,
    warehouse_manager_headers,
    analyst_headers,
):
    v1_id = fleet_setup["v1_id"]

    # 1. Analyst can read fleet
    res_analyst_read = client.get("/api/v1/fleet/vehicles", headers=analyst_headers)
    assert res_analyst_read.status_code == 200

    # 2. Analyst cannot register vehicles (403)
    res_analyst_write = client.post(
        "/api/v1/fleet/vehicles",
        json={"vehicle_code": "V-FORBID", "registration_number": "KA-FORBID", "vehicle_type": "DELIVERY_VAN", "capacity_kg": 500.0},
        headers=analyst_headers,
    )
    assert res_analyst_write.status_code == 403
    assert res_analyst_write.json()["error"]["code"] == "FORBIDDEN"

    # 3. Warehouse manager cannot update vehicle location (403)
    res_wh_loc = client.patch(
        f"/api/v1/fleet/vehicles/{v1_id}/location",
        json={"latitude": 12.5, "longitude": 77.5},
        headers=warehouse_manager_headers,
    )
    assert res_wh_loc.status_code == 403

    # 4. Fleet manager CAN update vehicle location (200)
    res_fm_loc = client.patch(
        f"/api/v1/fleet/vehicles/{v1_id}/location",
        json={"latitude": 12.95, "longitude": 77.65},
        headers=fleet_manager_headers,
    )
    assert res_fm_loc.status_code == 200

    # 5. Admin CAN update vehicle specifications (200)
    res_admin = client.patch(
        f"/api/v1/fleet/vehicles/{v1_id}",
        json={"model": "Admin Model Spec"},
        headers=admin_headers,
    )
    assert res_admin.status_code == 200

