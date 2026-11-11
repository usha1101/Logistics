from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.warehouse import (
    InventoryItem,
    InventoryMovement,
    MovementType,
    StockStatus,
    Warehouse,
    WarehouseStatus,
)
from app.schemas.analytics import (
    MetricAvailabilityStatus,
    WarehouseAnalyticsResponse,
    WarehousePerformanceSummary,
)
from app.services.analytics.filters import apply_date_filter, build_filter_meta


def compute_warehouse_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    warehouse_id: Optional[str] = None,
    status: Optional[str] = None,
    simulation_id: Optional[str] = None,
    include_simulations: bool = False,
) -> WarehouseAnalyticsResponse:
    filter_meta = build_filter_meta(start_date, end_date, simulation_id, include_simulations)

    wh_stmt = select(Warehouse)
    if warehouse_id:
        wh_stmt = wh_stmt.where(Warehouse.id == warehouse_id)
    if status:
        wh_stmt = wh_stmt.where(Warehouse.status == status)

    warehouses: List[Warehouse] = list(db.execute(wh_stmt).scalars().all())
    total_warehouses = len(warehouses)

    status_counts: Dict[str, int] = {s.value: 0 for s in WarehouseStatus}
    total_capacity = 0.0
    total_used = 0.0
    wh_utilizations: List[float] = []

    wh_ids = [w.id for w in warehouses]

    # Inventory items for these warehouses
    inv_stmt = select(InventoryItem)
    if wh_ids:
        inv_stmt = inv_stmt.where(InventoryItem.warehouse_id.in_(wh_ids))
    elif warehouse_id or status:
        inv_stmt = inv_stmt.where(False)

    items: List[InventoryItem] = list(db.execute(inv_stmt).scalars().all())
    items_by_wh: Dict[str, List[InventoryItem]] = {w.id: [] for w in warehouses}
    for item in items:
        if item.warehouse_id in items_by_wh:
            items_by_wh[item.warehouse_id].append(item)

    total_inventory_items = len(items)
    in_stock_items = 0
    low_stock_items = 0
    out_of_stock_items = 0

    wh_summaries: List[WarehousePerformanceSummary] = []

    for w in warehouses:
        st = w.status
        status_counts[st] = status_counts.get(st, 0) + 1
        cap = float(w.total_capacity or 0.0)
        used = float(w.used_capacity or 0.0)
        total_capacity += cap
        total_used += used
        util_pct = round((used / cap) * 100.0, 2) if cap > 0 else 0.0
        wh_utilizations.append(util_pct)

        w_items = items_by_wh.get(w.id, [])
        w_in = 0
        w_low = 0
        w_out = 0
        for it in w_items:
            st_stock = it.status
            if st_stock == StockStatus.OUT_OF_STOCK:
                w_out += 1
                out_of_stock_items += 1
            elif st_stock == StockStatus.LOW_STOCK:
                w_low += 1
                low_stock_items += 1
            else:
                w_in += 1
                in_stock_items += 1

        wh_name = (
            w.network_node.name
            if getattr(w, "network_node", None) and getattr(w.network_node, "name", None)
            else w.warehouse_code
        )
        wh_summaries.append(
            WarehousePerformanceSummary(
                warehouse_id=w.id,
                warehouse_code=w.warehouse_code,
                name=wh_name,
                status=st,
                total_capacity=round(cap, 2),
                used_capacity=round(used, 2),
                utilization_percentage=util_pct,
                total_skus=len(w_items),
                in_stock_count=w_in,
                low_stock_count=w_low,
                out_of_stock_count=w_out,
            )
        )

    # Inventory movements scoped by date and warehouse items
    item_ids = [it.id for it in items]
    mov_stmt = select(InventoryMovement)
    if item_ids:
        mov_stmt = mov_stmt.where(InventoryMovement.inventory_item_id.in_(item_ids))
    elif warehouse_id or status or total_inventory_items == 0:
        mov_stmt = mov_stmt.where(False)
    mov_stmt = apply_date_filter(mov_stmt, InventoryMovement.created_at, start_date, end_date)

    movements: List[InventoryMovement] = list(db.execute(mov_stmt).scalars().all())
    total_movements = len(movements)
    inbound_count = 0
    outbound_count = 0
    adjustment_count = 0
    inbound_qty = 0
    outbound_qty = 0
    adjustment_qty = 0

    for m in movements:
        mt = m.movement_type
        qty = abs(int(m.quantity or 0))
        if mt == MovementType.STOCK_RECEIVED.value:
            inbound_count += 1
            inbound_qty += qty
        elif mt == MovementType.STOCK_DISPATCHED.value:
            outbound_count += 1
            outbound_qty += qty
        else:
            adjustment_count += 1
            adjustment_qty += qty

    overall_util = round((total_used / total_capacity) * 100.0, 2) if total_capacity > 0 else 0.0
    avg_wh_util = (
        round(sum(wh_utilizations) / len(wh_utilizations), 2) if wh_utilizations else 0.0
    )

    metric_classifications = {
        "total_warehouses": MetricAvailabilityStatus.ACTUAL.value,
        "overall_utilization_percentage": MetricAvailabilityStatus.ACTUAL.value,
        "average_warehouse_utilization_percentage": MetricAvailabilityStatus.ACTUAL.value,
        "total_inventory_items": MetricAvailabilityStatus.ACTUAL.value,
        "total_inventory_movements": MetricAvailabilityStatus.ACTUAL.value,
    }

    return WarehouseAnalyticsResponse(
        total_warehouses=total_warehouses,
        operational_warehouses=status_counts.get(WarehouseStatus.OPERATIONAL.value, 0),
        degraded_warehouses=status_counts.get(WarehouseStatus.DEGRADED.value, 0),
        closed_warehouses=status_counts.get(WarehouseStatus.CLOSED.value, 0),
        maintenance_warehouses=status_counts.get(WarehouseStatus.MAINTENANCE.value, 0),
        total_capacity=round(total_capacity, 2),
        total_used_capacity=round(total_used, 2),
        overall_utilization_percentage=overall_util,
        average_warehouse_utilization_percentage=avg_wh_util,
        total_inventory_items=total_inventory_items,
        in_stock_items=in_stock_items,
        low_stock_items=low_stock_items,
        out_of_stock_items=out_of_stock_items,
        total_inventory_movements=total_movements,
        inbound_movements_count=inbound_count,
        outbound_movements_count=outbound_count,
        adjustment_movements_count=adjustment_count,
        inbound_quantity_total=inbound_qty,
        outbound_quantity_total=outbound_qty,
        adjustment_quantity_total=adjustment_qty,
        warehouses=wh_summaries,
        metric_classifications=metric_classifications,
        unavailable_metrics=[],
        filter_meta=filter_meta,
    )

