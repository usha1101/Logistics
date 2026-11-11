import pytest
import networkx as nx

from app.models.network import NetworkEdge, NetworkNode, NodeType
from app.services.network_graph_service import (
    InvalidWeightError,
    NetworkGraphService,
    NodeNotFoundError,
    PathNotFoundError,
)


@pytest.fixture
def sample_nodes():
    return [
        NetworkNode(
            id="node-1",
            name="Whitefield Hub",
            node_type=NodeType.WAREHOUSE.value,
            latitude=12.9698,
            longitude=77.7499,
            region="East",
            address="Whitefield",
            is_active=True,
        ),
        NetworkNode(
            id="node-2",
            name="Electronic City Hub",
            node_type=NodeType.WAREHOUSE.value,
            latitude=12.8399,
            longitude=77.6770,
            region="South",
            address="E-City",
            is_active=True,
        ),
        NetworkNode(
            id="node-3",
            name="Koramangala Customer",
            node_type=NodeType.CUSTOMER.value,
            latitude=12.9352,
            longitude=77.6245,
            region="South",
            address="Koramangala",
            is_active=True,
        ),
        NetworkNode(
            id="node-4",
            name="HSR Layout Customer",
            node_type=NodeType.CUSTOMER.value,
            latitude=12.9121,
            longitude=77.6446,
            region="South-East",
            address="HSR",
            is_active=True,
        ),
        NetworkNode(
            id="node-isolated",
            name="Isolated Depot",
            node_type=NodeType.CUSTOMER.value,
            latitude=13.0500,
            longitude=77.5500,
            region="North",
            address="Isolated",
            is_active=True,
        ),
        NetworkNode(
            id="node-inactive",
            name="Inactive Hub",
            node_type=NodeType.WAREHOUSE.value,
            latitude=12.9000,
            longitude=77.6000,
            region="South",
            address="Inactive",
            is_active=False,
        ),
    ]


@pytest.fixture
def sample_edges():
    return [
        # node-1 -> node-2 (Trunk bidirectional)
        NetworkEdge(
            id="edge-1-2",
            source_node_id="node-1",
            target_node_id="node-2",
            distance_km=25.0,
            estimated_travel_minutes=50,
            road_type="HIGHWAY",
            is_active=True,
        ),
        NetworkEdge(
            id="edge-2-1",
            source_node_id="node-2",
            target_node_id="node-1",
            distance_km=25.0,
            estimated_travel_minutes=50,
            road_type="HIGHWAY",
            is_active=True,
        ),
        # node-2 -> node-3
        NetworkEdge(
            id="edge-2-3",
            source_node_id="node-2",
            target_node_id="node-3",
            distance_km=14.0,
            estimated_travel_minutes=30,
            road_type="PRIMARY",
            is_active=True,
        ),
        # node-3 -> node-4
        NetworkEdge(
            id="edge-3-4",
            source_node_id="node-3",
            target_node_id="node-4",
            distance_km=4.0,
            estimated_travel_minutes=10,
            road_type="ARTERIAL",
            is_active=True,
        ),
        # node-1 -> node-4 (Alternative path, longer distance but faster speed for testing weight differences)
        NetworkEdge(
            id="edge-1-4",
            source_node_id="node-1",
            target_node_id="node-4",
            distance_km=42.0,
            estimated_travel_minutes=35,
            road_type="EXPRESSWAY",
            is_active=True,
        ),
        # Inactive edge
        NetworkEdge(
            id="edge-inactive",
            source_node_id="node-1",
            target_node_id="node-3",
            distance_km=15.0,
            estimated_travel_minutes=25,
            road_type="SECONDARY",
            is_active=False,
        ),
    ]


def test_build_digraph_preserves_attributes(sample_nodes, sample_edges):
    G = NetworkGraphService.build_digraph(sample_nodes, sample_edges, only_active=True)
    assert isinstance(G, nx.DiGraph)
    # node-inactive should be excluded
    assert "node-inactive" not in G
    assert "node-1" in G
    assert G.nodes["node-1"]["name"] == "Whitefield Hub"
    assert G.nodes["node-1"]["node_type"] == NodeType.WAREHOUSE.value

    # Check edge attributes
    assert G.has_edge("node-1", "node-2")
    edge_data = G.get_edge_data("node-1", "node-2")
    assert edge_data["distance_km"] == 25.0
    assert edge_data["estimated_travel_minutes"] == 50
    assert edge_data["road_type"] == "HIGHWAY"
    assert edge_data["distance"] == 25.0
    assert edge_data["travel_time"] == 50.0


def test_build_digraph_skips_invalid_endpoints(sample_nodes):
    invalid_edges = [
        NetworkEdge(
            id="edge-bad",
            source_node_id="node-1",
            target_node_id="nonexistent-target",
            distance_km=10.0,
            estimated_travel_minutes=20,
            is_active=True,
        )
    ]
    G = NetworkGraphService.build_digraph(sample_nodes, invalid_edges, only_active=True)
    assert not G.has_edge("node-1", "nonexistent-target")


def test_build_digraph_only_active_filtering(sample_nodes, sample_edges):
    active_g = NetworkGraphService.build_digraph(sample_nodes, sample_edges, only_active=True)
    all_g = NetworkGraphService.build_digraph(sample_nodes, sample_edges, only_active=False)

    assert "node-inactive" not in active_g
    assert "node-inactive" in all_g
    assert not active_g.has_edge("node-1", "node-3")  # edge-inactive
    assert all_g.has_edge("node-1", "node-3")


def test_build_undirected_graph(sample_nodes, sample_edges):
    G = NetworkGraphService.build_undirected_graph(sample_nodes, sample_edges, only_active=True)
    assert isinstance(G, nx.Graph)
    assert G.has_edge("node-3", "node-2")  # undirected edge navigable in both directions


def test_dijkstra_shortest_path_distance(sample_nodes, sample_edges):
    result = NetworkGraphService.calculate_shortest_path(
        nodes=sample_nodes,
        edges=sample_edges,
        origin_node_id="node-1",
        destination_node_id="node-4",
        weight="distance",
        directed=True,
        only_active=True,
    )

    # Path 1: node-1 -> node-4 is 42.0 km
    # Path 2: node-1 -> node-2 -> node-3 -> node-4 is 25.0 + 14.0 + 4.0 = 43.0 km
    # Therefore, shortest path by distance is node-1 -> node-4 (42.0 km)
    assert result.ordered_node_ids == ["node-1", "node-4"]
    assert result.total_distance_km == 42.0
    assert result.estimated_travel_minutes == 35.0
    assert result.algorithm == "Dijkstra"
    assert len(result.edges) == 1
    assert result.edges[0].id == "edge-1-4"
    assert len(result.coordinates) == 2
    assert result.coordinates[0] == [77.7499, 12.9698]


def test_dijkstra_shortest_path_travel_time(sample_nodes, sample_edges):
    # Shortest path by travel_time:
    # Path 1: node-1 -> node-4 is 35 minutes
    # Path 2: node-1 -> node-2 -> node-3 -> node-4 is 50 + 30 + 10 = 90 minutes
    # Path 1 is faster (35 mins)
    result = NetworkGraphService.calculate_shortest_path(
        nodes=sample_nodes,
        edges=sample_edges,
        origin_node_id="node-1",
        destination_node_id="node-4",
        weight="travel_time",
        directed=True,
        only_active=True,
    )
    assert result.ordered_node_ids == ["node-1", "node-4"]
    assert result.estimated_travel_minutes == 35.0


def test_dijkstra_same_origin_and_destination(sample_nodes, sample_edges):
    result = NetworkGraphService.calculate_shortest_path(
        nodes=sample_nodes,
        edges=sample_edges,
        origin_node_id="node-2",
        destination_node_id="node-2",
        weight="distance",
    )
    assert result.ordered_node_ids == ["node-2"]
    assert result.total_distance_km == 0.0
    assert result.estimated_travel_minutes == 0.0
    assert len(result.edges) == 0


def test_dijkstra_nonexistent_origin_raises_node_not_found(sample_nodes, sample_edges):
    with pytest.raises(NodeNotFoundError) as exc_info:
        NetworkGraphService.calculate_shortest_path(
            nodes=sample_nodes,
            edges=sample_edges,
            origin_node_id="nonexistent-id",
            destination_node_id="node-1",
        )
    assert "Origin node" in str(exc_info.value)


def test_dijkstra_nonexistent_destination_raises_node_not_found(sample_nodes, sample_edges):
    with pytest.raises(NodeNotFoundError) as exc_info:
        NetworkGraphService.calculate_shortest_path(
            nodes=sample_nodes,
            edges=sample_edges,
            origin_node_id="node-1",
            destination_node_id="nonexistent-id",
        )
    assert "Destination node" in str(exc_info.value)


def test_dijkstra_disconnected_nodes_raises_path_not_found(sample_nodes, sample_edges):
    with pytest.raises(PathNotFoundError) as exc_info:
        NetworkGraphService.calculate_shortest_path(
            nodes=sample_nodes,
            edges=sample_edges,
            origin_node_id="node-1",
            destination_node_id="node-isolated",
        )
    assert "No navigable path exists" in str(exc_info.value)


def test_dijkstra_directed_versus_undirected(sample_nodes, sample_edges):
    # In directed graph: edge is node-2 -> node-3. So node-3 cannot reach node-2.
    with pytest.raises(PathNotFoundError):
        NetworkGraphService.calculate_shortest_path(
            nodes=sample_nodes,
            edges=sample_edges,
            origin_node_id="node-3",
            destination_node_id="node-2",
            directed=True,
        )

    # In undirected graph: node-3 can reach node-2 along undirected connection
    result = NetworkGraphService.calculate_shortest_path(
        nodes=sample_nodes,
        edges=sample_edges,
        origin_node_id="node-3",
        destination_node_id="node-2",
        directed=False,
    )
    assert result.ordered_node_ids == ["node-3", "node-2"]
    assert result.total_distance_km == 14.0


def test_network_validation_detects_isolated_nodes(sample_nodes, sample_edges):
    val = NetworkGraphService.validate_network(sample_nodes, sample_edges)
    assert "node-isolated" in val.isolated_nodes
    assert val.warning_count > 0


def test_network_validation_detects_invalid_references(sample_nodes):
    bad_edges = [
        NetworkEdge(
            id="edge-phantom",
            source_node_id="node-1",
            target_node_id="ghost-node",
            distance_km=10.0,
            estimated_travel_minutes=15,
            is_active=True,
        )
    ]
    val = NetworkGraphService.validate_network(sample_nodes, bad_edges)
    assert val.is_valid is False
    assert val.validation_status == "INVALID"
    assert "edge-phantom" in val.invalid_edge_references


def test_network_validation_detects_invalid_coordinates():
    # Bypass model init validation via internal dictionary to simulate corrupted DB rows
    node = NetworkNode(
        id="node-bad-coord",
        name="North Pole Beyond",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.0,
        longitude=77.0,
        is_active=True,
    )
    node.__dict__["latitude"] = 150.0  # Corrupted out-of-bounds latitude

    val = NetworkGraphService.validate_network([node], [])
    assert val.is_valid is False
    assert any(e.category == "COORDINATES" for e in val.errors)




def test_network_analytics_calculated(sample_nodes, sample_edges):
    analytics = NetworkGraphService.calculate_analytics(sample_nodes, sample_edges, only_active=True)
    # Active nodes: 5 (node-1, node-2, node-3, node-4, node-isolated)
    assert analytics.total_nodes == 5
    assert analytics.warehouse_nodes == 2
    assert analytics.customer_nodes == 3
    assert analytics.total_edges == 5  # 5 active edges
    assert analytics.isolated_nodes == 1
    assert "node-isolated" in analytics.isolated_node_ids
    assert analytics.network_connectivity_status == "DISCONNECTED"
    assert analytics.total_network_distance_km == 25.0 + 25.0 + 14.0 + 4.0 + 42.0
    assert analytics.graph_density > 0


def test_network_analytics_empty_network():
    analytics = NetworkGraphService.calculate_analytics([], [])
    assert analytics.total_nodes == 0
    assert analytics.total_edges == 0
    assert analytics.graph_density == 0.0
    assert analytics.average_edge_distance_km is None
    assert analytics.network_connectivity_status == "DISCONNECTED"


def test_node_connections_inspection(sample_nodes, sample_edges):
    conn = NetworkGraphService.get_node_connections(sample_nodes, sample_edges, "node-2", only_active=True)
    assert conn.node_id == "node-2"
    # node-2 has outgoing to node-1, node-3 (2 outgoing)
    # node-2 has incoming from node-1 (1 incoming)
    assert conn.out_degree == 2
    assert conn.in_degree == 1
    assert conn.total_degree == 3

    # node-1 is bidirectional with node-2
    node1_detail = next(cn for cn in conn.connected_nodes if cn.id == "node-1")
    assert node1_detail.direction == "BIDIRECTIONAL"

    # node-3 is outgoing only from node-2
    node3_detail = next(cn for cn in conn.connected_nodes if cn.id == "node-3")
    assert node3_detail.direction == "OUTGOING"


def test_get_components_breakdown(sample_nodes, sample_edges):
    comp_resp = NetworkGraphService.get_components(sample_nodes, sample_edges, only_active=True)
    # One main component with 4 nodes, one isolated component with node-isolated
    assert comp_resp.total_components == 2
    assert comp_resp.is_connected is False
    assert comp_resp.components[0].node_count == 4
    assert comp_resp.components[1].node_count == 1


def test_geojson_generation_points_and_linestrings(sample_nodes, sample_edges):
    # All features
    fc_all = NetworkGraphService.generate_geojson(sample_nodes, sample_edges, feature_type="all", only_active=True)
    assert fc_all.type == "FeatureCollection"
    # 5 active nodes + 5 active edges = 10 features
    assert len(fc_all.features) == 10

    # Nodes only
    fc_nodes = NetworkGraphService.generate_geojson(sample_nodes, sample_edges, feature_type="nodes", only_active=True)
    assert len(fc_nodes.features) == 5
    assert all(f.geometry.type == "Point" for f in fc_nodes.features)
    assert fc_nodes.features[0].geometry.coordinates == [77.7499, 12.9698]

    # Edges only
    fc_edges = NetworkGraphService.generate_geojson(sample_nodes, sample_edges, feature_type="edges", only_active=True)
    assert len(fc_edges.features) == 5
    assert all(f.geometry.type == "LineString" for f in fc_edges.features)
    assert len(fc_edges.features[0].geometry.coordinates) == 2  # [[lon1, lat1], [lon2, lat2]]
