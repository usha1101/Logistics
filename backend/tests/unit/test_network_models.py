import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models.network import NetworkEdge, NetworkNode, NodeType


def test_network_node_creation(db_session: Session):
    node = NetworkNode(
        name="Test Warehouse Hub",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.9716,
        longitude=77.5946,
        address="Central Bengaluru",
        region="Central",
        is_active=True,
    )
    db_session.add(node)
    db_session.commit()
    db_session.refresh(node)

    assert node.id is not None
    assert node.name == "Test Warehouse Hub"
    assert node.node_type == NodeType.WAREHOUSE.value
    assert node.latitude == 12.9716
    assert node.longitude == 77.5946
    assert node.is_active is True


def test_network_edge_creation(db_session: Session):
    node_a = NetworkNode(
        name="Node A",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.9,
        longitude=77.6,
    )
    node_b = NetworkNode(
        name="Node B",
        node_type=NodeType.CUSTOMER.value,
        latitude=12.95,
        longitude=77.65,
    )
    db_session.add_all([node_a, node_b])
    db_session.commit()

    edge = NetworkEdge(
        source_node_id=node_a.id,
        target_node_id=node_b.id,
        distance_km=10.5,
        estimated_travel_minutes=25,
        road_type="PRIMARY",
        is_active=True,
    )
    db_session.add(edge)
    db_session.commit()
    db_session.refresh(edge)

    assert edge.id is not None
    assert edge.source_node_id == node_a.id
    assert edge.target_node_id == node_b.id
    assert edge.distance_km == 10.5
    assert edge.estimated_travel_minutes == 25


def test_foreign_key_enforcement(db_session: Session):
    # Attempt to create edge pointing to non-existent nodes
    edge = NetworkEdge(
        source_node_id="non-existent-source-id",
        target_node_id="non-existent-target-id",
        distance_km=5.0,
        estimated_travel_minutes=15,
    )
    db_session.add(edge)
    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()
    db_session.rollback()


def test_invalid_coordinates_rejected(db_session: Session):
    # Invalid latitude > 90
    with pytest.raises(ValueError, match="Latitude"):
        NetworkNode(
            name="Invalid Lat",
            node_type=NodeType.CUSTOMER.value,
            latitude=95.0,
            longitude=77.0,
        )

    # Invalid longitude < -180
    with pytest.raises(ValueError, match="Longitude"):
        NetworkNode(
            name="Invalid Lon",
            node_type=NodeType.CUSTOMER.value,
            latitude=12.0,
            longitude=-185.0,
        )


def test_invalid_distance_and_travel_time_rejected(db_session: Session):
    node_a = NetworkNode(name="A", node_type=NodeType.WAREHOUSE.value, latitude=12.0, longitude=77.0)
    node_b = NetworkNode(name="B", node_type=NodeType.CUSTOMER.value, latitude=12.1, longitude=77.1)
    db_session.add_all([node_a, node_b])
    db_session.commit()

    # Negative distance rejected
    with pytest.raises(ValueError, match="distance_km"):
        NetworkEdge(
            source_node_id=node_a.id,
            target_node_id=node_b.id,
            distance_km=-5.0,
            estimated_travel_minutes=10,
        )

    # Zero distance rejected
    with pytest.raises(ValueError, match="distance_km"):
        NetworkEdge(
            source_node_id=node_a.id,
            target_node_id=node_b.id,
            distance_km=0,
            estimated_travel_minutes=10,
        )

    # Negative travel time rejected
    with pytest.raises(ValueError, match="estimated_travel_minutes"):
        NetworkEdge(
            source_node_id=node_a.id,
            target_node_id=node_b.id,
            distance_km=5.0,
            estimated_travel_minutes=-10,
        )

    # Self-connection rejected
    with pytest.raises(ValueError, match="cannot be identical"):
        NetworkEdge(
            source_node_id=node_a.id,
            target_node_id=node_a.id,
            distance_km=5.0,
            estimated_travel_minutes=10,
        )


def test_duplicate_connections_rejected(db_session: Session):
    node_a = NetworkNode(name="N1", node_type=NodeType.WAREHOUSE.value, latitude=12.0, longitude=77.0)
    node_b = NetworkNode(name="N2", node_type=NodeType.CUSTOMER.value, latitude=12.1, longitude=77.1)
    db_session.add_all([node_a, node_b])
    db_session.commit()

    edge1 = NetworkEdge(
        source_node_id=node_a.id,
        target_node_id=node_b.id,
        distance_km=10.0,
        estimated_travel_minutes=20,
    )
    db_session.add(edge1)
    db_session.commit()

    # Same directed edge A -> B should violate UniqueConstraint
    edge2 = NetworkEdge(
        source_node_id=node_a.id,
        target_node_id=node_b.id,
        distance_km=12.0,
        estimated_travel_minutes=25,
    )
    db_session.add(edge2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
