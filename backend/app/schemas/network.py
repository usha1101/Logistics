from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.network import NodeType


class NetworkWeightType(str, Enum):
    DISTANCE = "distance"
    TRAVEL_TIME = "travel_time"


class FeatureTypeFilter(str, Enum):
    ALL = "all"
    NODES = "nodes"
    EDGES = "edges"


class NetworkNodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    name: str
    type: str = Field(alias="node_type")
    node_type: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    region: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @computed_field
    def coordinates(self) -> List[float]:
        """GeoJSON format [longitude, latitude] for map renderers."""
        return [self.longitude, self.latitude]


class NetworkEdgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_node_id: str
    target_node_id: str
    distance_km: float
    estimated_travel_minutes: int
    road_type: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NetworkSummary(BaseModel):
    total_nodes: int
    total_warehouses: int
    total_customers: int
    total_connections: int


class NetworkData(BaseModel):
    name: str = "LOGIPULSE Demo Network"
    nodes: List[NetworkNodeRead]
    edges: List[NetworkEdgeRead]


class NetworkStateResponse(BaseModel):
    simulation_id: Optional[str] = None
    network: NetworkData
    summary: NetworkSummary
    data_source: Literal["SIMULATED"] = "SIMULATED"


class PaginatedNodesResponse(BaseModel):
    items: List[NetworkNodeRead]
    total: int
    skip: int
    limit: int


class PaginatedEdgesResponse(BaseModel):
    items: List[NetworkEdgeRead]
    total: int
    skip: int
    limit: int


# ============================================================================
# STAGE 7: GRAPH INTELLIGENCE & VISUALIZATION SCHEMAS
# ============================================================================

class GraphMetadata(BaseModel):
    directed: bool = True
    total_nodes: int
    total_edges: int
    warehouse_nodes: int
    customer_nodes: int
    density: float


class GraphNodeData(BaseModel):
    id: str
    name: str
    node_type: str
    region: Optional[str] = None
    latitude: float
    longitude: float
    coordinates: List[float]
    in_degree: int
    out_degree: int
    degree: int
    is_active: bool


class GraphEdgeData(BaseModel):
    id: str
    source_node_id: str
    target_node_id: str
    distance_km: float
    estimated_travel_minutes: int
    road_type: Optional[str] = None
    is_active: bool


class NetworkGraphResponse(BaseModel):
    metadata: GraphMetadata
    nodes: List[GraphNodeData]
    edges: List[GraphEdgeData]
    is_connected: bool
    connected_components_count: int
    data_source: Literal["SIMULATED"] = "SIMULATED"


class NetworkAnalyticsResponse(BaseModel):
    total_nodes: int
    total_edges: int
    warehouse_nodes: int
    customer_nodes: int
    connected_components: int
    strongly_connected_components: Optional[int] = None
    isolated_nodes: int
    isolated_node_ids: List[str]
    graph_density: float
    average_node_degree: float
    total_network_distance_km: float
    average_edge_distance_km: Optional[float] = None
    average_travel_time_minutes: Optional[float] = None
    network_connectivity_status: Literal["CONNECTED", "DISCONNECTED"]
    data_source: Literal["SIMULATED"] = "SIMULATED"


class ValidationErrorItem(BaseModel):
    category: str
    message: str
    entity_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ValidationWarningItem(BaseModel):
    category: str
    message: str
    entity_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class NetworkValidationResponse(BaseModel):
    validation_status: Literal["VALID", "WARNINGS", "INVALID"]
    is_valid: bool
    error_count: int
    warning_count: int
    errors: List[ValidationErrorItem]
    warnings: List[ValidationWarningItem]
    isolated_nodes: List[str]
    disconnected_components: List[List[str]]
    invalid_edge_references: List[str]


# GeoJSON (RFC 7946)
class GeoJSONGeometry(BaseModel):
    type: Literal["Point", "LineString"]
    coordinates: Any


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: GeoJSONGeometry
    properties: Dict[str, Any]


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[GeoJSONFeature]
    metadata: Optional[Dict[str, Any]] = None


# Shortest Path
class PathNodeDetail(BaseModel):
    id: str
    name: str
    node_type: str
    coordinates: List[float]


class PathEdgeDetail(BaseModel):
    id: str
    source_node_id: str
    target_node_id: str
    distance_km: float
    estimated_travel_minutes: int
    road_type: Optional[str] = None


class ShortestPathResponse(BaseModel):
    origin_node_id: str
    destination_node_id: str
    origin_node: PathNodeDetail
    destination_node: PathNodeDetail
    weight: str
    algorithm: Literal["Dijkstra"] = "Dijkstra"
    ordered_node_ids: List[str]
    ordered_nodes: List[PathNodeDetail]
    edge_ids: List[str]
    edges: List[PathEdgeDetail]
    total_distance_km: float
    estimated_travel_minutes: Optional[float] = None
    coordinates: List[List[float]]
    data_source: Literal["SIMULATED"] = "SIMULATED"


# Node Connectivity
class ConnectedNodeDetail(BaseModel):
    id: str
    name: str
    node_type: str
    coordinates: List[float]
    direction: Literal["OUTGOING", "INCOMING", "BIDIRECTIONAL"]


class ConnectingEdgeDetail(BaseModel):
    id: str
    source_node_id: str
    target_node_id: str
    distance_km: float
    estimated_travel_minutes: int
    road_type: Optional[str] = None
    direction: Literal["OUTGOING", "INCOMING"]


class NodeConnectivityResponse(BaseModel):
    node_id: str
    node_name: str
    node_type: str
    in_degree: int
    out_degree: int
    total_degree: int
    connected_nodes: List[ConnectedNodeDetail]
    connecting_edges: List[ConnectingEdgeDetail]


# Network Components
class ComponentDetail(BaseModel):
    component_index: int
    node_count: int
    node_ids: List[str]
    warehouse_count: int
    customer_count: int


class NetworkComponentsResponse(BaseModel):
    total_components: int
    is_connected: bool
    components: List[ComponentDetail]


