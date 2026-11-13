export type NodeType = 'WAREHOUSE' | 'CUSTOMER'
export type NetworkWeightType = 'distance' | 'travel_time'
export type FeatureTypeFilter = 'all' | 'nodes' | 'edges'

export interface NetworkNodeRead {
  id: string
  name: string
  type: string
  node_type: NodeType | string
  latitude: number
  longitude: number
  address: string | null
  region: string | null
  is_active: boolean
  coordinates: [number, number]
  created_at: string | null
  updated_at: string | null
}

export interface NetworkEdgeRead {
  id: string
  source_node_id: string
  target_node_id: string
  distance_km: number
  estimated_travel_minutes: number
  road_type: string | null
  is_active: boolean
  created_at: string | null
  updated_at: string | null
}

export interface NetworkSummary {
  total_nodes: number
  total_warehouses: number
  total_customers: number
  total_connections: number
}

export interface NetworkData {
  name: string
  nodes: NetworkNodeRead[]
  edges: NetworkEdgeRead[]
}

export interface NetworkStateResponse {
  simulation_id: string | null
  network: NetworkData
  summary: NetworkSummary
  data_source: 'SIMULATED' | string
}

export interface GraphMetadata {
  directed: boolean
  total_nodes: number
  total_edges: number
  warehouse_nodes: number
  customer_nodes: number
  density: number
}

export interface GraphNodeData {
  id: string
  name: string
  node_type: NodeType | string
  region: string | null
  latitude: number
  longitude: number
  coordinates: [number, number]
  in_degree: number
  out_degree: number
  degree: number
  is_active: boolean
}

export interface GraphEdgeData {
  id: string
  source_node_id: string
  target_node_id: string
  distance_km: number
  estimated_travel_minutes: number
  road_type: string | null
  is_active: boolean
}

export interface NetworkGraphResponse {
  metadata: GraphMetadata
  nodes: GraphNodeData[]
  edges: GraphEdgeData[]
  is_connected: boolean
  connected_components_count: number
  data_source: 'SIMULATED' | string
}

export interface NetworkAnalyticsResponse {
  total_nodes: number
  total_edges: number
  warehouse_nodes: number
  customer_nodes: number
  connected_components: number
  strongly_connected_components: number | null
  isolated_nodes: number
  isolated_node_ids: string[]
  graph_density: number
  average_node_degree: number
  total_network_distance_km: number
  average_edge_distance_km: number | null
  average_travel_time_minutes: number | null
  network_connectivity_status: 'CONNECTED' | 'DISCONNECTED'
  data_source: 'SIMULATED' | string
}

export interface ValidationItem {
  category: string
  message: string
  entity_id: string | null
  details: Record<string, unknown> | null
}

export interface NetworkValidationResponse {
  validation_status: 'VALID' | 'WARNINGS' | 'INVALID'
  is_valid: boolean
  error_count: number
  warning_count: number
  errors: ValidationItem[]
  warnings: ValidationItem[]
  isolated_nodes: string[]
  disconnected_components: string[][]
  invalid_edge_references: string[]
}

export interface GeoJSONFeature {
  type: 'Feature'
  id: string
  geometry: {
    type: 'Point' | 'LineString'
    coordinates: [number, number] | [number, number][]
  }
  properties: Record<string, unknown>
}

export interface GeoJSONFeatureCollection {
  type: 'FeatureCollection'
  features: GeoJSONFeature[]
  metadata: Record<string, unknown> | null
}

export interface PathNodeDetail {
  id: string
  name: string
  node_type: string
  coordinates: [number, number]
}

export interface PathEdgeDetail {
  id: string
  source_node_id: string
  target_node_id: string
  distance_km: number
  estimated_travel_minutes: number
  road_type: string | null
}

export interface ShortestPathResponse {
  origin_node_id: string
  destination_node_id: string
  origin_node: PathNodeDetail
  destination_node: PathNodeDetail
  weight: string
  algorithm: 'Dijkstra'
  ordered_node_ids: string[]
  ordered_nodes: PathNodeDetail[]
  edge_ids: string[]
  edges: PathEdgeDetail[]
  total_distance_km: number
  estimated_travel_minutes: number | null
  coordinates: [number, number][]
  data_source: 'SIMULATED' | string
}

export interface NodeConnectivityResponse {
  node_id: string
  node_name: string
  node_type: string
  in_degree: number
  out_degree: number
  total_degree: number
  connected_nodes: Array<{
    id: string
    name: string
    node_type: string
    coordinates: [number, number]
    direction: 'OUTGOING' | 'INCOMING' | 'BIDIRECTIONAL'
  }>
  connecting_edges: Array<{
    id: string
    source_node_id: string
    target_node_id: string
    distance_km: number
    estimated_travel_minutes: number
    road_type: string | null
    direction: 'OUTGOING' | 'INCOMING'
  }>
}

