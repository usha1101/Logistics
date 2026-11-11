from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.session import get_db
from app.models.user import User, UserRole
from app.models.warehouse import (
    InventoryItem,
    InventoryMovement,
    MovementType,
    Warehouse,
)
from app.schemas.warehouse import (
    InventoryItemRead,
    InventoryItemUpdate,
    PaginatedInventoryResponse,
    PaginatedMovementsResponse,
    StockMovementCreate,
    StockMovementRead,
)

router = APIRouter(prefix="/inventory", tags=["Inventory Management"])

ALL_INVENTORY_READ_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
    UserRole.WAREHOUSE_MANAGER,
    UserRole.FLEET_MANAGER,
    UserRole.ANALYST,
)

INVENTORY_MANAGE_ROLES = (
    UserRole.ADMIN,
    UserRole.WAREHOUSE_MANAGER,
)


@router.get(
    "/low-stock",
    response_model=PaginatedInventoryResponse,
    summary="List inventory items currently in LOW_STOCK or OUT_OF_STOCK state",
)
def get_low_stock_items(
    warehouse_id: Optional[str] = Query(None, description="Filter by warehouse ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_roles(*ALL_INVENTORY_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedInventoryResponse:
    query = select(InventoryItem).where(InventoryItem.quantity <= InventoryItem.reorder_level)

    if warehouse_id is not None:
        query = query.where(InventoryItem.warehouse_id == warehouse_id)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    items = list(db.execute(query.order_by(InventoryItem.quantity.asc()).offset(skip).limit(limit)).scalars().all())

    return PaginatedInventoryResponse(
        items=[InventoryItemRead.model_validate(i) for i in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{inventory_item_id}",
    response_model=InventoryItemRead,
    summary="Get single inventory item by ID",
)
def get_inventory_item(
    inventory_item_id: str,
    current_user: User = Depends(require_roles(*ALL_INVENTORY_READ_ROLES)),
    db: Session = Depends(get_db),
) -> InventoryItemRead:
    item = db.execute(
        select(InventoryItem).where(InventoryItem.id == inventory_item_id)
    ).scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory item '{inventory_item_id}' not found",
        )

    return InventoryItemRead.model_validate(item)


@router.patch(
    "/{inventory_item_id}",
    response_model=InventoryItemRead,
    summary="Update inventory metadata (Direct quantity changes are prohibited)",
)
def update_inventory_item(
    inventory_item_id: str,
    payload: InventoryItemUpdate,
    current_user: User = Depends(require_roles(*INVENTORY_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> InventoryItemRead:
    item = db.execute(
        select(InventoryItem).where(InventoryItem.id == inventory_item_id)
    ).scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory item '{inventory_item_id}' not found",
        )

    wh = db.execute(select(Warehouse).where(Warehouse.id == item.warehouse_id)).scalar_one_or_none()

    if payload.product_name is not None:
        item.product_name = payload.product_name
    if payload.category is not None:
        item.category = payload.category
    if payload.reorder_level is not None:
        item.reorder_level = payload.reorder_level
    if payload.unit is not None:
        item.unit = payload.unit

    # If unit_volume changed and item has quantity, adjust warehouse used capacity accordingly
    if payload.unit_volume is not None and payload.unit_volume != item.unit_volume:
        if wh:
            old_vol = (item.unit_volume or 0.0) * item.quantity
            new_vol = payload.unit_volume * item.quantity
            diff = new_vol - old_vol
            if diff > 0 and wh.used_capacity + diff > wh.total_capacity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Increasing unit volume requires {diff} additional capacity units, exceeding available capacity",
                )
            wh.used_capacity = max(0.0, round(wh.used_capacity + diff, 2))
        item.unit_volume = payload.unit_volume

    db.commit()
    db.refresh(item)
    return InventoryItemRead.model_validate(item)


@router.post(
    "/{inventory_item_id}/movements",
    response_model=StockMovementRead,
    status_code=status.HTTP_201_CREATED,
    summary="Execute an audited, transactional stock movement (receipt, dispatch, or adjustment)",
)
def record_stock_movement(
    inventory_item_id: str,
    payload: StockMovementCreate,
    current_user: User = Depends(require_roles(*INVENTORY_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> StockMovementRead:
    item = db.execute(
        select(InventoryItem).where(InventoryItem.id == inventory_item_id)
    ).scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory item '{inventory_item_id}' not found",
        )

    wh = db.execute(select(Warehouse).where(Warehouse.id == item.warehouse_id)).scalar_one_or_none()
    prev_qty = item.quantity
    vol_per_unit = item.unit_volume or 0.0

    if payload.movement_type == MovementType.STOCK_RECEIVED:
        new_qty = prev_qty + payload.quantity
        vol_change = payload.quantity * vol_per_unit
        if wh and vol_change > 0:
            if wh.used_capacity + vol_change > wh.total_capacity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Receiving {payload.quantity} units requires {vol_change} capacity, exceeding available warehouse capacity ({wh.total_capacity - wh.used_capacity})",
                )
            wh.used_capacity = round(wh.used_capacity + vol_change, 2)

    elif payload.movement_type == MovementType.STOCK_DISPATCHED:
        if payload.quantity > prev_qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient stock for dispatch: requested {payload.quantity}, but only {prev_qty} units available",
            )
        new_qty = prev_qty - payload.quantity
        vol_change = payload.quantity * vol_per_unit
        if wh and vol_change > 0:
            wh.used_capacity = max(0.0, round(wh.used_capacity - vol_change, 2))

    elif payload.movement_type == MovementType.STOCK_ADJUSTMENT:
        if not payload.adjustment_type:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Field 'adjustment_type' ('INCREASE' or 'DECREASE') is required for STOCK_ADJUSTMENT movements",
            )
        if payload.adjustment_type == "INCREASE":
            new_qty = prev_qty + payload.quantity
            vol_change = payload.quantity * vol_per_unit
            if wh and vol_change > 0:
                if wh.used_capacity + vol_change > wh.total_capacity:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Capacity limit exceeded during stock adjustment increase",
                    )
                wh.used_capacity = round(wh.used_capacity + vol_change, 2)
        else:  # DECREASE
            if payload.quantity > prev_qty:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Adjustment decrease of {payload.quantity} exceeds available stock ({prev_qty})",
                )
            new_qty = prev_qty - payload.quantity
            vol_change = payload.quantity * vol_per_unit
            if wh and vol_change > 0:
                wh.used_capacity = max(0.0, round(wh.used_capacity - vol_change, 2))
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown movement type '{payload.movement_type}'",
        )

    # 1. Update item quantity
    item.quantity = new_qty

    # 2. Record immutable audit entry
    movement = InventoryMovement(
        inventory_item_id=item.id,
        movement_type=payload.movement_type.value if isinstance(payload.movement_type, MovementType) else str(payload.movement_type),
        quantity=payload.quantity,
        previous_quantity=prev_qty,
        new_quantity=new_qty,
        reference=payload.reference,
        notes=payload.notes,
        created_by_user_id=current_user.id,
    )
    db.add(movement)

    # 3. Commit transaction
    db.commit()
    db.refresh(movement)

    return StockMovementRead.model_validate(movement)


@router.get(
    "/{inventory_item_id}/movements",
    response_model=PaginatedMovementsResponse,
    summary="Retrieve audit trail history of stock movements for an inventory item",
)
def get_inventory_movements(
    inventory_item_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_roles(*ALL_INVENTORY_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedMovementsResponse:
    item = db.execute(
        select(InventoryItem).where(InventoryItem.id == inventory_item_id)
    ).scalar_one_or_none()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory item '{inventory_item_id}' not found",
        )

    query = (
        select(InventoryMovement)
        .where(InventoryMovement.inventory_item_id == inventory_item_id)
        .order_by(InventoryMovement.created_at.desc())
    )

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    items = list(db.execute(query.offset(skip).limit(limit)).scalars().all())

    return PaginatedMovementsResponse(
        items=[StockMovementRead.model_validate(m) for m in items],
        total=total,
        skip=skip,
        limit=limit,
    )

