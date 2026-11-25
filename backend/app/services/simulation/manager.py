import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from fastapi import WebSocket
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.disruption import Disruption, DisruptionStatus, DisruptionType
from app.models.network import NetworkEdge, NetworkNode
from app.models.order import Order, OrderStatus
from app.models.simulation import (
    Simulation,
    SimulationEvent,
    SimulationEventType,
    SimulationStatus,
    SimulationTelemetry,
    SimulationVehicleState,
    SimulationVehicleStatus,
)
from app.models.vehicle import Vehicle, VehicleStatus
from app.models.warehouse import Warehouse
from app.services.network_graph_service import NetworkGraphService, PathNotFoundError
from app.services.simulation.clock import SimulationClock
from app.services.simulation.events import create_simulation_event
from app.services.simulation.exceptions import (
    InvalidStateTransitionError,
    RouteCalculationError,
    SimulationNotFoundError,
    VehicleAlreadyAssignedError,
    VehicleUnavailableError,
)
from app.services.simulation.movement import advance_vehicle_along_route

logger = logging.getLogger("simulation_manager")

# Baseline average driving speed in Bengaluru urban network (km/h)
DEFAULT_VEHICLE_SPEED_KMPH = 45.0


from app.core.broker import broker as ws_manager, BaseBroadcastBroker, LocalBroadcastBroker

# Alias for backward compatibility with existing imports
WebSocketConnectionManager = LocalBroadcastBroker


class SimulationManager:
    """Orchestrates simulation lifecycles, vehicle routing, background ticks, and telemetry generation."""

    def __init__(self):
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._clocks: Dict[str, SimulationClock] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the running FastAPI application event loop."""
        self._loop = loop

    def get_event_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        if self._loop and self._loop.is_running():
            return self._loop
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    def get_clock(self, simulation: Simulation) -> SimulationClock:
        if simulation.id not in self._clocks:
            self._clocks[simulation.id] = SimulationClock(
                current_simulated_time=simulation.simulated_time,
                speed_multiplier=simulation.simulation_speed_multiplier,
            )
        return self._clocks[simulation.id]

    # =========================================================================
    # LIFECYCLE MANAGEMENT
    # =========================================================================

    def create_simulation(
        self,
        db: Session,
        name: str = "Bengaluru Logistics Simulation",
        seed: int = 42,
        speed_multiplier: float = 1.0,
        configuration: Optional[Dict[str, Any]] = None,
        created_by_user_id: Optional[str] = None,
    ) -> Simulation:
        sim = Simulation(
            name=name,
            seed=seed,
            status=SimulationStatus.CREATED.value,
            simulation_speed_multiplier=speed_multiplier,
            configuration=configuration or {},
            created_by_user_id=created_by_user_id,
        )
        db.add(sim)
        db.commit()
        db.refresh(sim)
        return sim

    def start_simulation(self, simulation_id: str, db: Session) -> Simulation:
        sim = db.execute(select(Simulation).where(Simulation.id == simulation_id)).scalar_one_or_none()
        if not sim:
            raise SimulationNotFoundError(f"Simulation '{simulation_id}' not found")

        if sim.status not in (SimulationStatus.CREATED.value, SimulationStatus.PAUSED.value):
            raise InvalidStateTransitionError(
                f"Cannot start simulation from status '{sim.status}'. Allowed statuses: CREATED, PAUSED"
            )

        now = datetime.now(timezone.utc)
        is_resume = sim.status == SimulationStatus.PAUSED.value

        sim.status = SimulationStatus.RUNNING.value
        if not sim.started_at:
            sim.started_at = now
        if is_resume:
            sim.resumed_at = now
        if not sim.simulated_time:
            sim.simulated_time = now

        clock = self.get_clock(sim)
        clock.resume()

        event_type = SimulationEventType.SIMULATION_RESUMED if is_resume else SimulationEventType.SIMULATION_STARTED
        create_simulation_event(
            db=db,
            simulation_id=sim.id,
            event_type=event_type,
            simulated_timestamp=sim.simulated_time,
            event_data={"speed_multiplier": sim.simulation_speed_multiplier},
        )
        db.commit()
        db.refresh(sim)

        # Notify via WebSocket
        self._safe_async_broadcast(sim.id, {
            "event": event_type.value,
            "simulation_id": sim.id,
            "status": sim.status,
            "simulated_time": sim.simulated_time.isoformat(),
        })

        # Launch background loop if not already running
        self._ensure_background_loop(sim.id)
        return sim

    def pause_simulation(self, simulation_id: str, db: Session) -> Simulation:
        sim = db.execute(select(Simulation).where(Simulation.id == simulation_id)).scalar_one_or_none()
        if not sim:
            raise SimulationNotFoundError(f"Simulation '{simulation_id}' not found")

        if sim.status != SimulationStatus.RUNNING.value:
            raise InvalidStateTransitionError(
                f"Cannot pause simulation from status '{sim.status}'. Allowed status: RUNNING"
            )

        now = datetime.now(timezone.utc)
        sim.status = SimulationStatus.PAUSED.value
        sim.paused_at = now

        clock = self.get_clock(sim)
        clock.pause()

        create_simulation_event(
            db=db,
            simulation_id=sim.id,
            event_type=SimulationEventType.SIMULATION_PAUSED,
            simulated_timestamp=sim.simulated_time,
        )
        db.commit()
        db.refresh(sim)

        # Cancel background loop
        self._stop_background_loop(sim.id)

        self._safe_async_broadcast(sim.id, {
            "event": SimulationEventType.SIMULATION_PAUSED.value,
            "simulation_id": sim.id,
            "status": sim.status,
        })
        return sim

    def resume_simulation(self, simulation_id: str, db: Session) -> Simulation:
        return self.start_simulation(simulation_id, db)

    def stop_simulation(self, simulation_id: str, db: Session) -> Simulation:
        sim = db.execute(select(Simulation).where(Simulation.id == simulation_id)).scalar_one_or_none()
        if not sim:
            raise SimulationNotFoundError(f"Simulation '{simulation_id}' not found")

        if sim.status not in (SimulationStatus.RUNNING.value, SimulationStatus.PAUSED.value):
            raise InvalidStateTransitionError(
                f"Cannot stop simulation from status '{sim.status}'. Allowed statuses: RUNNING, PAUSED"
            )

        now = datetime.now(timezone.utc)
        sim.status = SimulationStatus.STOPPED.value
        sim.stopped_at = now

        self._stop_background_loop(sim.id)

        create_simulation_event(
            db=db,
            simulation_id=sim.id,
            event_type=SimulationEventType.SIMULATION_STOPPED,
            simulated_timestamp=sim.simulated_time,
        )
        db.commit()
        db.refresh(sim)

        self._safe_async_broadcast(sim.id, {
            "event": SimulationEventType.SIMULATION_STOPPED.value,
            "simulation_id": sim.id,
            "status": sim.status,
        })
        return sim

    def reset_simulation(self, simulation_id: str, db: Session) -> Simulation:
        sim = db.execute(select(Simulation).where(Simulation.id == simulation_id)).scalar_one_or_none()
        if not sim:
            raise SimulationNotFoundError(f"Simulation '{simulation_id}' not found")

        if sim.status not in (SimulationStatus.STOPPED.value, SimulationStatus.COMPLETED.value):
            raise InvalidStateTransitionError(
                f"Cannot reset simulation from status '{sim.status}'. Allowed statuses: STOPPED, COMPLETED"
            )

        self._stop_background_loop(sim.id)

        # Reset all vehicle states back to origin
        nodes_map = {n.id: n for n in db.execute(select(NetworkNode)).scalars().all()}
        for vs in sim.vehicle_states:
            origin_node = nodes_map.get(vs.origin_node_id)
            if origin_node:
                vs.current_latitude = origin_node.latitude
                vs.current_longitude = origin_node.longitude
            vs.current_route_segment = 0
            vs.segment_progress = 0.0
            vs.progress_percentage = 0.0
            vs.current_speed_kmph = 0.0
            vs.status = SimulationVehicleStatus.QUEUED.value
            vs.simulated_departure_time = None
            vs.actual_arrival_time = None

        sim.status = SimulationStatus.CREATED.value
        sim.started_at = None
        sim.paused_at = None
        sim.resumed_at = None
        sim.stopped_at = None
        sim.simulated_time = None

        if sim.id in self._clocks:
            del self._clocks[sim.id]

        create_simulation_event(
            db=db,
            simulation_id=sim.id,
            event_type=SimulationEventType.SIMULATION_RESET,
        )
        db.commit()
        db.refresh(sim)

        self._safe_async_broadcast(sim.id, {
            "event": SimulationEventType.SIMULATION_RESET.value,
            "simulation_id": sim.id,
            "status": sim.status,
        })
        return sim

    def update_speed(self, simulation_id: str, speed_multiplier: float, db: Session) -> Simulation:
        sim = db.execute(select(Simulation).where(Simulation.id == simulation_id)).scalar_one_or_none()
        if not sim:
            raise SimulationNotFoundError(f"Simulation '{simulation_id}' not found")

        sim.simulation_speed_multiplier = max(0.1, min(100.0, float(speed_multiplier)))
        if sim.id in self._clocks:
            self._clocks[sim.id].set_speed(sim.simulation_speed_multiplier)

        create_simulation_event(
            db=db,
            simulation_id=sim.id,
            event_type=SimulationEventType.SIMULATION_SPEED_CHANGED,
            simulated_timestamp=sim.simulated_time,
            event_data={"new_speed_multiplier": sim.simulation_speed_multiplier},
        )
        db.commit()
        db.refresh(sim)

        self._safe_async_broadcast(sim.id, {
            "event": SimulationEventType.SIMULATION_SPEED_CHANGED.value,
            "simulation_id": sim.id,
            "speed_multiplier": sim.simulation_speed_multiplier,
        })
        return sim

    # =========================================================================
    # VEHICLE ASSIGNMENT & ROUTING
    # =========================================================================

    def add_vehicle_to_simulation(
        self,
        simulation_id: str,
        vehicle_id: str,
        origin_node_id: str,
        destination_node_id: str,
        db: Session,
    ) -> SimulationVehicleState:
        sim = db.execute(select(Simulation).where(Simulation.id == simulation_id)).scalar_one_or_none()
        if not sim:
            raise SimulationNotFoundError(f"Simulation '{simulation_id}' not found")

        # 1. Validate vehicle
        veh = db.execute(select(Vehicle).where(Vehicle.id == vehicle_id)).scalar_one_or_none()
        if not veh:
            raise VehicleUnavailableError(f"Vehicle '{vehicle_id}' not found")
        if not veh.is_active:
            raise VehicleUnavailableError(f"Vehicle '{veh.vehicle_code}' is inactive")
        if veh.status in (VehicleStatus.BREAKDOWN.value, VehicleStatus.MAINTENANCE.value, VehicleStatus.OFFLINE.value):
            raise VehicleUnavailableError(f"Vehicle '{veh.vehicle_code}' unavailable due to status '{veh.status}'")

        # 2. Check duplicate vehicle in simulation
        existing = db.execute(
            select(SimulationVehicleState).where(
                SimulationVehicleState.simulation_id == simulation_id,
                SimulationVehicleState.vehicle_id == vehicle_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise VehicleAlreadyAssignedError(
                f"Vehicle '{veh.vehicle_code}' is already assigned to simulation '{simulation_id}'"
            )

        # 3. Validate origin and destination nodes
        nodes = list(db.execute(select(NetworkNode).where(NetworkNode.is_active.is_(True))).scalars().all())
        nodes_map = {n.id: n for n in nodes}
        if origin_node_id not in nodes_map:
            raise RouteCalculationError(f"Origin node '{origin_node_id}' not found or inactive")
        if destination_node_id not in nodes_map:
            raise RouteCalculationError(f"Destination node '{destination_node_id}' not found or inactive")

        # 4. Calculate route via NetworkGraphService (Stage 7)
        edges = list(db.execute(select(NetworkEdge).where(NetworkEdge.is_active.is_(True))).scalars().all())

        try:
            route_result = NetworkGraphService.calculate_shortest_path(
                nodes=nodes,
                edges=edges,
                origin_node_id=origin_node_id,
                destination_node_id=destination_node_id,
                weight="distance",
                directed=False,  # Allow bidirectional road navigation for simulated vehicles
                only_active=True,
            )
        except PathNotFoundError as e:
            raise RouteCalculationError(str(e))

        origin_node = nodes_map[origin_node_id]
        dest_node = nodes_map[destination_node_id]

        # 5. Initialize vehicle state record
        v_state = SimulationVehicleState(
            simulation_id=simulation_id,
            vehicle_id=vehicle_id,
            origin_node_id=origin_node_id,
            destination_node_id=destination_node_id,
            route_node_ids=route_result.ordered_node_ids,
            current_route_segment=0,
            segment_progress=0.0,
            progress_percentage=0.0,
            current_latitude=origin_node.latitude,
            current_longitude=origin_node.longitude,
            current_speed_kmph=0.0,
            heading_degrees=0.0,
            status=SimulationVehicleStatus.QUEUED.value,
        )
        db.add(v_state)

        create_simulation_event(
            db=db,
            simulation_id=simulation_id,
            vehicle_id=vehicle_id,
            event_type=SimulationEventType.VEHICLE_ASSIGNED,
            event_data={
                "vehicle_code": veh.vehicle_code,
                "origin_node": origin_node.name,
                "destination_node": dest_node.name,
                "route_length_km": route_result.total_distance_km,
                "route_nodes_count": len(route_result.ordered_node_ids),
            },
        )
        db.commit()
        db.refresh(v_state)

        return v_state

    def load_eligible_orders(
        self,
        simulation_id: str,
        db: Session,
        order_ids: Optional[List[str]] = None,
        max_orders: int = 10,
    ) -> Dict[str, Any]:
        """
        Safely loads eligible production orders into a simulation as simulated vehicle runs.
        - Does NOT modify production orders or vehicle states in place.
        - Selects active/available vehicles matching capacity and warehouse.
        - Maps order warehouse and delivery coordinates to nearest network nodes.
        - Calculates deterministic shortest routes.
        - Avoids assigning the same vehicle or order twice within the simulation run.
        """
        import math

        sim = db.execute(select(Simulation).where(Simulation.id == simulation_id)).scalar_one_or_none()
        if not sim:
            raise SimulationNotFoundError(f"Simulation '{simulation_id}' not found")

        # 1. Fetch eligible orders
        # Eligible statuses: IN_TRANSIT, READY_FOR_DISPATCH, DISPATCHED, CONFIRMED, PROCESSING
        order_query = select(Order).where(
            Order.status.in_([
                OrderStatus.IN_TRANSIT.value,
                OrderStatus.READY_FOR_DISPATCH.value,
                OrderStatus.DISPATCHED.value,
                OrderStatus.CONFIRMED.value,
                OrderStatus.PROCESSING.value,
            ])
        )
        if order_ids:
            order_query = order_query.where(Order.id.in_(order_ids))

        orders = list(db.execute(order_query).scalars().all())

        # Already assigned vehicles in this simulation
        existing_vehicle_ids = {
            vs.vehicle_id for vs in sim.vehicle_states
        }

        # Warehouses map to resolve network_node_id
        warehouses_map = {w.id: w for w in db.execute(select(Warehouse)).scalars().all()}

        # Network nodes
        active_nodes = list(db.execute(select(NetworkNode).where(NetworkNode.is_active.is_(True))).scalars().all())
        if not active_nodes:
            raise RouteCalculationError("No active network nodes available for simulation routing")

        def _distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            R = 6371.0
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
            return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

        # Vehicles pool
        all_vehicles = list(db.execute(select(Vehicle).where(Vehicle.is_active.is_(True))).scalars().all())
        available_vehicles = [
            v for v in all_vehicles
            if v.id not in existing_vehicle_ids
            and v.status not in (VehicleStatus.BREAKDOWN.value, VehicleStatus.MAINTENANCE.value, VehicleStatus.OFFLINE.value)
        ]

        loaded_items = []
        skipped_orders = []

        for ord_obj in orders:
            if len(loaded_items) >= max_orders:
                break

            # Identify origin warehouse node
            wh = warehouses_map.get(ord_obj.warehouse_id)
            if not wh or not wh.network_node_id:
                skipped_orders.append(f"{ord_obj.order_number}: Warehouse network node not mapped")
                continue
            origin_node_id = wh.network_node_id

            # Identify destination customer node
            customer_nodes = [n for n in active_nodes if n.node_type != "WAREHOUSE"]
            candidate_nodes = customer_nodes if customer_nodes else active_nodes
            dest_node = min(
                candidate_nodes,
                key=lambda n: _distance(ord_obj.delivery_latitude, ord_obj.delivery_longitude, n.latitude, n.longitude),
            )
            destination_node_id = dest_node.id

            if origin_node_id == destination_node_id:
                skipped_orders.append(f"{ord_obj.order_number}: Origin and destination nodes identical")
                continue

            # Select suitable vehicle
            candidate_veh = None
            if ord_obj.assigned_vehicle_id and ord_obj.assigned_vehicle_id not in existing_vehicle_ids:
                matching = next((v for v in available_vehicles if v.id == ord_obj.assigned_vehicle_id), None)
                if matching and matching.capacity_kg >= ord_obj.total_weight_kg:
                    candidate_veh = matching

            if not candidate_veh:
                # Find best available vehicle with sufficient capacity
                valid_pool = [
                    v for v in available_vehicles
                    if v.id not in existing_vehicle_ids and v.capacity_kg >= ord_obj.total_weight_kg
                ]
                if valid_pool:
                    # Pick vehicle closest to warehouse or matching home warehouse
                    home_matches = [v for v in valid_pool if v.home_warehouse_id == ord_obj.warehouse_id]
                    candidate_veh = home_matches[0] if home_matches else valid_pool[0]

            if not candidate_veh:
                skipped_orders.append(f"{ord_obj.order_number}: No available vehicle with capacity >= {ord_obj.total_weight_kg}kg")
                continue

            # Assign vehicle to simulation route
            try:
                v_state = self.add_vehicle_to_simulation(
                    simulation_id=simulation_id,
                    vehicle_id=candidate_veh.id,
                    origin_node_id=origin_node_id,
                    destination_node_id=destination_node_id,
                    db=db,
                )
                existing_vehicle_ids.add(candidate_veh.id)
                available_vehicles = [v for v in available_vehicles if v.id != candidate_veh.id]

                nodes_dict = {n.id: n.name for n in active_nodes}
                loaded_items.append({
                    "order_id": ord_obj.id,
                    "order_number": ord_obj.order_number,
                    "vehicle_id": candidate_veh.id,
                    "vehicle_code": candidate_veh.vehicle_code,
                    "origin_node_id": origin_node_id,
                    "origin_node_name": nodes_dict.get(origin_node_id, "Warehouse Hub"),
                    "destination_node_id": destination_node_id,
                    "destination_node_name": nodes_dict.get(destination_node_id, "Customer Node"),
                    "route_distance_km": round(_distance(
                        next(n.latitude for n in active_nodes if n.id == origin_node_id),
                        next(n.longitude for n in active_nodes if n.id == origin_node_id),
                        dest_node.latitude,
                        dest_node.longitude,
                    ), 1),
                })
            except Exception as e:
                skipped_orders.append(f"{ord_obj.order_number}: Routing error ({str(e)})")

        return {
            "simulation_id": simulation_id,
            "loaded_count": len(loaded_items),
            "assignments": loaded_items,
            "skipped_orders": skipped_orders,
        }

    # =========================================================================
    # SIMULATION MOVEMENT STEP (TICK)
    # =========================================================================

    def step_simulation(self, simulation_id: str, db: Session, wall_seconds: float = 1.0) -> Optional[Simulation]:
        """Execute one simulation step: advances simulated time, moves vehicles, writes telemetry."""
        sim = db.execute(select(Simulation).where(Simulation.id == simulation_id)).scalar_one_or_none()
        if not sim or sim.status != SimulationStatus.RUNNING.value:
            return sim

        clock = self.get_clock(sim)
        simulated_now = clock.tick(wall_seconds)
        sim.simulated_time = simulated_now

        # Load active nodes for coordinate lookups
        nodes_map = {n.id: n for n in db.execute(select(NetworkNode)).scalars().all()}
        all_arrived = True
        has_vehicles = len(sim.vehicle_states) > 0

        # Query active disruptions that affect this simulation or its vehicles
        active_breakdowns: Set[str] = set()
        active_disruptions = list(
            db.execute(
                select(Disruption).where(
                    Disruption.status.in_([DisruptionStatus.ACTIVE.value, DisruptionStatus.DETECTED.value]),
                    or_(
                        Disruption.simulation_id == sim.id,
                        Disruption.simulation_id.is_(None),
                    ),
                    Disruption.disruption_type == DisruptionType.VEHICLE_BREAKDOWN.value,
                )
            ).scalars().all()
        )
        for d in active_disruptions:
            if d.affected_vehicle_id:
                active_breakdowns.add(d.affected_vehicle_id)

        for vs in sim.vehicle_states:
            if vs.status == SimulationVehicleStatus.ARRIVED.value:
                continue

            # Check if vehicle is experiencing a simulated breakdown disruption
            if vs.vehicle_id in active_breakdowns:
                if vs.status != SimulationVehicleStatus.BREAKDOWN.value:
                    vs.status = SimulationVehicleStatus.BREAKDOWN.value
                    vs.current_speed_kmph = 0.0
                    create_simulation_event(
                        db=db,
                        simulation_id=sim.id,
                        vehicle_id=vs.vehicle_id,
                        event_type=SimulationEventType.VEHICLE_POSITION_UPDATED,
                        simulated_timestamp=simulated_now,
                        event_data={"status": "BREAKDOWN", "reason": "Simulated vehicle breakdown fault"},
                    )
                    self._safe_async_broadcast(sim.id, {
                        "event": SimulationEventType.VEHICLE_POSITION_UPDATED.value,
                        "simulation_id": sim.id,
                        "vehicle_id": vs.vehicle_id,
                        "status": "BREAKDOWN",
                        "speed_kmph": 0.0,
                        "latitude": vs.current_latitude,
                        "longitude": vs.current_longitude,
                        "progress_percentage": vs.progress_percentage,
                        "heading_degrees": vs.heading_degrees,
                        "simulated_time": simulated_now.isoformat(),
                    })
                continue

            # If vehicle was in breakdown but disruption is resolved, recover to EN_ROUTE
            if vs.status == SimulationVehicleStatus.BREAKDOWN.value and vs.vehicle_id not in active_breakdowns:
                vs.status = SimulationVehicleStatus.EN_ROUTE.value

            all_arrived = False

            # If vehicle was queued, depart now
            if vs.status == SimulationVehicleStatus.QUEUED.value:
                vs.status = SimulationVehicleStatus.EN_ROUTE.value
                vs.simulated_departure_time = simulated_now
                create_simulation_event(
                    db=db,
                    simulation_id=sim.id,
                    vehicle_id=vs.vehicle_id,
                    event_type=SimulationEventType.VEHICLE_DEPARTED,
                    simulated_timestamp=simulated_now,
                )

            # Build route coordinate list [(lat, lon), ...]
            route_coords = [
                (nodes_map[nid].latitude, nodes_map[nid].longitude)
                for nid in vs.route_node_ids
                if nid in nodes_map
            ]

            effective_speed = DEFAULT_VEHICLE_SPEED_KMPH * sim.simulation_speed_multiplier

            movement_res = advance_vehicle_along_route(
                route_coords=route_coords,
                current_segment=vs.current_route_segment,
                segment_progress=vs.segment_progress,
                speed_kmph=DEFAULT_VEHICLE_SPEED_KMPH,
                delta_seconds=wall_seconds * sim.simulation_speed_multiplier,
            )

            vs.current_latitude = movement_res.new_latitude
            vs.current_longitude = movement_res.new_longitude
            vs.current_route_segment = movement_res.new_segment_index
            vs.segment_progress = movement_res.new_segment_progress
            vs.progress_percentage = movement_res.new_progress_percentage
            vs.current_speed_kmph = movement_res.new_speed_kmph
            vs.heading_degrees = movement_res.new_heading_degrees

            # Record telemetry point
            telem = SimulationTelemetry(
                simulation_id=sim.id,
                vehicle_id=vs.vehicle_id,
                latitude=movement_res.new_latitude,
                longitude=movement_res.new_longitude,
                speed_kmph=movement_res.new_speed_kmph,
                heading_degrees=movement_res.new_heading_degrees,
                recorded_at=simulated_now,
                source="SIMULATION",
            )
            db.add(telem)

            # Emit position updated event
            create_simulation_event(
                db=db,
                simulation_id=sim.id,
                vehicle_id=vs.vehicle_id,
                event_type=SimulationEventType.VEHICLE_POSITION_UPDATED,
                simulated_timestamp=simulated_now,
                event_data={
                    "latitude": movement_res.new_latitude,
                    "longitude": movement_res.new_longitude,
                    "progress_percentage": movement_res.new_progress_percentage,
                    "speed_kmph": movement_res.new_speed_kmph,
                    "heading_degrees": movement_res.new_heading_degrees,
                },
            )

            # Broadcast position update to WebSockets
            self._safe_async_broadcast(sim.id, {
                "event": SimulationEventType.VEHICLE_POSITION_UPDATED.value,
                "simulation_id": sim.id,
                "vehicle_id": vs.vehicle_id,
                "latitude": movement_res.new_latitude,
                "longitude": movement_res.new_longitude,
                "progress_percentage": movement_res.new_progress_percentage,
                "speed_kmph": movement_res.new_speed_kmph,
                "heading_degrees": movement_res.new_heading_degrees,
                "simulated_time": simulated_now.isoformat(),
            })

            # Check arrival
            if movement_res.has_arrived:
                vs.status = SimulationVehicleStatus.ARRIVED.value
                vs.actual_arrival_time = simulated_now
                vs.current_speed_kmph = 0.0

                create_simulation_event(
                    db=db,
                    simulation_id=sim.id,
                    vehicle_id=vs.vehicle_id,
                    event_type=SimulationEventType.VEHICLE_ARRIVED,
                    simulated_timestamp=simulated_now,
                )
                self._safe_async_broadcast(sim.id, {
                    "event": SimulationEventType.VEHICLE_ARRIVED.value,
                    "simulation_id": sim.id,
                    "vehicle_id": vs.vehicle_id,
                    "simulated_time": simulated_now.isoformat(),
                })

        # Check if entire simulation completed (all vehicles have arrived)
        all_arrived = all(v.status == SimulationVehicleStatus.ARRIVED.value for v in sim.vehicle_states)
        if has_vehicles and all_arrived:
            sim.status = SimulationStatus.COMPLETED.value
            sim.stopped_at = datetime.now(timezone.utc)
            self._stop_background_loop(sim.id)

            create_simulation_event(
                db=db,
                simulation_id=sim.id,
                event_type=SimulationEventType.SIMULATION_COMPLETED,
                simulated_timestamp=simulated_now,
            )
            self._safe_async_broadcast(sim.id, {
                "event": SimulationEventType.SIMULATION_COMPLETED.value,
                "simulation_id": sim.id,
                "status": sim.status,
            })

        db.commit()
        db.refresh(sim)
        return sim

    # =========================================================================
    # BACKGROUND RUNTIME LOOP
    # =========================================================================

    def _ensure_background_loop(self, simulation_id: str) -> None:
        if simulation_id in self._running_tasks and not self._running_tasks[simulation_id].done():
            return  # Already running

        loop = self.get_event_loop()
        if not loop:
            return

        try:
            # Check if we are inside the running loop thread
            running = None
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                pass

            if running is loop:
                task = loop.create_task(self._background_simulation_task(simulation_id))
            else:
                task = asyncio.run_coroutine_threadsafe(self._background_simulation_task(simulation_id), loop)
            self._running_tasks[simulation_id] = task
        except Exception as e:
            logger.warning(f"Could not launch background task for simulation '{simulation_id}': {e}")

    def _stop_background_loop(self, simulation_id: str) -> None:
        if simulation_id in self._running_tasks:
            task = self._running_tasks.pop(simulation_id)
            if not task.done():
                task.cancel()

    async def _background_simulation_task(self, simulation_id: str) -> None:
        """Periodic background ticker advancing simulation time and vehicle states."""
        logger.info(f"Background task started for simulation '{simulation_id}'")
        try:
            while True:
                await asyncio.sleep(1.0)
                # Run step with independent DB session
                with SessionLocal() as db:
                    sim = self.step_simulation(simulation_id, db=db, wall_seconds=1.0)
                    if not sim or sim.status != SimulationStatus.RUNNING.value:
                        break
        except asyncio.CancelledError:
            logger.info(f"Background task cancelled for simulation '{simulation_id}'")
        except Exception as e:
            logger.error(f"Error in background simulation task for '{simulation_id}': {e}", exc_info=True)
            with SessionLocal() as db:
                sim = db.execute(select(Simulation).where(Simulation.id == simulation_id)).scalar_one_or_none()
                if sim:
                    sim.status = SimulationStatus.FAILED.value
                    create_simulation_event(
                        db=db,
                        simulation_id=sim.id,
                        event_type=SimulationEventType.SIMULATION_FAILED,
                        event_data={"error": str(e)},
                    )
                    db.commit()

    def _safe_async_broadcast(self, simulation_id: str, message: Dict[str, Any]) -> None:
        loop = self.get_event_loop()
        if not loop:
            return

        try:
            running = None
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                pass

            if running is loop:
                loop.create_task(ws_manager.broadcast(simulation_id, message))
            else:
                asyncio.run_coroutine_threadsafe(ws_manager.broadcast(simulation_id, message), loop)
        except Exception as e:
            logger.warning(f"Failed to schedule async broadcast on simulation '{simulation_id}': {e}")


# Global singleton instance
simulation_manager = SimulationManager()
