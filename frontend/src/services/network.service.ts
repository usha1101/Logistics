import { apiClient } from '@/lib/api-client'
import type { OffsetPaginatedResponse } from '@/types/common'
import type {
  FeatureTypeFilter,
  GeoJSONFeatureCollection,
  NetworkAnalyticsResponse,
  NetworkEdgeRead,
  NetworkGraphResponse,
  NetworkNodeRead,
  NetworkStateResponse,
  NetworkValidationResponse,
  NetworkWeightType,
  NodeConnectivityResponse,
  ShortestPathResponse,
} from '@/types/network'

export const networkService = {
  async getGeoJson(params?: {
    feature_type?: FeatureTypeFilter
    only_active?: boolean
  }): Promise<GeoJSONFeatureCollection> {
    const { data } = await apiClient.get<GeoJSONFeatureCollection>('/network/geojson', { params })
    return data
  },

  async getGraph(onlyActive = true): Promise<NetworkGraphResponse> {
    const { data } = await apiClient.get<NetworkGraphResponse>('/network/graph', {
      params: { only_active: onlyActive },
    })
    return data
  },

  async getAnalytics(onlyActive = true): Promise<NetworkAnalyticsResponse> {
    const { data } = await apiClient.get<NetworkAnalyticsResponse>('/network/analytics', {
      params: { only_active: onlyActive },
    })
    return data
  },

  async getValidation(): Promise<NetworkValidationResponse> {
    const { data } = await apiClient.get<NetworkValidationResponse>('/network/validate')
    return data
  },

  async getState(): Promise<NetworkStateResponse> {
    const { data } = await apiClient.get<NetworkStateResponse>('/network/state')
    return data
  },

  async getShortestPath(params: {
    origin_node_id: string
    destination_node_id: string
    weight?: NetworkWeightType
    directed?: boolean
  }): Promise<ShortestPathResponse> {
    const { data } = await apiClient.get<ShortestPathResponse>('/network/shortest-path', {
      params,
    })
    return data
  },

  async getNodeConnections(nodeId: string, onlyActive = true): Promise<NodeConnectivityResponse> {
    const { data } = await apiClient.get<NodeConnectivityResponse>(
      `/network/nodes/${nodeId}/connections`,
      { params: { only_active: onlyActive } },
    )
    return data
  },

  async listNodes(params?: {
    node_type?: 'WAREHOUSE' | 'CUSTOMER'
    region?: string
    is_active?: boolean
    skip?: number
    limit?: number
  }): Promise<OffsetPaginatedResponse<NetworkNodeRead>> {
    const { data } = await apiClient.get<OffsetPaginatedResponse<NetworkNodeRead>>(
      '/network/nodes',
      { params },
    )
    return data
  },

  async listEdges(params?: {
    source_node_id?: string
    target_node_id?: string
    is_active?: boolean
    skip?: number
    limit?: number
  }): Promise<OffsetPaginatedResponse<NetworkEdgeRead>> {
    const { data } = await apiClient.get<OffsetPaginatedResponse<NetworkEdgeRead>>(
      '/network/edges',
      { params },
    )
    return data
  },
}

