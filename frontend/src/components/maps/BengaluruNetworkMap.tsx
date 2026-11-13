import L from 'leaflet'
import { useEffect, useRef } from 'react'

export interface MapNodePoint {
  id: string
  name: string
  nodeType: 'WAREHOUSE' | 'CUSTOMER' | string
  latitude: number
  longitude: number
  subtitle?: string
  selected?: boolean
}

export interface MapEdgeSegment {
  id: string
  from: [number, number]
  to: [number, number]
  label?: string
  highlighted?: boolean
  dashed?: boolean
}

export interface MapVehicleMarker {
  id: string
  code: string
  status: string
  latitude: number
  longitude: number
  speedKmph?: number | null
  selected?: boolean
}

const BENGALURU_CENTER: [number, number] = [12.9716, 77.5946]

function getVehicleColor(status: string): string {
  switch (status.toUpperCase()) {
    case 'AVAILABLE':
    case 'ARRIVED':
      return '#22C55E'
    case 'IN_TRANSIT':
    case 'EN_ROUTE':
      return '#3B82F6'
    case 'BREAKDOWN':
      return '#EF4444'
    case 'MAINTENANCE':
    case 'PAUSED':
      return '#F97316'
    default:
      return '#C6C6C7'
  }
}

export function BengaluruNetworkMap({
  nodes = [],
  edges = [],
  vehicles = [],
  highlightedPath = [],
  heightClass = 'h-[460px]',
  onSelectNode,
  onSelectVehicle,
}: {
  nodes?: MapNodePoint[]
  edges?: MapEdgeSegment[]
  vehicles?: MapVehicleMarker[]
  highlightedPath?: [number, number][]
  heightClass?: string
  onSelectNode?: (nodeId: string) => void
  onSelectVehicle?: (vehicleId: string) => void
}) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<L.Map | null>(null)
  const layerGroupRef = useRef<L.LayerGroup | null>(null)
  const fittedRef = useRef(false)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = L.map(containerRef.current, {
      center: BENGALURU_CENTER,
      zoom: 12,
      zoomControl: true,
    })

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap &copy; CARTO',
      maxZoom: 18,
    }).addTo(map)

    const layerGroup = L.layerGroup().addTo(map)
    mapRef.current = map
    layerGroupRef.current = layerGroup

    return () => {
      map.remove()
      mapRef.current = null
      layerGroupRef.current = null
      fittedRef.current = false
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    const layerGroup = layerGroupRef.current
    if (!map || !layerGroup) return

    layerGroup.clearLayers()
    const boundsPoints: [number, number][] = []

    edges.forEach((edge) => {
      boundsPoints.push(edge.from, edge.to)
      L.polyline([edge.from, edge.to], {
        color: edge.highlighted ? '#C6F432' : '#4B5563',
        weight: edge.highlighted ? 3.5 : 1.6,
        opacity: edge.highlighted ? 0.95 : 0.6,
        dashArray: edge.dashed ? '6 6' : undefined,
      })
        .bindTooltip(edge.label ?? 'Corridor', { sticky: true })
        .addTo(layerGroup)
    })

    if (highlightedPath.length >= 2) {
      highlightedPath.forEach((pt) => boundsPoints.push(pt))
      L.polyline(highlightedPath, {
        color: '#C6F432',
        weight: 4.5,
        opacity: 1,
      }).addTo(layerGroup)
    }

    nodes.forEach((node) => {
      if (!Number.isFinite(node.latitude) || !Number.isFinite(node.longitude)) return
      boundsPoints.push([node.latitude, node.longitude])
      const isWarehouse = node.nodeType === 'WAREHOUSE'
      const marker = L.circleMarker([node.latitude, node.longitude], {
        radius: isWarehouse ? 9 : 5.5,
        color: node.selected ? '#FFFFFF' : isWarehouse ? '#C6F432' : '#94A3B8',
        weight: node.selected ? 3 : 1.5,
        fillColor: isWarehouse ? '#C6F432' : '#1E293B',
        fillOpacity: isWarehouse ? 0.9 : 0.85,
      })

      marker.bindTooltip(
        `${node.name}${node.subtitle ? ` — ${node.subtitle}` : ''}`,
        { direction: 'top' },
      )
      if (onSelectNode) {
        marker.on('click', () => onSelectNode(node.id))
      }
      marker.addTo(layerGroup)
    })

    vehicles.forEach((v) => {
      if (!Number.isFinite(v.latitude) || !Number.isFinite(v.longitude)) return
      boundsPoints.push([v.latitude, v.longitude])
      const color = getVehicleColor(v.status)
      const marker = L.circleMarker([v.latitude, v.longitude], {
        radius: v.selected ? 9 : 7,
        color: v.selected ? '#C6F432' : '#0B0B0C',
        weight: v.selected ? 3 : 2,
        fillColor: color,
        fillOpacity: 1,
      })
      const speedText =
        v.speedKmph !== null && v.speedKmph !== undefined ? ` • ${v.speedKmph.toFixed(0)} km/h` : ''
      marker.bindTooltip(`${v.code} (${v.status})${speedText}`, { direction: 'top' })
      if (onSelectVehicle) {
        marker.on('click', () => onSelectVehicle(v.id))
      }
      marker.addTo(layerGroup)
    })

    if (!fittedRef.current && boundsPoints.length > 0) {
      const bounds = L.latLngBounds(boundsPoints)
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [28, 28], maxZoom: 13 })
        fittedRef.current = true
      }
    }
  }, [nodes, edges, vehicles, highlightedPath, onSelectNode, onSelectVehicle])

  return (
    <div
      ref={containerRef}
      className={`w-full overflow-hidden rounded-lg border border-surface-container-highest bg-surface-container-lowest ${heightClass}`}
    />
  )
}

