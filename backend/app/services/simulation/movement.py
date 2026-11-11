import math
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class MovementStepResult:
    new_latitude: float
    new_longitude: float
    new_segment_index: int
    new_segment_progress: float
    new_progress_percentage: float
    new_speed_kmph: float
    new_heading_degrees: float
    has_arrived: bool


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points in kilometers."""
    R = 6371.0  # Earth radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate forward azimuth (bearing) from point 1 to point 2 in degrees (0 - 360)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360.0) % 360.0


def interpolate_position(
    lat1: float, lon1: float, lat2: float, lon2: float, fraction: float
) -> Tuple[float, float]:
    """Linearly interpolate position between two coordinates by progress fraction (0.0 - 1.0)."""
    f = max(0.0, min(1.0, fraction))
    lat = lat1 + f * (lat2 - lat1)
    lon = lon1 + f * (lon2 - lon1)
    return round(lat, 6), round(lon, 6)


def advance_vehicle_along_route(
    route_coords: List[Tuple[float, float]],
    current_segment: int,
    segment_progress: float,
    speed_kmph: float,
    delta_seconds: float,
) -> MovementStepResult:
    """Deterministic vehicle progression along a sequence of route coordinate waypoints.

    Coordinates must be [(lat, lon), ...].
    """
    num_coords = len(route_coords)
    if num_coords <= 1:
        # Route is a single point
        lat, lon = route_coords[0] if num_coords == 1 else (0.0, 0.0)
        return MovementStepResult(
            new_latitude=lat,
            new_longitude=lon,
            new_segment_index=0,
            new_segment_progress=1.0,
            new_progress_percentage=100.0,
            new_speed_kmph=0.0,
            new_heading_degrees=0.0,
            has_arrived=True,
        )

    # Compute individual segment lengths and total route length
    num_segments = num_coords - 1
    segment_lengths = [
        calculate_haversine_distance(
            route_coords[i][0], route_coords[i][1],
            route_coords[i + 1][0], route_coords[i + 1][1]
        )
        for i in range(num_segments)
    ]
    total_route_distance = sum(segment_lengths)
    if total_route_distance <= 0:
        total_route_distance = 0.001

    # Distance to move in this tick (km)
    hours = delta_seconds / 3600.0
    distance_to_move = speed_kmph * hours

    seg_idx = min(current_segment, num_segments - 1)
    progress = max(0.0, min(1.0, segment_progress))

    # Advance distance across segments
    while distance_to_move > 0 and seg_idx < num_segments:
        seg_len = segment_lengths[seg_idx]
        if seg_len <= 0:
            seg_idx += 1
            progress = 0.0
            continue

        remaining_in_seg_km = (1.0 - progress) * seg_len
        if distance_to_move < remaining_in_seg_km:
            progress += distance_to_move / seg_len
            distance_to_move = 0.0
        else:
            distance_to_move -= remaining_in_seg_km
            seg_idx += 1
            progress = 0.0

    # Check if arrival reached
    has_arrived = seg_idx >= num_segments
    if has_arrived:
        final_seg = num_segments - 1
        dest_lat, dest_lon = route_coords[-1]
        prev_lat, prev_lon = route_coords[-2]
        heading = calculate_bearing(prev_lat, prev_lon, dest_lat, dest_lon)
        return MovementStepResult(
            new_latitude=dest_lat,
            new_longitude=dest_lon,
            new_segment_index=final_seg,
            new_segment_progress=1.0,
            new_progress_percentage=100.0,
            new_speed_kmph=0.0,
            new_heading_degrees=round(heading, 1),
            has_arrived=True,
        )

    # Currently within seg_idx
    start_lat, start_lon = route_coords[seg_idx]
    end_lat, end_lon = route_coords[seg_idx + 1]

    curr_lat, curr_lon = interpolate_position(start_lat, start_lon, end_lat, end_lon, progress)
    heading = calculate_bearing(start_lat, start_lon, end_lat, end_lon)

    # Compute overall percentage
    distance_covered = sum(segment_lengths[:seg_idx]) + (progress * segment_lengths[seg_idx])
    progress_percentage = min(99.9, max(0.0, (distance_covered / total_route_distance) * 100.0))

    return MovementStepResult(
        new_latitude=curr_lat,
        new_longitude=curr_lon,
        new_segment_index=seg_idx,
        new_segment_progress=round(progress, 4),
        new_progress_percentage=round(progress_percentage, 2),
        new_speed_kmph=speed_kmph,
        new_heading_degrees=round(heading, 1),
        has_arrived=False,
    )

