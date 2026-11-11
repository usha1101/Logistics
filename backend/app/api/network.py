from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.session import get_db
from app.models.network import NetworkEdge, NetworkNode, NodeType
from app.models.user import User, UserRole
from app.schemas.network import (
    FeatureTypeFilter,
    GeoJSONFeatureCollection,
    NetworkAnalyticsResponse,
    NetworkComponentsResponse,
    NetworkData,
    NetworkEdgeRead,
    NetworkGraphResponse,
    NetworkNodeRead,
    NetworkStateResponse,
    NetworkSummary,
    NetworkValidationResponse,
    NetworkWeightType,
    NodeConnectivityResponse,
    PaginatedEdgesResponse,
    PaginatedNodesResponse,
    ShortestPathResponse,
)
from app.services.network_graph_service import (
    InvalidWeightError,
    NetworkGraphService,
    NodeNotFoundError,
    PathNotFoundError,
)

router = APIRouter(prefix="/network", tags=["Logistics Network"])

# Roles with full read access to individual nodes and edges
ALL_NETWORK_READ_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
    UserRole.ANALYST,
    UserRole.FLEET_MANAGER,
    UserRole.WAREHOUSE_MANAGER,
)

# Roles permitted to inspect full network digital twin state
NETWORK_STATE_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
    UserRole.ANALYST,
)


def _load_network_elements(db: Session, only_active: bool = False):
    """Helper to query nodes and edges in a single batch to avoid N+1 queries."""
    node_query = select(NetworkNode)
    edge_query = select(NetworkEdge)
    if only_active:
        node_query = node_query.where(NetworkNode.is_active.is_(True))
        edge_query = edge_query.where(NetworkEdge.is_active.is_(True))

    nodes = list(db.execute(node_query.order_by(NetworkNode.name.asc())).scalars().all())
    edges = list(db.execute(edge_query.order_by(NetworkEdge.created_at.asc())).scalars().all())
    return nodes, edges


# ============================================================================
# STAGE 7: GRAPH INTELLIGENCE & VISUALIZATION ENDPOINTS
# ============================================================================

@router.get(
    "/graph",
    response_model=NetworkGraphResponse,
    summary="Get complete graph overview, node/edge attributes, and connectivity",
)
def get_graph_overview(
    only_active: bool = Query(True, description="Filter only active nodes and edges"),
    current_user: User = Depends(require_roles(*ALL_NETWORK_READ_ROLES)),
    db: Session = Depends(get_db),
) -> NetworkGraphResponse:
    """Return nodes, edges, graph metadata, density, and connectivity information."""
    nodes, edges = _load_network_elements(db, only_active=only_active)
    return NetworkGraphService.get_graph_overview(nodes, edges, only_active=only_active)


@router.get(
    "/analytics",
    response_model=NetworkAnalyticsResponse,
    summary="Get calculated network graph metrics and topology statistics",
)
def get_network_analytics(
    only_active: bool = Query(True, description="Calculate metrics on active graph"),
    current_user: User = Depends(require_roles(*ALL_NETWORK_READ_ROLES)),
    db: Session = Depends(get_db),
) -> NetworkAnalyticsResponse:
    """Calculate mathematically supported graph metrics (density, degree, components, distances)."""
    nodes, edges = _load_network_elements(db, only_active=only_active)
    return NetworkGraphService.calculate_analytics(nodes, edges, only_active=only_active)


@router.get(
    "/validate",
    response_model=NetworkValidationResponse,
    summary="Validate network topology, references, attributes, and coordinates",
)
def validate_network(
    current_user: User = Depends(require_roles(*ALL_NETWORK_READ_ROLES)),
    db: Session = Depends(get_db),
) -> NetworkValidationResponse:
    """Audit graph for isolated nodes, disconnected components, invalid references, and coordinate anomalies."""
    nodes, edges = _load_network_elements(db, only_active=False)
    return NetworkGraphService.validate_network(nodes, edges)


@router.get(
    "/geojson",
    response_model=GeoJSONFeatureCollection,
    summary="Get network as RFC 7946 GeoJSON FeatureCollection",
)
def get_network_geojson(
    feature_type: FeatureTypeFilter = Query(
        FeatureTypeFilter.ALL,
        description="Filter feature types: 'all', 'nodes', or 'edges'",
    ),
    only_active: bool = Query(True, description="Include only active features"),
    current_user: User = Depends(require_roles(*ALL_NETWORK_READ_ROLES)),
    db: Session = Depends(get_db),
) -> GeoJSONFeatureCollection:
    """Generate GeoJSON Point and LineString features with [longitude, latitude] coordinates."""
    nodes, edges = _load_network_elements(db, only_active=only_active)
    return NetworkGraphService.generate_geojson(
        nodes, edges, feature_type=feature_type.value, only_active=only_active
    )


@router.get(
    "/shortest-path",
    response_model=ShortestPathResponse,
    summary="Calculate shortest path between two nodes using Dijkstra's algorithm",
)
def calculate_shortest_path(
    origin_node_id: str = Query(..., description="Origin node UUID"),
    destination_node_id: str = Query(..., description="Destination node UUID"),
    weight: NetworkWeightType = Query(
        NetworkWeightType.DISTANCE,
        description="Weight attribute: 'distance' or 'travel_time'",
    ),
    directed: bool = Query(
        True,
        description="Follow directed edges (True) or treat as undirected road network (False)",
    ),
    current_user: User = Depends(require_roles(*ALL_NETWORK_READ_ROLES)),
    db: Session = Depends(get_db),
) -> ShortestPathResponse:
    """Calculate shortest path, ordered node IDs, edge sequences, cumulative distance, and travel time."""
    nodes, edges = _load_network_elements(db, only_active=True)
    try:
        return NetworkGraphService.calculate_shortest_path(
            nodes=nodes,
            edges=edges,
            origin_node_id=origin_node_id,
            destination_node_id=destination_node_id,
            weight=weight.value,
            directed=directed,
            only_active=True,
        )
    except NodeNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PathNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidWeightError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/components",
    response_model=NetworkComponentsResponse,
    summary="Get connected components and node memberships",
)
def get_network_components(
    only_active: bool = Query(True, description="Calculate on active graph"),
    current_user: User = Depends(require_roles(*ALL_NETWORK_READ_ROLES)),
    db: Session = Depends(get_db),
) -> NetworkComponentsResponse:
    """Return list of connected components, node sizes, and warehouse/customer breakdowns."""
    nodes, edges = _load_network_elements(db, only_active=only_active)
    return NetworkGraphService.get_components(nodes, edges, only_active=only_active)


@router.get(
    "/nodes/{node_id}/connections",
    response_model=NodeConnectivityResponse,
    summary="Get direct connections, incident edges, and degree for a node",
)
def get_node_connections(
    node_id: str,
    only_active: bool = Query(True, description="Consider only active connections"),
    current_user: User = Depends(require_roles(*ALL_NETWORK_READ_ROLES)),
    db: Session = Depends(get_db),
) -> NodeConnectivityResponse:
    """Inspect adjacent nodes, incident edges, travel times, and directional degree."""
    nodes, edges = _load_network_elements(db, only_active=only_active)
    try:
        return NetworkGraphService.get_node_connections(
            nodes=nodes, edges=edges, node_id=node_id, only_active=only_active
        )
    except NodeNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ============================================================================
# EXISTING NETWORK APIS (PRESERVED)
# ============================================================================

@router.get(
    "/state",
    response_model=NetworkStateResponse,
    summary="Get complete active logistics network digital twin state",
)

def get_network_state(
    current_user: User = Depends(require_roles(*NETWORK_STATE_ROLES)),
    db: Session = Depends(get_db),
) -> NetworkStateResponse:
    # 1. Efficiently query active nodes and edges (avoids N+1 query overhead)
    nodes_stmt = (
        select(NetworkNode)
        .where(NetworkNode.is_active.is_(True))
        .order_by(NetworkNode.node_type.desc(), NetworkNode.name.asc())
    )
    nodes = list(db.execute(nodes_stmt).scalars().all())

    edges_stmt = (
        select(NetworkEdge)
        .where(NetworkEdge.is_active.is_(True))
        .order_by(NetworkEdge.created_at.asc())
    )
    edges = list(db.execute(edges_stmt).scalars().all())

    total_warehouses = sum(
        1 for n in nodes if n.node_type == NodeType.WAREHOUSE.value
    )
    total_customers = sum(
        1 for n in nodes if n.node_type == NodeType.CUSTOMER.value
    )

    summary = NetworkSummary(
        total_nodes=len(nodes),
        total_warehouses=total_warehouses,
        total_customers=total_customers,
        total_connections=len(edges),
    )

    network_data = NetworkData(
        name="LOGIPULSE Demo Network",
        nodes=[NetworkNodeRead.model_validate(n) for n in nodes],
        edges=[NetworkEdgeRead.model_validate(e) for e in edges],
    )

    return NetworkStateResponse(
        simulation_id=None,
        network=network_data,
        summary=summary,
        data_source="SIMULATED",
    )


@router.get(
    "/nodes",
    response_model=PaginatedNodesResponse,
    summary="List network nodes with filtering and pagination",
)
def list_nodes(
    node_type: Optional[NodeType] = Query(None, description="Filter by node type"),
    region: Optional[str] = Query(None, description="Filter by geographic region"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    current_user: User = Depends(require_roles(*ALL_NETWORK_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedNodesResponse:
    query = select(NetworkNode)

    if node_type is not None:
        type_str = node_type.value if isinstance(node_type, NodeType) else str(node_type)
        query = query.where(NetworkNode.node_type == type_str)
    if region is not None:
        query = query.where(NetworkNode.region == region)
    if is_active is not None:
        query = query.where(NetworkNode.is_active.is_(is_active))

    # Total matching records count
    total_stmt = select(func.count()).select_from(query.subquery())
    total = db.execute(total_stmt).scalar() or 0

    # Paginated results
    paginated_stmt = query.order_by(NetworkNode.name.asc()).offset(skip).limit(limit)
    items = list(db.execute(paginated_stmt).scalars().all())

    return PaginatedNodesResponse(
        items=[NetworkNodeRead.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/nodes/{node_id}",
    response_model=NetworkNodeRead,
    summary="Get single network node by ID",
)
def get_node(
    node_id: str,
    current_user: User = Depends(require_roles(*ALL_NETWORK_READ_ROLES)),
    db: Session = Depends(get_db),
) -> NetworkNodeRead:
    stmt = select(NetworkNode).where(NetworkNode.id == node_id)
    node = db.execute(stmt).scalar_one_or_none()
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network node '{node_id}' not found",
        )
    return NetworkNodeRead.model_validate(node)


@router.get(
    "/edges",
    response_model=PaginatedEdgesResponse,
    summary="List network edges with filtering and pagination",
)
def list_edges(
    source_node_id: Optional[str] = Query(None, description="Filter by source node ID"),
    target_node_id: Optional[str] = Query(None, description="Filter by target node ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    current_user: User = Depends(require_roles(*ALL_NETWORK_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedEdgesResponse:
    query = select(NetworkEdge)

    if source_node_id is not None:
        query = query.where(NetworkEdge.source_node_id == source_node_id)
    if target_node_id is not None:
        query = query.where(NetworkEdge.target_node_id == target_node_id)
    if is_active is not None:
        query = query.where(NetworkEdge.is_active.is_(is_active))

    total_stmt = select(func.count()).select_from(query.subquery())
    total = db.execute(total_stmt).scalar() or 0

    paginated_stmt = query.order_by(NetworkEdge.created_at.asc()).offset(skip).limit(limit)
    items = list(db.execute(paginated_stmt).scalars().all())

    return PaginatedEdgesResponse(
        items=[NetworkEdgeRead.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/edges/{edge_id}",
    response_model=NetworkEdgeRead,
    summary="Get single network edge by ID",
)
def get_edge(
    edge_id: str,
    current_user: User = Depends(require_roles(*ALL_NETWORK_READ_ROLES)),
    db: Session = Depends(get_db),
) -> NetworkEdgeRead:
    stmt = select(NetworkEdge).where(NetworkEdge.id == edge_id)
    edge = db.execute(stmt).scalar_one_or_none()
    if not edge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network edge '{edge_id}' not found",
        )
    return NetworkEdgeRead.model_validate(edge)

