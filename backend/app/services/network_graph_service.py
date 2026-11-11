import logging
from typing import Any, Dict, List, Literal, Optional, Sequence, Set, Tuple
import networkx as nx

from app.models.network import NetworkEdge, NetworkNode, NodeType
from app.schemas.network import (
    ComponentDetail,
    ConnectedNodeDetail,
    ConnectingEdgeDetail,
    FeatureTypeFilter,
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    GeoJSONGeometry,
    GraphEdgeData,
    GraphMetadata,
    GraphNodeData,
    NetworkAnalyticsResponse,
    NetworkComponentsResponse,
    NetworkGraphResponse,
    NetworkValidationResponse,
    NetworkWeightType,
    NodeConnectivityResponse,
    PathEdgeDetail,
    PathNodeDetail,
    ShortestPathResponse,
    ValidationErrorItem,
    ValidationWarningItem,
)

logger = logging.getLogger("network_graph_service")


class NetworkGraphError(Exception):
    """Base exception for network graph operations."""
    pass


class NodeNotFoundError(NetworkGraphError):
    """Raised when an origin or destination node does not exist."""
    pass


class PathNotFoundError(NetworkGraphError):
    """Raised when no navigable path exists between two nodes."""
    pass


class InvalidWeightError(NetworkGraphError):
    """Raised when an edge weight is non-positive or unsupported."""
    pass


class NetworkGraphService:
    """Service for transforming database network models into in-memory NetworkX graphs

    and executing graph intelligence, shortest path algorithms, analytics, and GeoJSON visualizations.
    """

    @staticmethod
    def build_digraph(
        nodes: Sequence[NetworkNode],
        edges: Sequence[NetworkEdge],
        only_active: bool = True,
    ) -> nx.DiGraph:
        """Construct a NetworkX DiGraph preserving node and edge identities and attributes.

        Avoids creating connections absent from the database.
        """
        G = nx.DiGraph()

        # Filter active nodes if requested
        valid_node_ids: Set[str] = set()
        for node in nodes:
            if only_active and not node.is_active:
                continue
            valid_node_ids.add(node.id)
            G.add_node(
                node.id,
                id=node.id,
                name=node.name,
                node_type=node.node_type,
                latitude=node.latitude,
                longitude=node.longitude,
                region=node.region,
                address=node.address,
                is_active=node.is_active,
            )

        # Add edges whose endpoints exist in the node set
        for edge in edges:
            if only_active and not edge.is_active:
                continue
            if edge.source_node_id not in valid_node_ids or edge.target_node_id not in valid_node_ids:
                # Do not invent connections to non-existent nodes
                continue

            # Weight attributes for Dijkstra
            dist = float(edge.distance_km) if edge.distance_km is not None else 0.0
            travel = float(edge.estimated_travel_minutes) if edge.estimated_travel_minutes is not None else 0.0

            G.add_edge(
                edge.source_node_id,
                edge.target_node_id,
                id=edge.id,
                source_node_id=edge.source_node_id,
                target_node_id=edge.target_node_id,
                distance_km=dist,
                estimated_travel_minutes=int(travel),
                road_type=edge.road_type,
                is_active=edge.is_active,
                distance=dist,
                travel_time=travel,
            )

        return G

    @staticmethod
    def build_undirected_graph(
        nodes: Sequence[NetworkNode],
        edges: Sequence[NetworkEdge],
        only_active: bool = True,
    ) -> nx.Graph:
        """Construct an undirected NetworkX Graph."""
        di_g = NetworkGraphService.build_digraph(nodes, edges, only_active=only_active)
        return di_g.to_undirected()

    @staticmethod
    def get_graph_overview(
        nodes: Sequence[NetworkNode],
        edges: Sequence[NetworkEdge],
        only_active: bool = False,
    ) -> NetworkGraphResponse:
        """Build graph overview with node and edge data and connectivity information."""
        G = NetworkGraphService.build_digraph(nodes, edges, only_active=only_active)

        nodes_map = {n.id: n for n in nodes}
        graph_nodes: List[GraphNodeData] = []
        warehouse_count = 0
        customer_count = 0

        for node_id, data in G.nodes(data=True):
            in_deg = G.in_degree(node_id)
            out_deg = G.out_degree(node_id)
            tot_deg = in_deg + out_deg
            n_type = data.get("node_type", "UNKNOWN")
            if n_type == NodeType.WAREHOUSE.value:
                warehouse_count += 1
            elif n_type == NodeType.CUSTOMER.value:
                customer_count += 1

            graph_nodes.append(
                GraphNodeData(
                    id=node_id,
                    name=data.get("name", ""),
                    node_type=n_type,
                    region=data.get("region"),
                    latitude=data.get("latitude", 0.0),
                    longitude=data.get("longitude", 0.0),
                    coordinates=[data.get("longitude", 0.0), data.get("latitude", 0.0)],
                    in_degree=in_deg,
                    out_degree=out_deg,
                    degree=tot_deg,
                    is_active=data.get("is_active", True),
                )
            )

        graph_edges: List[GraphEdgeData] = []
        for u, v, data in G.edges(data=True):
            graph_edges.append(
                GraphEdgeData(
                    id=data.get("id", f"{u}->{v}"),
                    source_node_id=u,
                    target_node_id=v,
                    distance_km=data.get("distance_km", 0.0),
                    estimated_travel_minutes=data.get("estimated_travel_minutes", 0),
                    road_type=data.get("road_type"),
                    is_active=data.get("is_active", True),
                )
            )

        num_nodes = len(graph_nodes)
        density = nx.density(G) if num_nodes > 1 else 0.0
        components_count = nx.number_weakly_connected_components(G) if num_nodes > 0 else 0
        is_connected = components_count == 1 if num_nodes > 0 else False

        metadata = GraphMetadata(
            directed=True,
            total_nodes=num_nodes,
            total_edges=len(graph_edges),
            warehouse_nodes=warehouse_count,
            customer_nodes=customer_count,
            density=round(density, 4),
        )

        return NetworkGraphResponse(
            metadata=metadata,
            nodes=graph_nodes,
            edges=graph_edges,
            is_connected=is_connected,
            connected_components_count=components_count,
            data_source="SIMULATED",
        )

    @staticmethod
    def validate_network(
        nodes: Sequence[NetworkNode],
        edges: Sequence[NetworkEdge],
    ) -> NetworkValidationResponse:
        """Validate network topology and attribute consistency without mutating user data."""
        errors: List[ValidationErrorItem] = []
        warnings: List[ValidationWarningItem] = []
        node_ids: Set[str] = {n.id for n in nodes}

        # 1. Validate Nodes
        for node in nodes:
            # Coordinates
            if node.latitude is None or node.longitude is None:
                errors.append(
                    ValidationErrorItem(
                        category="COORDINATES",
                        message=f"Node '{node.name}' ({node.id}) has missing geographical coordinates",
                        entity_id=node.id,
                    )
                )
            elif not (-90.0 <= node.latitude <= 90.0) or not (-180.0 <= node.longitude <= 180.0):
                errors.append(
                    ValidationErrorItem(
                        category="COORDINATES",
                        message=f"Node '{node.name}' ({node.id}) coordinates ({node.latitude}, {node.longitude}) out of bounds",
                        entity_id=node.id,
                        details={"latitude": node.latitude, "longitude": node.longitude},
                    )
                )

            if not node.is_active:
                warnings.append(
                    ValidationWarningItem(
                        category="INACTIVE_NODE",
                        message=f"Node '{node.name}' ({node.id}) is marked inactive",
                        entity_id=node.id,
                    )
                )

        # 2. Validate Edges
        invalid_edge_references: List[str] = []
        edge_pairs: Set[Tuple[str, str]] = set()

        for edge in edges:
            has_ref_error = False
            if edge.source_node_id not in node_ids:
                has_ref_error = True
                errors.append(
                    ValidationErrorItem(
                        category="INVALID_REFERENCE",
                        message=f"Edge '{edge.id}' references non-existent source node '{edge.source_node_id}'",
                        entity_id=edge.id,
                        details={"missing_node_id": edge.source_node_id, "role": "source"},
                    )
                )
            if edge.target_node_id not in node_ids:
                has_ref_error = True
                errors.append(
                    ValidationErrorItem(
                        category="INVALID_REFERENCE",
                        message=f"Edge '{edge.id}' references non-existent target node '{edge.target_node_id}'",
                        entity_id=edge.id,
                        details={"missing_node_id": edge.target_node_id, "role": "target"},
                    )
                )
            if has_ref_error:
                invalid_edge_references.append(edge.id)

            if edge.source_node_id == edge.target_node_id:
                errors.append(
                    ValidationErrorItem(
                        category="SELF_LOOP",
                        message=f"Edge '{edge.id}' is a self-referencing loop",
                        entity_id=edge.id,
                    )
                )

            # Distance
            if edge.distance_km is None:
                errors.append(
                    ValidationErrorItem(
                        category="MISSING_DISTANCE",
                        message=f"Edge '{edge.id}' missing distance_km attribute",
                        entity_id=edge.id,
                    )
                )
            elif edge.distance_km <= 0:
                errors.append(
                    ValidationErrorItem(
                        category="NEGATIVE_DISTANCE",
                        message=f"Edge '{edge.id}' has non-positive distance {edge.distance_km} km",
                        entity_id=edge.id,
                        details={"distance_km": edge.distance_km},
                    )
                )

            # Travel time
            if edge.estimated_travel_minutes is None:
                warnings.append(
                    ValidationWarningItem(
                        category="MISSING_TRAVEL_TIME",
                        message=f"Edge '{edge.id}' missing estimated_travel_minutes attribute",
                        entity_id=edge.id,
                    )
                )
            elif edge.estimated_travel_minutes <= 0:
                warnings.append(
                    ValidationWarningItem(
                        category="INVALID_TRAVEL_TIME",
                        message=f"Edge '{edge.id}' has non-positive travel time {edge.estimated_travel_minutes} mins",
                        entity_id=edge.id,
                        details={"estimated_travel_minutes": edge.estimated_travel_minutes},
                    )
                )

            # Duplicate pairs
            pair = (edge.source_node_id, edge.target_node_id)
            if pair in edge_pairs:
                warnings.append(
                    ValidationWarningItem(
                        category="DUPLICATE_EDGE",
                        message=f"Duplicate edge detected between '{edge.source_node_id}' and '{edge.target_node_id}'",
                        entity_id=edge.id,
                    )
                )
            else:
                edge_pairs.add(pair)

            if not edge.is_active:
                warnings.append(
                    ValidationWarningItem(
                        category="INACTIVE_EDGE",
                        message=f"Edge '{edge.id}' is marked inactive",
                        entity_id=edge.id,
                    )
                )

        # 3. Topology Validation (Isolated Nodes & Components)
        G = NetworkGraphService.build_digraph(nodes, edges, only_active=False)
        isolated_nodes: List[str] = [n for n in G.nodes() if G.degree(n) == 0]
        if isolated_nodes:
            warnings.append(
                ValidationWarningItem(
                    category="ISOLATED_NODES",
                    message=f"Found {len(isolated_nodes)} isolated node(s) with no connections",
                    details={"isolated_node_ids": isolated_nodes},
                )
            )

        disconnected_components: List[List[str]] = []
        if len(G.nodes()) > 0:
            components = list(nx.weakly_connected_components(G))
            if len(components) > 1:
                disconnected_components = [sorted(list(c)) for c in components]
                warnings.append(
                    ValidationWarningItem(
                        category="DISCONNECTED_COMPONENTS",
                        message=f"Network partitioned into {len(components)} disconnected components",
                        details={"component_count": len(components)},
                    )
                )

        is_valid = len(errors) == 0
        if not is_valid:
            status: Literal["VALID", "WARNINGS", "INVALID"] = "INVALID"
        elif len(warnings) > 0:
            status = "WARNINGS"
        else:
            status = "VALID"

        return NetworkValidationResponse(
            validation_status=status,
            is_valid=is_valid,
            error_count=len(errors),
            warning_count=len(warnings),
            errors=errors,
            warnings=warnings,
            isolated_nodes=isolated_nodes,
            disconnected_components=disconnected_components,
            invalid_edge_references=invalid_edge_references,
        )

    @staticmethod
    def calculate_shortest_path(
        nodes: Sequence[NetworkNode],
        edges: Sequence[NetworkEdge],
        origin_node_id: str,
        destination_node_id: str,
        weight: str = "distance",
        directed: bool = True,
        only_active: bool = True,
    ) -> ShortestPathResponse:
        """Calculate shortest path between two nodes using Dijkstra's algorithm.

        Supports distance and travel-time weights.
        """
        nodes_map = {n.id: n for n in nodes}
        if origin_node_id not in nodes_map:
            raise NodeNotFoundError(f"Origin node '{origin_node_id}' not found in network")
        if destination_node_id not in nodes_map:
            raise NodeNotFoundError(f"Destination node '{destination_node_id}' not found in network")

        origin_node = nodes_map[origin_node_id]
        dest_node = nodes_map[destination_node_id]

        # Same origin and destination edge case
        if origin_node_id == destination_node_id:
            origin_detail = PathNodeDetail(
                id=origin_node.id,
                name=origin_node.name,
                node_type=origin_node.node_type,
                coordinates=[origin_node.longitude, origin_node.latitude],
            )
            return ShortestPathResponse(
                origin_node_id=origin_node_id,
                destination_node_id=destination_node_id,
                origin_node=origin_detail,
                destination_node=origin_detail,
                weight=weight,
                algorithm="Dijkstra",
                ordered_node_ids=[origin_node_id],
                ordered_nodes=[origin_detail],
                edge_ids=[],
                edges=[],
                total_distance_km=0.0,
                estimated_travel_minutes=0.0,
                coordinates=[[origin_node.longitude, origin_node.latitude]],
                data_source="SIMULATED",
            )

        # Build graph
        if directed:
            G = NetworkGraphService.build_digraph(nodes, edges, only_active=only_active)
        else:
            G = NetworkGraphService.build_undirected_graph(nodes, edges, only_active=only_active)

        if not G.has_node(origin_node_id):
            raise PathNotFoundError(f"Origin node '{origin_node_id}' is inactive or has no active graph representation")
        if not G.has_node(destination_node_id):
            raise PathNotFoundError(f"Destination node '{destination_node_id}' is inactive or has no active graph representation")

        weight_attr = "distance" if weight == "distance" else "travel_time"

        # Validate edge weights along graph
        for u, v, data in G.edges(data=True):
            val = data.get(weight_attr, 0.0)
            if val is None or val <= 0:
                raise InvalidWeightError(f"Edge ({u}->{v}) has non-positive weight {val} for attribute '{weight_attr}'")

        try:
            path_node_ids: List[str] = nx.dijkstra_path(
                G, origin_node_id, destination_node_id, weight=weight_attr
            )
        except nx.NetworkXNoPath:
            raise PathNotFoundError(
                f"No navigable path exists from node '{origin_node.name}' ({origin_node_id}) "
                f"to node '{dest_node.name}' ({destination_node_id}) using {weight} weighting"
            )

        # Assemble ordered nodes, edges, coordinates, and cumulative totals
        ordered_nodes: List[PathNodeDetail] = []
        coordinates: List[List[float]] = []
        for nid in path_node_ids:
            nd = nodes_map[nid]
            detail = PathNodeDetail(
                id=nd.id,
                name=nd.name,
                node_type=nd.node_type,
                coordinates=[nd.longitude, nd.latitude],
            )
            ordered_nodes.append(detail)
            coordinates.append([nd.longitude, nd.latitude])

        ordered_edges: List[PathEdgeDetail] = []
        edge_ids: List[str] = []
        total_distance = 0.0
        total_travel_minutes = 0.0

        for i in range(len(path_node_ids) - 1):
            u = path_node_ids[i]
            v = path_node_ids[i + 1]
            edge_data = G.get_edge_data(u, v)

            e_id = edge_data.get("id", f"{u}->{v}")
            e_dist = float(edge_data.get("distance_km", 0.0))
            e_time = int(edge_data.get("estimated_travel_minutes", 0))
            e_road = edge_data.get("road_type")

            edge_ids.append(e_id)
            total_distance += e_dist
            total_travel_minutes += e_time

            ordered_edges.append(
                PathEdgeDetail(
                    id=e_id,
                    source_node_id=u,
                    target_node_id=v,
                    distance_km=e_dist,
                    estimated_travel_minutes=e_time,
                    road_type=e_road,
                )
            )

        return ShortestPathResponse(
            origin_node_id=origin_node_id,
            destination_node_id=destination_node_id,
            origin_node=ordered_nodes[0],
            destination_node=ordered_nodes[-1],
            weight=weight,
            algorithm="Dijkstra",
            ordered_node_ids=path_node_ids,
            ordered_nodes=ordered_nodes,
            edge_ids=edge_ids,
            edges=ordered_edges,
            total_distance_km=round(total_distance, 2),
            estimated_travel_minutes=round(total_travel_minutes, 1),
            coordinates=coordinates,
            data_source="SIMULATED",
        )

    @staticmethod
    def calculate_analytics(
        nodes: Sequence[NetworkNode],
        edges: Sequence[NetworkEdge],
        only_active: bool = True,
    ) -> NetworkAnalyticsResponse:
        """Calculate mathematically supported graph network analytics."""
        G = NetworkGraphService.build_digraph(nodes, edges, only_active=only_active)

        total_nodes = len(G.nodes())
        total_edges = len(G.edges())

        warehouse_count = sum(1 for _, d in G.nodes(data=True) if d.get("node_type") == NodeType.WAREHOUSE.value)
        customer_count = sum(1 for _, d in G.nodes(data=True) if d.get("node_type") == NodeType.CUSTOMER.value)

        if total_nodes == 0:
            return NetworkAnalyticsResponse(
                total_nodes=0,
                total_edges=0,
                warehouse_nodes=0,
                customer_nodes=0,
                connected_components=0,
                strongly_connected_components=0,
                isolated_nodes=0,
                isolated_node_ids=[],
                graph_density=0.0,
                average_node_degree=0.0,
                total_network_distance_km=0.0,
                average_edge_distance_km=None,
                average_travel_time_minutes=None,
                network_connectivity_status="DISCONNECTED",
                data_source="SIMULATED",
            )

        isolated = [n for n in G.nodes() if G.degree(n) == 0]
        connected_components_count = nx.number_weakly_connected_components(G)
        strongly_connected_count = nx.number_strongly_connected_components(G)

        density = nx.density(G) if total_nodes > 1 else 0.0

        degrees = [deg for _, deg in G.degree()]
        avg_degree = sum(degrees) / total_nodes if total_nodes > 0 else 0.0

        edge_distances = [d.get("distance_km", 0.0) for _, _, d in G.edges(data=True)]
        edge_times = [d.get("estimated_travel_minutes", 0.0) for _, _, d in G.edges(data=True)]

        total_dist = sum(edge_distances)
        avg_dist = (total_dist / total_edges) if total_edges > 0 else None
        avg_time = (sum(edge_times) / total_edges) if total_edges > 0 else None

        is_connected = connected_components_count == 1 and len(isolated) == 0

        return NetworkAnalyticsResponse(
            total_nodes=total_nodes,
            total_edges=total_edges,
            warehouse_nodes=warehouse_count,
            customer_nodes=customer_count,
            connected_components=connected_components_count,
            strongly_connected_components=strongly_connected_count,
            isolated_nodes=len(isolated),
            isolated_node_ids=isolated,
            graph_density=round(density, 4),
            average_node_degree=round(avg_degree, 2),
            total_network_distance_km=round(total_dist, 2),
            average_edge_distance_km=round(avg_dist, 2) if avg_dist is not None else None,
            average_travel_time_minutes=round(avg_time, 2) if avg_time is not None else None,
            network_connectivity_status="CONNECTED" if is_connected else "DISCONNECTED",
            data_source="SIMULATED",
        )

    @staticmethod
    def get_node_connections(
        nodes: Sequence[NetworkNode],
        edges: Sequence[NetworkEdge],
        node_id: str,
        only_active: bool = True,
    ) -> NodeConnectivityResponse:
        """Inspect direct connectivity, incident edges, and degree for a specific node."""
        nodes_map = {n.id: n for n in nodes}
        if node_id not in nodes_map:
            raise NodeNotFoundError(f"Node '{node_id}' not found in network")

        target_node = nodes_map[node_id]

        outgoing_edges: List[ConnectingEdgeDetail] = []
        incoming_edges: List[ConnectingEdgeDetail] = []
        outgoing_target_ids: Set[str] = set()
        incoming_source_ids: Set[str] = set()

        for edge in edges:
            if only_active and not edge.is_active:
                continue
            if edge.source_node_id == node_id and edge.target_node_id in nodes_map:
                outgoing_target_ids.add(edge.target_node_id)
                outgoing_edges.append(
                    ConnectingEdgeDetail(
                        id=edge.id,
                        source_node_id=edge.source_node_id,
                        target_node_id=edge.target_node_id,
                        distance_km=edge.distance_km,
                        estimated_travel_minutes=edge.estimated_travel_minutes,
                        road_type=edge.road_type,
                        direction="OUTGOING",
                    )
                )
            elif edge.target_node_id == node_id and edge.source_node_id in nodes_map:
                incoming_source_ids.add(edge.source_node_id)
                incoming_edges.append(
                    ConnectingEdgeDetail(
                        id=edge.id,
                        source_node_id=edge.source_node_id,
                        target_node_id=edge.target_node_id,
                        distance_km=edge.distance_km,
                        estimated_travel_minutes=edge.estimated_travel_minutes,
                        road_type=edge.road_type,
                        direction="INCOMING",
                    )
                )

        connected_node_ids = outgoing_target_ids.union(incoming_source_ids)
        connected_nodes: List[ConnectedNodeDetail] = []

        for cid in sorted(connected_node_ids):
            c_node = nodes_map[cid]
            if cid in outgoing_target_ids and cid in incoming_source_ids:
                dir_label: Literal["OUTGOING", "INCOMING", "BIDIRECTIONAL"] = "BIDIRECTIONAL"
            elif cid in outgoing_target_ids:
                dir_label = "OUTGOING"
            else:
                dir_label = "INCOMING"

            connected_nodes.append(
                ConnectedNodeDetail(
                    id=c_node.id,
                    name=c_node.name,
                    node_type=c_node.node_type,
                    coordinates=[c_node.longitude, c_node.latitude],
                    direction=dir_label,
                )
            )

        all_edges = outgoing_edges + incoming_edges

        return NodeConnectivityResponse(
            node_id=target_node.id,
            node_name=target_node.name,
            node_type=target_node.node_type,
            in_degree=len(incoming_edges),
            out_degree=len(outgoing_edges),
            total_degree=len(incoming_edges) + len(outgoing_edges),
            connected_nodes=connected_nodes,
            connecting_edges=all_edges,
        )

    @staticmethod
    def get_components(
        nodes: Sequence[NetworkNode],
        edges: Sequence[NetworkEdge],
        only_active: bool = True,
    ) -> NetworkComponentsResponse:
        """Calculate weakly connected components and their node memberships."""
        G = NetworkGraphService.build_digraph(nodes, edges, only_active=only_active)
        nodes_map = {n.id: n for n in nodes}

        if len(G.nodes()) == 0:
            return NetworkComponentsResponse(
                total_components=0,
                is_connected=False,
                components=[],
            )

        raw_components = list(nx.weakly_connected_components(G))
        # Sort components by size descending
        raw_components.sort(key=lambda s: len(s), reverse=True)

        components: List[ComponentDetail] = []
        for idx, comp_nodes in enumerate(raw_components):
            sorted_nodes = sorted(list(comp_nodes))
            w_count = sum(1 for nid in sorted_nodes if nodes_map.get(nid) and nodes_map[nid].node_type == NodeType.WAREHOUSE.value)
            c_count = sum(1 for nid in sorted_nodes if nodes_map.get(nid) and nodes_map[nid].node_type == NodeType.CUSTOMER.value)

            components.append(
                ComponentDetail(
                    component_index=idx + 1,
                    node_count=len(sorted_nodes),
                    node_ids=sorted_nodes,
                    warehouse_count=w_count,
                    customer_count=c_count,
                )
            )

        is_connected = len(raw_components) == 1 and not any(G.degree(n) == 0 for n in G.nodes())

        return NetworkComponentsResponse(
            total_components=len(components),
            is_connected=is_connected,
            components=components,
        )

    @staticmethod
    def generate_geojson(
        nodes: Sequence[NetworkNode],
        edges: Sequence[NetworkEdge],
        feature_type: str = "all",
        only_active: bool = True,
    ) -> GeoJSONFeatureCollection:
        """Generate an RFC 7946 compliant GeoJSON FeatureCollection with Point and LineString features."""
        features: List[GeoJSONFeature] = []
        nodes_map = {n.id: n for n in nodes}

        include_nodes = feature_type in (FeatureTypeFilter.ALL.value, FeatureTypeFilter.NODES.value)
        include_edges = feature_type in (FeatureTypeFilter.ALL.value, FeatureTypeFilter.EDGES.value)

        # 1. Point Features for Nodes
        if include_nodes:
            for node in nodes:
                if only_active and not node.is_active:
                    continue
                features.append(
                    GeoJSONFeature(
                        id=node.id,
                        geometry=GeoJSONGeometry(
                            type="Point",
                            coordinates=[node.longitude, node.latitude],
                        ),
                        properties={
                            "feature_type": "node",
                            "id": node.id,
                            "name": node.name,
                            "node_type": node.node_type,
                            "region": node.region,
                            "address": node.address,
                            "is_active": node.is_active,
                        },
                    )
                )

        # 2. LineString Features for Edges
        if include_edges:
            for edge in edges:
                if only_active and not edge.is_active:
                    continue
                source = nodes_map.get(edge.source_node_id)
                target = nodes_map.get(edge.target_node_id)
                if not source or not target:
                    continue

                features.append(
                    GeoJSONFeature(
                        id=edge.id,
                        geometry=GeoJSONGeometry(
                            type="LineString",
                            coordinates=[
                                [source.longitude, source.latitude],
                                [target.longitude, target.latitude],
                            ],
                        ),
                        properties={
                            "feature_type": "edge",
                            "id": edge.id,
                            "source_node_id": edge.source_node_id,
                            "target_node_id": edge.target_node_id,
                            "source_name": source.name,
                            "target_name": target.name,
                            "distance_km": edge.distance_km,
                            "estimated_travel_minutes": edge.estimated_travel_minutes,
                            "road_type": edge.road_type,
                            "is_active": edge.is_active,
                        },
                    )
                )

        metadata = {
            "total_features": len(features),
            "filter": feature_type,
            "data_source": "SIMULATED",
        }

        return GeoJSONFeatureCollection(features=features, metadata=metadata)

