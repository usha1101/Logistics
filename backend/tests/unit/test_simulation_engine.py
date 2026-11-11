import pytest
from datetime import datetime, timezone
import math

from app.models.network import NetworkNode, NodeType
from app.models.simulation import SimulationStatus, SimulationVehicleStatus
from app.services.simulation.clock import SimulationClock
from app.services.simulation.exceptions import InvalidStateTransitionError
from app.services.simulation.movement import (
    advance_vehicle_along_route,
    calculate_bearing,
    calculate_haversine_distance,
    interpolate_position,
)


def test_simulation_clock_tick_and_speed_multiplier():
    t0 = datetime(2026, 11, 11, 10, 0, 0, tzinfo=timezone.utc)
    clock = SimulationClock(current_simulated_time=t0, speed_multiplier=2.0)

    # 10 wall seconds at 2x speed -> 20 simulated seconds
    t1 = clock.tick(wall_seconds=10.0)
    assert (t1 - t0).total_seconds() == 20.0

    # Pause clock: time should not advance
    clock.pause()
    t2 = clock.tick(wall_seconds=10.0)
    assert t2 == t1

    # Resume clock
    clock.resume()
    clock.set_speed(5.0)
    t3 = clock.tick(wall_seconds=10.0)
    assert (t3 - t2).total_seconds() == 50.0


def test_haversine_distance_calculation():
    # Bengaluru Whitefield (12.9698, 77.7499) to Electronic City (12.8399, 77.6770)
    dist = calculate_haversine_distance(12.9698, 77.7499, 12.8399, 77.6770)
    assert 15.0 < dist < 20.0  # Straight-line geodesic distance is ~16.5 km

    # Zero distance for identical points
    assert calculate_haversine_distance(12.9698, 77.7499, 12.9698, 77.7499) == 0.0


def test_bearing_calculation():
    # Due North: lat increases, lon constant
    bearing_north = calculate_bearing(12.0, 77.0, 13.0, 77.0)
    assert round(bearing_north, 1) == 0.0

    # Due East along equator:
    bearing_east = calculate_bearing(0.0, 77.0, 0.0, 78.0)
    assert round(bearing_east, 1) == 90.0

    # Due South: lat decreases, lon constant
    bearing_south = calculate_bearing(12.0, 77.0, 11.0, 77.0)
    assert round(bearing_south, 1) == 180.0

    # Due West along equator:
    bearing_west = calculate_bearing(0.0, 77.0, 0.0, 76.0)
    assert round(bearing_west, 1) == 270.0



def test_interpolate_position():
    lat1, lon1 = 12.0, 77.0
    lat2, lon2 = 14.0, 79.0

    # 0.0 -> origin
    assert interpolate_position(lat1, lon1, lat2, lon2, 0.0) == (12.0, 77.0)
    # 0.5 -> midpoint
    assert interpolate_position(lat1, lon1, lat2, lon2, 0.5) == (13.0, 78.0)
    # 1.0 -> destination
    assert interpolate_position(lat1, lon1, lat2, lon2, 1.0) == (14.0, 79.0)
    # Clamping outside [0, 1]
    assert interpolate_position(lat1, lon1, lat2, lon2, -0.5) == (12.0, 77.0)
    assert interpolate_position(lat1, lon1, lat2, lon2, 1.5) == (14.0, 79.0)


def test_advance_vehicle_single_point_route():
    coords = [(12.9698, 77.7499)]
    res = advance_vehicle_along_route(
        route_coords=coords,
        current_segment=0,
        segment_progress=0.0,
        speed_kmph=45.0,
        delta_seconds=10.0,
    )
    assert res.has_arrived is True
    assert res.new_progress_percentage == 100.0


def test_advance_vehicle_along_multi_segment_route():
    # 3-point route: (12.0, 77.0) -> (12.1, 77.0) -> (12.2, 77.0)
    # Each segment is approx 11.1 km
    coords = [(12.0, 77.0), (12.1, 77.0), (12.2, 77.0)]

    # Advance 5.55 km (approx half of segment 0) at 55.5 km/h for 360 seconds (0.1 hr)
    res1 = advance_vehicle_along_route(
        route_coords=coords,
        current_segment=0,
        segment_progress=0.0,
        speed_kmph=55.5,
        delta_seconds=360.0,  # 5.55 km
    )
    assert res1.has_arrived is False
    assert res1.new_segment_index == 0
    assert 0.45 < res1.new_segment_progress < 0.55
    assert 20.0 < res1.new_progress_percentage < 30.0
    assert res1.new_heading_degrees == 0.0  # Heading North

    # Advance enough to cross into segment 1
    res2 = advance_vehicle_along_route(
        route_coords=coords,
        current_segment=res1.new_segment_index,
        segment_progress=res1.new_segment_progress,
        speed_kmph=80.0,
        delta_seconds=360.0,  # 8 km more -> total ~13.55 km
    )
    assert res2.has_arrived is False
    assert res2.new_segment_index == 1
    assert 0.1 < res2.new_segment_progress < 0.4
    assert 50.0 < res2.new_progress_percentage < 75.0

    # Advance past final point -> vehicle arrives
    res3 = advance_vehicle_along_route(
        route_coords=coords,
        current_segment=res2.new_segment_index,
        segment_progress=res2.new_segment_progress,
        speed_kmph=150.0,
        delta_seconds=1000.0,
    )
    assert res3.has_arrived is True
    assert res3.new_latitude == 12.2
    assert res3.new_longitude == 77.0
    assert res3.new_progress_percentage == 100.0
    assert res3.new_speed_kmph == 0.0


def test_simulation_lifecycle_state_machine(db_session):
    from app.services.simulation.manager import simulation_manager

    # 1. Create
    sim = simulation_manager.create_simulation(db_session, name="Lifecycle Test")
    assert sim.status == SimulationStatus.CREATED.value

    # Cannot pause or stop from CREATED
    with pytest.raises(InvalidStateTransitionError):
        simulation_manager.pause_simulation(sim.id, db_session)
    with pytest.raises(InvalidStateTransitionError):
        simulation_manager.stop_simulation(sim.id, db_session)

    # 2. Start -> RUNNING
    sim = simulation_manager.start_simulation(sim.id, db_session)
    assert sim.status == SimulationStatus.RUNNING.value
    assert sim.started_at is not None

    # Cannot start again while RUNNING
    with pytest.raises(InvalidStateTransitionError):
        simulation_manager.start_simulation(sim.id, db_session)

    # 3. Pause -> PAUSED
    sim = simulation_manager.pause_simulation(sim.id, db_session)
    assert sim.status == SimulationStatus.PAUSED.value
    assert sim.paused_at is not None

    # 4. Resume -> RUNNING
    sim = simulation_manager.resume_simulation(sim.id, db_session)
    assert sim.status == SimulationStatus.RUNNING.value
    assert sim.resumed_at is not None

    # 5. Stop -> STOPPED
    sim = simulation_manager.stop_simulation(sim.id, db_session)
    assert sim.status == SimulationStatus.STOPPED.value
    assert sim.stopped_at is not None

    # 6. Reset -> CREATED
    sim = simulation_manager.reset_simulation(sim.id, db_session)
    assert sim.status == SimulationStatus.CREATED.value
    assert sim.started_at is None


def test_clock_boundary_clamping():
    clock = SimulationClock()
    clock.set_speed(0.01)  # Below 0.1x minimum
    assert clock.speed_multiplier == 0.1

    clock.set_speed(250.0)  # Above 100.0x maximum
    assert clock.speed_multiplier == 100.0


@pytest.mark.anyio
async def test_websocket_manager_connect_disconnect_broadcast():
    from app.services.simulation.manager import WebSocketConnectionManager
    from unittest.mock import AsyncMock

    mgr = WebSocketConnectionManager()
    ws_mock = AsyncMock()

    await mgr.connect("sim-test-room", ws_mock)
    assert "sim-test-room" in mgr._rooms
    assert ws_mock in mgr._rooms["sim-test-room"]

    # Broadcast message
    await mgr.broadcast("sim-test-room", {"type": "TEST_EVENT"})
    ws_mock.send_json.assert_called_once_with({"type": "TEST_EVENT"})

    # Disconnect
    mgr.disconnect("sim-test-room", ws_mock)
    assert "sim-test-room" not in mgr._rooms


def test_step_simulation_when_not_running(db_session):
    from app.services.simulation.manager import simulation_manager

    sim = simulation_manager.create_simulation(db_session, name="Paused Step Test")
    # Step simulation while CREATED should be a safe no-op
    res = simulation_manager.step_simulation(sim.id, db_session, wall_seconds=1.0)
    assert res.status == SimulationStatus.CREATED.value


