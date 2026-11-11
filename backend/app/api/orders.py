from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.session import get_db
from app.models.order import (
    Customer,
    Order,
    OrderAssignmentHistory,
    OrderItem,
    OrderPriority,
    OrderStatus,
    OrderStatusHistory,
    PERMITTED_STATUS_TRANSITIONS,
)
from app.models.user import User, UserRole
from app.models.vehicle import Vehicle, VehicleStatus
from app.models.warehouse import Warehouse
from app.schemas.order import (
    OrderAssignmentHistoryRead,
    OrderAssignmentUpdate,
    OrderCreate,
    OrderItemCreate,
    OrderItemRead,
    OrderRead,
    OrderStatusHistoryRead,
    OrderStatusUpdate,
    OrderSummaryResponse,
    OrderUpdate,
    PaginatedOrdersResponse,
)

router = APIRouter(prefix="/orders", tags=["Order Management"])

ALL_ORDER_READ_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
    UserRole.WAREHOUSE_MANAGER,
    UserRole.FLEET_MANAGER,
    UserRole.ANALYST,
)

ORDER_MANAGE_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
)

ORDER_STATUS_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
    UserRole.WAREHOUSE_MANAGER,
)

ORDER_ASSIGN_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
    UserRole.FLEET_MANAGER,
)

WAREHOUSE_MANAGER_ALLOWED_STATUSES = {
    OrderStatus.CONFIRMED.value,
    OrderStatus.PROCESSING.value,
    OrderStatus.READY_FOR_DISPATCH.value,
    OrderStatus.ON_HOLD.value,
}


@router.get(
    "/summary",
    response_model=OrderSummaryResponse,
    summary="Get aggregated database-derived order metrics and status breakdown",
)
def get_order_summary(
    current_user: User = Depends(require_roles(*ALL_ORDER_READ_ROLES)),
    db: Session = Depends(get_db),
) -> OrderSummaryResponse:
    orders = list(db.execute(select(Order)).scalars().all())

    now = datetime.now(timezone.utc)
    total_orders = len(orders)
    created_orders = sum(1 for o in orders if o.status == OrderStatus.CREATED.value)
    confirmed_orders = sum(1 for o in orders if o.status == OrderStatus.CONFIRMED.value)
    processing_orders = sum(1 for o in orders if o.status == OrderStatus.PROCESSING.value)
    ready_for_dispatch_orders = sum(1 for o in orders if o.status == OrderStatus.READY_FOR_DISPATCH.value)
    dispatched_orders = sum(1 for o in orders if o.status == OrderStatus.DISPATCHED.value)
    in_transit_orders = sum(1 for o in orders if o.status == OrderStatus.IN_TRANSIT.value)
    delivered_orders = sum(1 for o in orders if o.status == OrderStatus.DELIVERED.value)
    cancelled_orders = sum(1 for o in orders if o.status == OrderStatus.CANCELLED.value)
    on_hold_orders = sum(1 for o in orders if o.status == OrderStatus.ON_HOLD.value)
    failed_delivery_orders = sum(1 for o in orders if o.status == OrderStatus.FAILED_DELIVERY.value)

    overdue_orders = sum(1 for o in orders if o.is_overdue)
    unassigned_orders = sum(1 for o in orders if o.assigned_vehicle_id is None and o.status not in (OrderStatus.DELIVERED.value, OrderStatus.CANCELLED.value))
    urgent_orders = sum(1 for o in orders if o.priority == OrderPriority.URGENT.value and o.status not in (OrderStatus.DELIVERED.value, OrderStatus.CANCELLED.value))

    total_order_value = sum(o.total_amount for o in orders)
    total_order_weight_kg = sum(o.total_weight_kg for o in orders)

    return OrderSummaryResponse(
        total_orders=total_orders,
        created_orders=created_orders,
        confirmed_orders=confirmed_orders,
        processing_orders=processing_orders,
        ready_for_dispatch_orders=ready_for_dispatch_orders,
        dispatched_orders=dispatched_orders,
        in_transit_orders=in_transit_orders,
        delivered_orders=delivered_orders,
        cancelled_orders=cancelled_orders,
        on_hold_orders=on_hold_orders,
        failed_delivery_orders=failed_delivery_orders,
        overdue_orders=overdue_orders,
        unassigned_orders=unassigned_orders,
        urgent_orders=urgent_orders,
        total_order_value=round(total_order_value, 2),
        total_order_weight_kg=round(total_order_weight_kg, 2),
        generated_at=now,
        data_source="SIMULATED",
    )


@router.get(
    "/pending",
    response_model=PaginatedOrdersResponse,
    summary="List all pending orders awaiting dispatch or fulfillment",
)
def get_pending_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles(*ALL_ORDER_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedOrdersResponse:
    pending_statuses = [
        OrderStatus.CREATED.value,
        OrderStatus.CONFIRMED.value,
        OrderStatus.PROCESSING.value,
        OrderStatus.READY_FOR_DISPATCH.value,
    ]
    query = select(Order).where(Order.status.in_(pending_statuses)).order_by(Order.expected_delivery_at.asc())
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    orders = list(db.execute(query.offset(skip).limit(limit)).scalars().all())

    return PaginatedOrdersResponse(
        items=[OrderRead.model_validate(o) for o in orders],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/overdue",
    response_model=PaginatedOrdersResponse,
    summary="List orders that have breached their expected delivery deadline",
)
def get_overdue_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles(*ALL_ORDER_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedOrdersResponse:
    now = datetime.now(timezone.utc)
    terminal_statuses = [OrderStatus.DELIVERED.value, OrderStatus.CANCELLED.value]
    query = (
        select(Order)
        .where(
            Order.status.notin_(terminal_statuses),
            Order.expected_delivery_at < now,
        )
        .order_by(Order.expected_delivery_at.asc())
    )
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    orders = list(db.execute(query.offset(skip).limit(limit)).scalars().all())

    return PaginatedOrdersResponse(
        items=[OrderRead.model_validate(o) for o in orders],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/unassigned",
    response_model=PaginatedOrdersResponse,
    summary="List active orders that do not have an assigned delivery vehicle",
)
def get_unassigned_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles(*ALL_ORDER_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedOrdersResponse:
    terminal_statuses = [OrderStatus.DELIVERED.value, OrderStatus.CANCELLED.value]
    query = (
        select(Order)
        .where(
            Order.assigned_vehicle_id.is_(None),
            Order.status.notin_(terminal_statuses),
        )
        .order_by(Order.expected_delivery_at.asc())
    )
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    orders = list(db.execute(query.offset(skip).limit(limit)).scalars().all())

    return PaginatedOrdersResponse(
        items=[OrderRead.model_validate(o) for o in orders],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "",
    response_model=PaginatedOrdersResponse,
    summary="List orders with comprehensive filtering and pagination",
)
def list_orders(
    status_filter: Optional[OrderStatus] = Query(None, alias="status", description="Filter by status"),
    priority_filter: Optional[OrderPriority] = Query(None, alias="priority", description="Filter by priority"),
    customer_id: Optional[str] = Query(None, description="Filter by customer ID"),
    warehouse_id: Optional[str] = Query(None, description="Filter by origin warehouse ID"),
    assigned_vehicle_id: Optional[str] = Query(None, description="Filter by assigned vehicle ID"),
    is_overdue: Optional[bool] = Query(None, description="Filter by overdue status"),
    start_date: Optional[datetime] = Query(None, description="Filter orders created on or after"),
    end_date: Optional[datetime] = Query(None, description="Filter orders created on or before"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles(*ALL_ORDER_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedOrdersResponse:
    query = select(Order)

    if status_filter is not None:
        query = query.where(Order.status == status_filter.value)
    if priority_filter is not None:
        query = query.where(Order.priority == priority_filter.value)
    if customer_id is not None:
        query = query.where(Order.customer_id == customer_id)
    if warehouse_id is not None:
        query = query.where(Order.warehouse_id == warehouse_id)
    if assigned_vehicle_id is not None:
        query = query.where(Order.assigned_vehicle_id == assigned_vehicle_id)
    if start_date is not None:
        query = query.where(Order.created_at >= start_date)
    if end_date is not None:
        query = query.where(Order.created_at <= end_date)
    if is_overdue is not None:
        now = datetime.now(timezone.utc)
        terminal = [OrderStatus.DELIVERED.value, OrderStatus.CANCELLED.value]
        if is_overdue:
            query = query.where(Order.status.notin_(terminal), Order.expected_delivery_at < now)
        else:
            query = query.where(or_(Order.status.in_(terminal), Order.expected_delivery_at >= now))

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    orders = list(db.execute(query.order_by(Order.created_at.desc()).offset(skip).limit(limit)).scalars().all())

    return PaginatedOrdersResponse(
        items=[OrderRead.model_validate(o) for o in orders],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order with optional initial order items",
)
def create_order(
    payload: OrderCreate,
    current_user: User = Depends(require_roles(*ORDER_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> OrderRead:
    # 1. Check duplicate order number
    existing_order = db.execute(select(Order).where(Order.order_number == payload.order_number)).scalar_one_or_none()
    if existing_order:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Order with order_number '{payload.order_number}' already exists",
        )

    # 2. Check customer exists
    customer = db.execute(select(Customer).where(Customer.id == payload.customer_id)).scalar_one_or_none()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Customer '{payload.customer_id}' not found",
        )

    # 3. Check warehouse exists
    warehouse = db.execute(select(Warehouse).where(Warehouse.id == payload.warehouse_id)).scalar_one_or_none()
    if not warehouse:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Warehouse '{payload.warehouse_id}' not found",
        )

    now = datetime.now(timezone.utc)
    order = Order(
        order_number=payload.order_number,
        customer_id=payload.customer_id,
        warehouse_id=payload.warehouse_id,
        status=OrderStatus.CREATED.value,
        priority=payload.priority.value if payload.priority else OrderPriority.NORMAL.value,
        order_date=now,
        expected_delivery_at=payload.expected_delivery_at,
        delivery_address=payload.delivery_address,
        delivery_latitude=payload.delivery_latitude,
        delivery_longitude=payload.delivery_longitude,
        total_weight_kg=0.0,
        total_amount=0.0,
        notes=payload.notes,
        created_by_user_id=current_user.id,
    )
    db.add(order)
    db.flush()

    total_weight = 0.0
    total_amount = 0.0

    if payload.items:
        for itm in payload.items:
            sub = round(itm.quantity * itm.unit_price, 2)
            wt = round(itm.quantity * itm.unit_weight_kg, 2)
            order_item = OrderItem(
                order_id=order.id,
                product_code=itm.product_code,
                product_name=itm.product_name,
                quantity=itm.quantity,
                unit_price=itm.unit_price,
                unit_weight_kg=itm.unit_weight_kg,
                subtotal=sub,
                total_weight_kg=wt,
            )
            db.add(order_item)
            total_amount += sub
            total_weight += wt

    order.total_amount = round(total_amount, 2)
    order.total_weight_kg = round(total_weight, 2)

    # Record initial status history
    hist = OrderStatusHistory(
        order_id=order.id,
        previous_status=None,
        new_status=OrderStatus.CREATED.value,
        reason="Order initialized",
        changed_by_user_id=current_user.id,
        changed_at=now,
    )
    db.add(hist)

    db.commit()
    db.refresh(order)
    return OrderRead.model_validate(order)


@router.get(
    "/{order_id}",
    response_model=OrderRead,
    summary="Get complete order details including items and customer info",
)
def get_order(
    order_id: str,
    current_user: User = Depends(require_roles(*ALL_ORDER_READ_ROLES)),
    db: Session = Depends(get_db),
) -> OrderRead:
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found",
        )
    return OrderRead.model_validate(order)


@router.patch(
    "/{order_id}",
    response_model=OrderRead,
    summary="Update permitted order properties (priority, deadline, notes, address)",
)
def update_order(
    order_id: str,
    payload: OrderUpdate,
    current_user: User = Depends(require_roles(*ORDER_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> OrderRead:
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found",
        )

    if order.status in (OrderStatus.DELIVERED.value, OrderStatus.CANCELLED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot modify order in terminal status '{order.status}'",
        )

    if payload.priority is not None:
        order.priority = payload.priority.value
    if payload.expected_delivery_at is not None:
        order.expected_delivery_at = payload.expected_delivery_at
    if payload.delivery_address is not None:
        order.delivery_address = payload.delivery_address
    if payload.delivery_latitude is not None:
        order.delivery_latitude = payload.delivery_latitude
    if payload.delivery_longitude is not None:
        order.delivery_longitude = payload.delivery_longitude
    if payload.notes is not None:
        order.notes = payload.notes

    db.commit()
    db.refresh(order)
    return OrderRead.model_validate(order)


@router.get(
    "/{order_id}/items",
    response_model=List[OrderItemRead],
    summary="List all line items for an order",
)
def list_order_items(
    order_id: str,
    current_user: User = Depends(require_roles(*ALL_ORDER_READ_ROLES)),
    db: Session = Depends(get_db),
) -> List[OrderItemRead]:
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found",
        )
    return [OrderItemRead.model_validate(i) for i in order.items]


@router.post(
    "/{order_id}/items",
    response_model=OrderItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add an item to an order and recalculate order totals",
)
def add_order_item(
    order_id: str,
    payload: OrderItemCreate,
    current_user: User = Depends(require_roles(*ORDER_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> OrderItemRead:
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found",
        )

    if order.status not in (OrderStatus.CREATED.value, OrderStatus.CONFIRMED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot add items to order with status '{order.status}'",
        )

    sub = round(payload.quantity * payload.unit_price, 2)
    wt = round(payload.quantity * payload.unit_weight_kg, 2)

    item = OrderItem(
        order_id=order.id,
        product_code=payload.product_code,
        product_name=payload.product_name,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        unit_weight_kg=payload.unit_weight_kg,
        subtotal=sub,
        total_weight_kg=wt,
    )
    db.add(item)
    db.flush()

    # Recalculate totals
    all_items = list(db.execute(select(OrderItem).where(OrderItem.order_id == order.id)).scalars().all())
    order.total_amount = round(sum(i.subtotal for i in all_items), 2)
    order.total_weight_kg = round(sum(i.total_weight_kg for i in all_items), 2)

    db.commit()
    db.refresh(item)
    return OrderItemRead.model_validate(item)


@router.patch(
    "/{order_id}/status",
    response_model=OrderRead,
    summary="Advance order lifecycle status with state-machine validation and audit trail",
)
def update_order_status(
    order_id: str,
    payload: OrderStatusUpdate,
    current_user: User = Depends(require_roles(*ORDER_STATUS_ROLES)),
    db: Session = Depends(get_db),
) -> OrderRead:
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found",
        )

    target_status = payload.status.value

    # If same status, return without duplicate history
    if order.status == target_status:
        return OrderRead.model_validate(order)

    # Warehouse manager role restriction
    if current_user.role == UserRole.WAREHOUSE_MANAGER.value:
        if target_status not in WAREHOUSE_MANAGER_ALLOWED_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Warehouse Manager role is restricted to updating orders to {WAREHOUSE_MANAGER_ALLOWED_STATUSES}",
            )

    # State transition validation
    allowed_transitions = PERMITTED_STATUS_TRANSITIONS.get(order.status, set())
    if target_status not in allowed_transitions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid order status transition from '{order.status}' to '{target_status}'",
        )

    now = datetime.now(timezone.utc)

    # Invariants for dispatch & delivery
    if target_status == OrderStatus.DISPATCHED.value:
        if order.dispatched_at is None:
            order.dispatched_at = now
    elif target_status == OrderStatus.DELIVERED.value:
        if order.dispatched_at is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An order cannot be delivered before it is dispatched",
            )
        if order.delivered_at is None:
            order.delivered_at = now
        # Release vehicle load upon delivery
        if order.assigned_vehicle_id:
            veh = db.execute(select(Vehicle).where(Vehicle.id == order.assigned_vehicle_id)).scalar_one_or_none()
            if veh:
                veh.current_load_kg = max(0.0, round(veh.current_load_kg - order.total_weight_kg, 2))
    elif target_status == OrderStatus.CANCELLED.value:
        # Release vehicle load upon cancellation
        if order.assigned_vehicle_id:
            veh = db.execute(select(Vehicle).where(Vehicle.id == order.assigned_vehicle_id)).scalar_one_or_none()
            if veh:
                veh.current_load_kg = max(0.0, round(veh.current_load_kg - order.total_weight_kg, 2))

    prev_status = order.status
    order.status = target_status

    # Record immutable status history
    history = OrderStatusHistory(
        order_id=order.id,
        previous_status=prev_status,
        new_status=target_status,
        reason=payload.reason,
        changed_by_user_id=current_user.id,
        changed_at=now,
    )
    db.add(history)

    db.commit()
    db.refresh(order)
    return OrderRead.model_validate(order)


@router.get(
    "/{order_id}/history",
    response_model=List[OrderStatusHistoryRead],
    summary="Get chronological status history for an order",
)
def get_order_status_history(
    order_id: str,
    current_user: User = Depends(require_roles(*ALL_ORDER_READ_ROLES)),
    db: Session = Depends(get_db),
) -> List[OrderStatusHistoryRead]:
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found",
        )
    return [OrderStatusHistoryRead.model_validate(h) for h in order.status_history]


@router.patch(
    "/{order_id}/assignment",
    response_model=OrderRead,
    summary="Assign or reassign an order to a vehicle with capacity validation and audit trail",
)
def assign_order_vehicle(
    order_id: str,
    payload: OrderAssignmentUpdate,
    current_user: User = Depends(require_roles(*ORDER_ASSIGN_ROLES)),
    db: Session = Depends(get_db),
) -> OrderRead:
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found",
        )

    if order.status in (OrderStatus.DELIVERED.value, OrderStatus.CANCELLED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot assign vehicle to order in terminal status '{order.status}'",
        )

    prev_veh_id = order.assigned_vehicle_id
    new_veh_id = payload.vehicle_id

    # If same vehicle assignment, return early
    if prev_veh_id == new_veh_id:
        return OrderRead.model_validate(order)

    now = datetime.now(timezone.utc)

    # 1. Handle unassignment (new_veh_id is None)
    if new_veh_id is None:
        if prev_veh_id:
            old_veh = db.execute(select(Vehicle).where(Vehicle.id == prev_veh_id)).scalar_one_or_none()
            if old_veh:
                old_veh.current_load_kg = max(0.0, round(old_veh.current_load_kg - order.total_weight_kg, 2))
        order.assigned_vehicle_id = None

    # 2. Handle new vehicle assignment
    else:
        new_veh = db.execute(select(Vehicle).where(Vehicle.id == new_veh_id)).scalar_one_or_none()
        if not new_veh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vehicle '{new_veh_id}' not found",
            )
        if not new_veh.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vehicle '{new_veh.vehicle_code}' is inactive and cannot be assigned",
            )
        if new_veh.status in (VehicleStatus.BREAKDOWN.value, VehicleStatus.MAINTENANCE.value, VehicleStatus.OFFLINE.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vehicle '{new_veh.vehicle_code}' status is '{new_veh.status}', which does not permit assignment",
            )

        # Check vehicle capacity
        available_capacity = round(new_veh.capacity_kg - new_veh.current_load_kg, 2)
        if order.total_weight_kg > available_capacity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Vehicle '{new_veh.vehicle_code}' has insufficient capacity: "
                    f"available {available_capacity} kg, order requires {order.total_weight_kg} kg"
                ),
            )

        # If previous vehicle exists, release previous vehicle load
        if prev_veh_id:
            old_veh = db.execute(select(Vehicle).where(Vehicle.id == prev_veh_id)).scalar_one_or_none()
            if old_veh:
                old_veh.current_load_kg = max(0.0, round(old_veh.current_load_kg - order.total_weight_kg, 2))

        # Add load to new vehicle
        new_veh.current_load_kg = round(new_veh.current_load_kg + order.total_weight_kg, 2)
        order.assigned_vehicle_id = new_veh_id

    # Record assignment history
    assignment_hist = OrderAssignmentHistory(
        order_id=order.id,
        previous_vehicle_id=prev_veh_id,
        new_vehicle_id=new_veh_id,
        assigned_by_user_id=current_user.id,
        reason=payload.reason,
        assigned_at=now,
    )
    db.add(assignment_hist)

    db.commit()
    db.refresh(order)
    return OrderRead.model_validate(order)


@router.get(
    "/{order_id}/assignment-history",
    response_model=List[OrderAssignmentHistoryRead],
    summary="Get vehicle assignment audit history for an order",
)
def get_order_assignment_history(
    order_id: str,
    current_user: User = Depends(require_roles(*ALL_ORDER_READ_ROLES)),
    db: Session = Depends(get_db),
) -> List[OrderAssignmentHistoryRead]:
    order = db.execute(select(Order).where(Order.id == order_id)).scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found",
        )
    return [OrderAssignmentHistoryRead.model_validate(h) for h in order.assignment_history]

