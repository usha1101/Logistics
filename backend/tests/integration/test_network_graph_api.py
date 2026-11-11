import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.network import NetworkEdge, NetworkNode, NodeType


@pytest.fixture
def network_setup(db_session: Session):
    # 3 Nodes: 2 Warehouses, 1 Customer
    n1 = NetworkNode(
        id="node-blr-wh1",
        name="Whitefield Distribution Hub",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.9698,
        longitude=77.7499,
        region="East Bengaluru",
        address="Whitefield EPIP",
        is_active=True,
    )
    n2 = NetworkNode(
        id="node-blr-wh2",
        name="Electronic City Distribution Hub",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.8399,
        longitude=77.6770,
        region="South Bengaluru",
        address="E-City Phase 1",
        is_active=True,
    )
    n3 = NetworkNode(
        id="node-blr-cust1",
        name="Koramangala Commercial Hub",
        node_type=NodeType.CUSTOMER.value,
        latitude=12.9352,
        longitude=77.6245,
        region="South Bengaluru",
        address="80 Feet Road",
        is_active=True,
    )
    n4_isolated = NetworkNode(
        id="node-blr-iso",
        name="Yelahanka Isolated Point",
        node_type=NodeType.CUSTOMER.value,
        latitude=13.1000,
        longitude=77.5900,
        region="North Bengaluru",
        address="Yelahanka Old Town",
        is_active=True,
    )

    # 3 Edges: n1 <-> n2 (bidirectional), n2 -> n3
    e1 = NetworkEdge(
        id="edge-wh1-wh2",
        source_node_id="node-blr-wh1",
        target_node_id="node-blr-wh2",
        distance_km=26.5,
        estimated_travel_minutes=55,
        road_type="PRIMARY_ORR",
        is_active=True,
    )
    e2 = NetworkEdge(
        id="edge-wh2-wh1",
        source_node_id="node-blr-wh2",
        target_node_id="node-blr-wh1",
        distance_km=26.5,
        estimated_travel_minutes=55,
        road_type="PRIMARY_ORR",
        is_active=True,
    )
    e3 = NetworkEdge(
        id="edge-wh2-cust1",
        source_node_id="node-blr-wh2",
        target_node_id="node-blr-cust1",
        distance_km=14.0,
        estimated_travel_minutes=34,
        road_type="PRIMARY",
        is_active=True,
    )

    db_session.add_all([n1, n2, n3, n4_isolated, e1, e2, e3])
    db_session.commit()

    return {
        "wh1_id": n1.id,
        "wh2_id": n2.id,
        "cust1_id": n3.id,
        "iso_id": n4_isolated.id,
        "edge1_id": e1.id,
    }


def test_get_graph_overview(client: TestClient, network_setup, ops_headers):
    res = client.get("/api/v1/network/graph", headers=ops_headers)
    assert res.status_code == 200
    data = res.json()
    assert "metadata" in data
    assert "nodes" in data
    assert "edges" in data
    assert data["metadata"]["total_nodes"] == 4
    assert data["metadata"]["total_edges"] == 3
    assert data["metadata"]["warehouse_nodes"] == 2
    assert data["metadata"]["customer_nodes"] == 2
    assert data["is_connected"] is False  # Isolated node exists


def test_get_network_analytics(client: TestClient, network_setup, analyst_headers):
    res = client.get("/api/v1/network/analytics", headers=analyst_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_nodes"] == 4
    assert data["total_edges"] == 3
    assert data["isolated_nodes"] == 1
    assert "node-blr-iso" in data["isolated_node_ids"]
    assert data["network_connectivity_status"] == "DISCONNECTED"
    assert data["total_network_distance_km"] == 26.5 + 26.5 + 14.0
    assert data["average_edge_distance_km"] > 0
    assert data["average_travel_time_minutes"] > 0


def test_validate_network_endpoint(client: TestClient, network_setup, admin_headers):
    res = client.get("/api/v1/network/validate", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is True
    assert data["validation_status"] == "WARNINGS"
    assert "node-blr-iso" in data["isolated_nodes"]
    assert len(data["warnings"]) >= 1


def test_get_geojson_all_features(client: TestClient, network_setup, fleet_headers):
    res = client.get("/api/v1/network/geojson", headers=fleet_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    # 4 nodes + 3 edges = 7 features
    assert len(data["features"]) == 7

    point_features = [f for f in data["features"] if f["geometry"]["type"] == "Point"]
    line_features = [f for f in data["features"] if f["geometry"]["type"] == "LineString"]
    assert len(point_features) == 4
    assert len(line_features) == 3


def test_get_geojson_filtered_nodes_only(client: TestClient, network_setup, warehouse_manager_headers):
    res = client.get("/api/v1/network/geojson?feature_type=nodes", headers=warehouse_manager_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["features"]) == 4
    assert all(f["geometry"]["type"] == "Point" for f in data["features"])


def test_get_geojson_filtered_edges_only(client: TestClient, network_setup, ops_headers):
    res = client.get("/api/v1/network/geojson?feature_type=edges", headers=ops_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["features"]) == 3
    assert all(f["geometry"]["type"] == "LineString" for f in data["features"])


def test_shortest_path_distance_success(client: TestClient, network_setup, analyst_headers):
    # Route: wh1 -> wh2 -> cust1
    res = client.get(
        f"/api/v1/network/shortest-path?origin_node_id={network_setup['wh1_id']}&destination_node_id={network_setup['cust1_id']}&weight=distance",
        headers=analyst_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ordered_node_ids"] == [network_setup["wh1_id"], network_setup["wh2_id"], network_setup["cust1_id"]]
    assert data["total_distance_km"] == 26.5 + 14.0
    assert data["estimated_travel_minutes"] == 55 + 34
    assert len(data["edges"]) == 2
    assert len(data["coordinates"]) == 3
    assert data["coordinates"][0] == [77.7499, 12.9698]


def test_shortest_path_travel_time_success(client: TestClient, network_setup, ops_headers):
    res = client.get(
        f"/api/v1/network/shortest-path?origin_node_id={network_setup['wh1_id']}&destination_node_id={network_setup['cust1_id']}&weight=travel_time",
        headers=ops_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["weight"] == "travel_time"
    assert data["ordered_node_ids"] == [network_setup["wh1_id"], network_setup["wh2_id"], network_setup["cust1_id"]]
    assert data["estimated_travel_minutes"] == 89.0


def test_shortest_path_same_node(client: TestClient, network_setup, admin_headers):
    res = client.get(
        f"/api/v1/network/shortest-path?origin_node_id={network_setup['wh1_id']}&destination_node_id={network_setup['wh1_id']}",
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ordered_node_ids"] == [network_setup["wh1_id"]]
    assert data["total_distance_km"] == 0.0
    assert data["estimated_travel_minutes"] == 0.0


def test_shortest_path_404_invalid_node(client: TestClient, network_setup, admin_headers):
    res = client.get(
        f"/api/v1/network/shortest-path?origin_node_id=invalid-node&destination_node_id={network_setup['wh1_id']}",
        headers=admin_headers,
    )
    assert res.status_code == 404
    error_data = res.json()["error"]
    assert "not found" in error_data["message"].lower()


def test_shortest_path_404_disconnected(client: TestClient, network_setup, admin_headers):
    res = client.get(
        f"/api/v1/network/shortest-path?origin_node_id={network_setup['wh1_id']}&destination_node_id={network_setup['iso_id']}",
        headers=admin_headers,
    )
    assert res.status_code == 404
    error_data = res.json()["error"]
    assert "no navigable path" in error_data["message"].lower()



def test_get_node_connections(client: TestClient, network_setup, fleet_headers):
    res = client.get(f"/api/v1/network/nodes/{network_setup['wh2_id']}/connections", headers=fleet_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["node_id"] == network_setup["wh2_id"]
    assert data["out_degree"] == 2  # to wh1, cust1
    assert data["in_degree"] == 1   # from wh1
    assert data["total_degree"] == 3
    assert len(data["connected_nodes"]) == 2
    assert len(data["connecting_edges"]) == 3


def test_get_node_connections_404(client: TestClient, admin_headers):
    res = client.get("/api/v1/network/nodes/nonexistent-node-id/connections", headers=admin_headers)
    assert res.status_code == 404


def test_get_network_components(client: TestClient, network_setup, warehouse_manager_headers):
    res = client.get("/api/v1/network/components", headers=warehouse_manager_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_components"] == 2
    assert data["is_connected"] is False
    assert len(data["components"]) == 2
    assert data["components"][0]["node_count"] == 3
    assert data["components"][1]["node_count"] == 1


def test_network_graph_rbac_all_roles_permitted(
    client: TestClient,
    network_setup,
    admin_headers,
    ops_headers,
    analyst_headers,
    fleet_headers,
    warehouse_manager_headers,
):
    for headers in [admin_headers, ops_headers, analyst_headers, fleet_headers, warehouse_manager_headers]:
        res = client.get("/api/v1/network/graph", headers=headers)
        assert res.status_code == 200


def test_network_graph_unauthenticated_rejected(client: TestClient):
    assert client.get("/api/v1/network/graph").status_code == 401
    assert client.get("/api/v1/network/analytics").status_code == 401
    assert client.get("/api/v1/network/validate").status_code == 401
    assert client.get("/api/v1/network/geojson").status_code == 401
    assert client.get("/api/v1/network/components").status_code == 401


def test_existing_network_state_preserved(client: TestClient, network_setup, ops_headers):
    res = client.get("/api/v1/network/state", headers=ops_headers)
    assert res.status_code == 200
    data = res.json()
    assert "network" in data
    assert "summary" in data
    assert data["summary"]["total_nodes"] == 4
    assert data["summary"]["total_connections"] == 3


def test_existing_dashboard_summary_preserved(client: TestClient, network_setup, ops_headers):
    res = client.get("/api/v1/dashboard/summary", headers=ops_headers)
    assert res.status_code == 200
    data = res.json()
    assert "network" in data
    assert "operations" in data
    assert data["network"]["total_warehouses"] == 2
