from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.network import NetworkEdge, NetworkNode, NodeType
from app.models.user import User, UserRole


def setup_sample_network(db_session: Session):
    wh1 = NetworkNode(
        name="Hub East",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.96,
        longitude=77.74,
        region="East",
        address="Whitefield",
        is_active=True,
    )
    wh2 = NetworkNode(
        name="Hub South Inactive",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.83,
        longitude=77.67,
        region="South",
        address="Electronic City",
        is_active=False,  # Inactive node
    )
    cust1 = NetworkNode(
        name="Cust North",
        node_type=NodeType.CUSTOMER.value,
        latitude=13.03,
        longitude=77.59,
        region="North",
        address="Hebbal",
        is_active=True,
    )
    cust2 = NetworkNode(
        name="Cust East",
        node_type=NodeType.CUSTOMER.value,
        latitude=12.95,
        longitude=77.69,
        region="East",
        address="Marathahalli",
        is_active=True,
    )
    db_session.add_all([wh1, wh2, cust1, cust2])
    db_session.commit()

    edge1 = NetworkEdge(
        source_node_id=wh1.id,
        target_node_id=cust2.id,
        distance_km=8.5,
        estimated_travel_minutes=20,
        road_type="PRIMARY",
        is_active=True,
    )
    edge2 = NetworkEdge(
        source_node_id=wh1.id,
        target_node_id=cust1.id,
        distance_km=18.0,
        estimated_travel_minutes=45,
        road_type="HIGHWAY",
        is_active=False,  # Inactive edge
    )
    db_session.add_all([edge1, edge2])
    db_session.commit()

    return {"wh1": wh1, "wh2": wh2, "cust1": cust1, "cust2": cust2, "edge1": edge1, "edge2": edge2}


def test_unauthenticated_requests_rejected(client: TestClient):
    assert client.get("/api/v1/network/state").status_code == 401
    assert client.get("/api/v1/network/nodes").status_code == 401
    assert client.get("/api/v1/network/edges").status_code == 401


def test_network_state_endpoint_schema_and_counts(
    client: TestClient, db_session: Session, admin_headers: dict
):
    setup_sample_network(db_session)

    response = client.get("/api/v1/network/state", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["simulation_id"] is None
    assert data["data_source"] == "SIMULATED"
    assert "network" in data
    assert "summary" in data

    summary = data["summary"]
    # Only active nodes (3: wh1, cust1, cust2) and active edges (1: edge1)
    assert summary["total_nodes"] == 3
    assert summary["total_warehouses"] == 1
    assert summary["total_customers"] == 2
    assert summary["total_connections"] == 1

    nodes = data["network"]["nodes"]
    assert len(nodes) == 3
    node_names = [n["name"] for n in nodes]
    assert "Hub East" in node_names
    assert "Cust North" in node_names
    assert "Cust East" in node_names
    assert "Hub South Inactive" not in node_names

    # Check GeoJSON-compatible coordinates [longitude, latitude]
    for n in nodes:
        assert len(n["coordinates"]) == 2
        assert n["coordinates"][0] == n["longitude"]
        assert n["coordinates"][1] == n["latitude"]

    edges = data["network"]["edges"]
    assert len(edges) == 1
    assert edges[0]["distance_km"] == 8.5
    assert edges[0]["is_active"] is True


def test_network_state_role_authorization(
    client: TestClient, db_session: Session, analyst_headers: dict
):
    # Analyst is permitted on /network/state
    response = client.get("/api/v1/network/state", headers=analyst_headers)
    assert response.status_code == 200

    # Create a Fleet Manager token
    fleet_user = User(
        username="fleet_test_user",
        email="fleet_test@logipulse.io",
        full_name="Fleet Officer",
        role=UserRole.FLEET_MANAGER.value,
        hashed_password="some_hash_value",
        is_active=True,
    )
    db_session.add(fleet_user)
    db_session.commit()
    fleet_token = create_access_token(fleet_user.id, fleet_user.username, fleet_user.role)

    # Fleet manager should be forbidden from full network twin state
    forbidden_resp = client.get(
        "/api/v1/network/state",
        headers={"Authorization": f"Bearer {fleet_token}"},
    )
    assert forbidden_resp.status_code == 403


def test_list_nodes_and_filtering(
    client: TestClient, db_session: Session, analyst_headers: dict
):
    setup_sample_network(db_session)

    # 1. List all nodes without filters
    res_all = client.get("/api/v1/network/nodes", headers=analyst_headers)
    assert res_all.status_code == 200
    assert res_all.json()["total"] == 4

    # 2. Filter by node_type=WAREHOUSE
    res_wh = client.get("/api/v1/network/nodes?node_type=WAREHOUSE", headers=analyst_headers)
    assert res_wh.status_code == 200
    assert res_wh.json()["total"] == 2
    for n in res_wh.json()["items"]:
        assert n["node_type"] == "WAREHOUSE"

    # 3. Filter by region=East
    res_east = client.get("/api/v1/network/nodes?region=East", headers=analyst_headers)
    assert res_east.status_code == 200
    assert res_east.json()["total"] == 2

    # 4. Filter by is_active=true
    res_active = client.get("/api/v1/network/nodes?is_active=true", headers=analyst_headers)
    assert res_active.status_code == 200
    assert res_active.json()["total"] == 3


def test_node_pagination(client: TestClient, db_session: Session, analyst_headers: dict):
    setup_sample_network(db_session)

    res_page = client.get("/api/v1/network/nodes?skip=1&limit=2", headers=analyst_headers)
    assert res_page.status_code == 200
    data = res_page.json()
    assert data["total"] == 4
    assert data["skip"] == 1
    assert data["limit"] == 2
    assert len(data["items"]) == 2


def test_get_single_node_and_404(
    client: TestClient, db_session: Session, analyst_headers: dict
):
    net = setup_sample_network(db_session)

    # Existing node
    res = client.get(f"/api/v1/network/nodes/{net['wh1'].id}", headers=analyst_headers)
    assert res.status_code == 200
    assert res.json()["name"] == "Hub East"

    # Non-existent node
    res_404 = client.get("/api/v1/network/nodes/non-existent-id-123", headers=analyst_headers)
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "NOT_FOUND"


def test_list_edges_and_single_edge(
    client: TestClient, db_session: Session, analyst_headers: dict
):
    net = setup_sample_network(db_session)

    # 1. List edges
    res = client.get("/api/v1/network/edges", headers=analyst_headers)
    assert res.status_code == 200
    assert res.json()["total"] == 2

    # 2. Filter edges by source_node_id
    res_src = client.get(
        f"/api/v1/network/edges?source_node_id={net['wh1'].id}", headers=analyst_headers
    )
    assert res_src.status_code == 200
    assert res_src.json()["total"] == 2

    # 3. Filter edges by is_active=true
    res_act = client.get("/api/v1/network/edges?is_active=true", headers=analyst_headers)
    assert res_act.status_code == 200
    assert res_act.json()["total"] == 1

    # 4. Get single edge
    res_edge = client.get(f"/api/v1/network/edges/{net['edge1'].id}", headers=analyst_headers)
    assert res_edge.status_code == 200
    assert res_edge.json()["distance_km"] == 8.5

    # 5. Missing edge returns 404
    res_edge_404 = client.get("/api/v1/network/edges/missing-edge-id", headers=analyst_headers)
    assert res_edge_404.status_code == 404
    assert res_edge_404.json()["error"]["code"] == "NOT_FOUND"

