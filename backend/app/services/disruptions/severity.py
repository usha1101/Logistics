from typing import Any, Dict, Optional
from app.models.disruption import DisruptionSeverity, DisruptionType


def calculate_severity(
    disruption_type: DisruptionType | str,
    parameters: Optional[Dict[str, Any]] = None,
    affected_resource_context: Optional[Dict[str, Any]] = None,
) -> DisruptionSeverity:
    """
    Deterministically computes disruption severity based on explicit business rules:
    
    1. VEHICLE_BREAKDOWN:
       - If payload/load > 1000 kg OR vehicle carries urgent/high priority orders: CRITICAL
       - If payload/load > 500 kg: HIGH
       - If vehicle is empty / idling: LOW
       - Default: MEDIUM

    2. TRAFFIC_CONGESTION:
       - speed_reduction_pct >= 70 OR delay_minutes >= 60: CRITICAL
       - speed_reduction_pct >= 40 OR delay_minutes >= 30: HIGH
       - speed_reduction_pct >= 20 OR delay_minutes >= 15: MEDIUM
       - Default / minor delay: LOW

    3. WAREHOUSE_SHUTDOWN:
       - capacity_utilization_pct >= 80 OR active_orders >= 20: CRITICAL
       - capacity_utilization_pct >= 50 OR active_orders >= 10: HIGH
       - active_orders > 0: MEDIUM
       - Default / empty warehouse: LOW

    4. DEMAND_SURGE:
       - surge_multiplier >= 3.0 OR extra_orders >= 50: CRITICAL
       - surge_multiplier >= 2.0 OR extra_orders >= 25: HIGH
       - surge_multiplier >= 1.3 OR extra_orders >= 10: MEDIUM
       - Default: LOW

    5. DELIVERY_DELAY:
       - delay_minutes >= 120 OR urgent_order: CRITICAL
       - delay_minutes >= 60: HIGH
       - delay_minutes >= 30: MEDIUM
       - Default: LOW
    """
    params = parameters or {}
    ctx = affected_resource_context or {}

    d_type = disruption_type.value if isinstance(disruption_type, DisruptionType) else disruption_type

    if d_type == DisruptionType.VEHICLE_BREAKDOWN.value:
        load = float(params.get("current_load_kg", ctx.get("current_load_kg", 0.0) or 0.0))
        has_urgent = bool(params.get("has_urgent_orders", ctx.get("has_urgent_orders", False)))
        is_idle = bool(params.get("is_idle", ctx.get("is_idle", False)))

        if has_urgent or load > 1000.0:
            return DisruptionSeverity.CRITICAL
        if load > 500.0:
            return DisruptionSeverity.HIGH
        if is_idle or load == 0.0:
            return DisruptionSeverity.LOW
        return DisruptionSeverity.MEDIUM

    elif d_type == DisruptionType.TRAFFIC_CONGESTION.value:
        speed_red = float(params.get("speed_reduction_pct", 0.0))
        delay_mins = float(params.get("delay_minutes", 0.0))

        if speed_red >= 70.0 or delay_mins >= 60.0:
            return DisruptionSeverity.CRITICAL
        if speed_red >= 40.0 or delay_mins >= 30.0:
            return DisruptionSeverity.HIGH
        if speed_red >= 20.0 or delay_mins >= 15.0:
            return DisruptionSeverity.MEDIUM
        return DisruptionSeverity.LOW

    elif d_type == DisruptionType.WAREHOUSE_SHUTDOWN.value:
        utilization = float(params.get("capacity_utilization_pct", ctx.get("capacity_utilization_pct", 0.0) or 0.0))
        active_orders = int(params.get("active_orders", ctx.get("active_orders", 0) or 0))

        if utilization >= 80.0 or active_orders >= 20:
            return DisruptionSeverity.CRITICAL
        if utilization >= 50.0 or active_orders >= 10:
            return DisruptionSeverity.HIGH
        if active_orders > 0:
            return DisruptionSeverity.MEDIUM
        return DisruptionSeverity.LOW

    elif d_type == DisruptionType.DEMAND_SURGE.value:
        multiplier = float(params.get("surge_multiplier", 1.0))
        extra_orders = int(params.get("extra_orders", 0))

        if multiplier >= 3.0 or extra_orders >= 50:
            return DisruptionSeverity.CRITICAL
        if multiplier >= 2.0 or extra_orders >= 25:
            return DisruptionSeverity.HIGH
        if multiplier >= 1.3 or extra_orders >= 10:
            return DisruptionSeverity.MEDIUM
        return DisruptionSeverity.LOW

    elif d_type == DisruptionType.DELIVERY_DELAY.value:
        delay_mins = float(params.get("delay_minutes", 0.0))
        is_urgent = bool(params.get("is_urgent", ctx.get("is_urgent", False)))

        if is_urgent or delay_mins >= 120.0:
            return DisruptionSeverity.CRITICAL
        if delay_mins >= 60.0:
            return DisruptionSeverity.HIGH
        if delay_mins >= 30.0:
            return DisruptionSeverity.MEDIUM
        return DisruptionSeverity.LOW

    return DisruptionSeverity.MEDIUM

