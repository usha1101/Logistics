from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.session import get_db
from app.models.network import NetworkNode, NodeType
from app.models.user import User, UserRole
from app.models.warehouse import (
    InventoryItem,
    Warehouse,
    WarehouseStatus,
    WarehouseType,
)
from app.schemas.warehouse import (
    InventoryItemCreate,
    InventoryItemRead,
    PaginatedInventoryResponse,
    PaginatedWarehousesResponse,
    WarehouseCreate,
    WarehouseRead,
    WarehouseSummaryResponse,
    WarehouseUpdate,
)

router = APIRouter(prefix="/warehouses", tags=["Warehouses"])

ALL_WAREHOUSE_READ_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
    UserRole.WAREHOUSE_MANAGER,
    UserRole.FLEET_MANAGER,
    UserRole.ANALYST,
)

WAREHOUSE_MANAGE_ROLES = (
    UserRole.ADMIN,
    UserRole.WAREHOUSE_MANAGER,
)

DASHBOARD_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
    UserRole.WAREHOUSE_MANAGER,
    UserRole.ANALYST,
)


@router.get(
    "/summary",
    response_model=WarehouseSummaryResponse,
    summary="Get aggregated warehouse and inventory operational metrics",
)
def get_warehouses_summary(
    current_user: User = Depends(require_roles(*DASHBOARD_ROLES)),
    db: Session = Depends(get_db),
) -> WarehouseSummaryResponse:
    # 1. Warehouse status counts
    total_warehouses = db.execute(select(func.count()).select_from(Warehouse)).scalar() or 0
    operational = db.execute(
        select(func.count()).select_from(Warehouse).where(Warehouse.status == WarehouseStatus.OPERATIONAL.value)
    ).scalar() or 0
    degraded = db.execute(
        select(func.count()).select_from(Warehouse).where(Warehouse.status == WarehouseStatus.DEGRADED.value)
    ).scalar() or 0
    closed = db.execute(
        select(func.count()).select_from(Warehouse).where(Warehouse.status == WarehouseStatus.CLOSED.value)
    ).scalar() or 0

    # 2. Storage capacity aggregates
    total_cap = db.execute(select(func.coalesce(func.sum(Warehouse.total_capacity), 0.0))).scalar() or 0.0
    used_cap = db.execute(select(func.coalesce(func.sum(Warehouse.used_capacity), 0.0))).scalar() or 0.0
    available_cap = max(0.0, total_cap - used_cap)
    avg_util = round((used_cap / total_cap) * 100, 2) if total_cap > 0 else None

    # 3. Inventory health counts
    total_inv = db.execute(select(func.count()).select_from(InventoryItem)).scalar() or 0
    out_of_stock = db.execute(
        select(func.count()).select_from(InventoryItem).where(InventoryItem.quantity == 0)
    ).scalar() or 0
    low_stock = db.execute(
        select(func.count())
        .select_from(InventoryItem)
        .where(InventoryItem.quantity > 0, InventoryItem.quantity <= InventoryItem.reorder_level)
    ).scalar() or 0

    return WarehouseSummaryResponse(
        total_warehouses=total_warehouses,
        operational_warehouses=operational,
        degraded_warehouses=degraded,
        closed_warehouses=closed,
        total_storage_capacity=round(total_cap, 2),
        used_storage_capacity=round(used_cap, 2),
        available_storage_capacity=round(available_cap, 2),
        average_utilization_percentage=avg_util,
        total_inventory_records=total_inv,
        low_stock_items=low_stock,
        out_of_stock_items=out_of_stock,
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_source="SIMULATED",
    )


@router.get(
    "",
    response_model=PaginatedWarehousesResponse,
    summary="List all warehouses with optional status/type/region filters",
)
def list_warehouses(
    status: Optional[WarehouseStatus] = Query(None, description="Filter by operational status"),
    warehouse_type: Optional[WarehouseType] = Query(None, description="Filter by warehouse classification"),
    region: Optional[str] = Query(None, description="Filter by geographical region of linked node"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_roles(*ALL_WAREHOUSE_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedWarehousesResponse:
    query = select(Warehouse).join(Warehouse.network_node)

    if status is not None:
        val = status.value if isinstance(status, WarehouseStatus) else str(status)
        query = query.where(Warehouse.status == val)
    if warehouse_type is not None:
        val = warehouse_type.value if isinstance(warehouse_type, WarehouseType) else str(warehouse_type)
        query = query.where(Warehouse.warehouse_type == val)
    if region is not None:
        query = query.where(NetworkNode.region == region)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    items = list(db.execute(query.order_by(Warehouse.warehouse_code.asc()).offset(skip).limit(limit)).scalars().all())

    return PaginatedWarehousesResponse(
        items=[WarehouseRead.model_validate(w) for w in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "",
    response_model=WarehouseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new warehouse linked to an existing WAREHOUSE NetworkNode",
)
def create_warehouse(
    payload: WarehouseCreate,
    current_user: User = Depends(require_roles(*WAREHOUSE_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> WarehouseRead:
    # 1. Verify target NetworkNode exists
    node = db.execute(
        select(NetworkNode).where(NetworkNode.id == payload.network_node_id)
    ).scalar_one_or_none()

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network node '{payload.network_node_id}' does not exist",
        )

    # 2. Prevent linking a CUSTOMER node as a warehouse
    if node.node_type != NodeType.WAREHOUSE.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot associate warehouse with a '{node.node_type}' node; node must be of type 'WAREHOUSE'",
        )

    # 3. Check if network_node is already associated with an existing warehouse
    existing_link = db.execute(
        select(Warehouse).where(Warehouse.network_node_id == payload.network_node_id)
    ).scalar_one_or_none()
    if existing_link:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Network node '{payload.network_node_id}' is already associated with warehouse '{existing_link.warehouse_code}'",
        )

    # 4. Check if warehouse_code is unique
    existing_code = db.execute(
        select(Warehouse).where(Warehouse.warehouse_code == payload.warehouse_code)
    ).scalar_one_or_none()
    if existing_code:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Warehouse code '{payload.warehouse_code}' is already registered",
        )

    warehouse = Warehouse(
        network_node_id=payload.network_node_id,
        warehouse_code=payload.warehouse_code,
        warehouse_type=payload.warehouse_type.value if isinstance(payload.warehouse_type, WarehouseType) else str(payload.warehouse_type),
        total_capacity=payload.total_capacity,
        used_capacity=0.0,
        status=payload.status.value if isinstance(payload.status, WarehouseStatus) else str(payload.status),
        manager_name=payload.manager_name,
        contact_number=payload.contact_number,
        operating_hours=payload.operating_hours,
    )
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)

    return WarehouseRead.model_validate(warehouse)


@router.get(
    "/{warehouse_id}",
    response_model=WarehouseRead,
    summary="Get single warehouse details by ID",
)
def get_warehouse(
    warehouse_id: str,
    current_user: User = Depends(require_roles(*ALL_WAREHOUSE_READ_ROLES)),
    db: Session = Depends(get_db),
) -> WarehouseRead:
    warehouse = db.execute(
        select(Warehouse).where(Warehouse.id == warehouse_id)
    ).scalar_one_or_none()

    if not warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse '{warehouse_id}' not found",
        )

    return WarehouseRead.model_validate(warehouse)


@router.patch(
    "/{warehouse_id}",
    response_model=WarehouseRead,
    summary="Update operational warehouse attributes",
)
def update_warehouse(
    warehouse_id: str,
    payload: WarehouseUpdate,
    current_user: User = Depends(require_roles(*WAREHOUSE_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> WarehouseRead:
    warehouse = db.execute(
        select(Warehouse).where(Warehouse.id == warehouse_id)
    ).scalar_one_or_none()

    if not warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse '{warehouse_id}' not found",
        )

    if payload.total_capacity is not None:
        if payload.total_capacity < warehouse.used_capacity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"New total capacity ({payload.total_capacity}) cannot be less than currently used capacity ({warehouse.used_capacity})",
            )
        warehouse.total_capacity = payload.total_capacity

    if payload.warehouse_type is not None:
        warehouse.warehouse_type = (
            payload.warehouse_type.value
            if isinstance(payload.warehouse_type, WarehouseType)
            else str(payload.warehouse_type)
        )
    if payload.status is not None:
        warehouse.status = (
            payload.status.value
            if isinstance(payload.status, WarehouseStatus)
            else str(payload.status)
        )
    if payload.manager_name is not None:
        warehouse.manager_name = payload.manager_name
    if payload.contact_number is not None:
        warehouse.contact_number = payload.contact_number
    if payload.operating_hours is not None:
        warehouse.operating_hours = payload.operating_hours

    db.commit()
    db.refresh(warehouse)
    return WarehouseRead.model_validate(warehouse)


@router.get(
    "/{warehouse_id}/inventory",
    response_model=PaginatedInventoryResponse,
    summary="List inventory items stored in a warehouse",
)
def list_warehouse_inventory(
    warehouse_id: str,
    category: Optional[str] = Query(None, description="Filter by product category"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_roles(*ALL_WAREHOUSE_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedInventoryResponse:
    # Verify warehouse exists
    wh = db.execute(select(Warehouse).where(Warehouse.id == warehouse_id)).scalar_one_or_none()
    if not wh:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse '{warehouse_id}' not found",
        )

    query = select(InventoryItem).where(InventoryItem.warehouse_id == warehouse_id)
    if category is not None:
        query = query.where(InventoryItem.category == category)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    items = list(db.execute(query.order_by(InventoryItem.sku.asc()).offset(skip).limit(limit)).scalars().all())

    return PaginatedInventoryResponse(
        items=[InventoryItemRead.model_validate(i) for i in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/{warehouse_id}/inventory",
    response_model=InventoryItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new inventory SKU to a warehouse",
)
def add_warehouse_inventory_item(
    warehouse_id: str,
    payload: InventoryItemCreate,
    current_user: User = Depends(require_roles(*WAREHOUSE_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> InventoryItemRead:
    wh = db.execute(select(Warehouse).where(Warehouse.id == warehouse_id)).scalar_one_or_none()
    if not wh:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warehouse '{warehouse_id}' not found",
        )

    # Check for duplicate SKU within this warehouse
    existing_sku = db.execute(
        select(InventoryItem).where(
            InventoryItem.warehouse_id == warehouse_id,
            InventoryItem.sku == payload.sku,
        )
    ).scalar_one_or_none()
    if existing_sku:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"SKU '{payload.sku}' already exists in warehouse '{wh.warehouse_code}'",
        )

    # If unit_volume and quantity > 0, check capacity headroom
    added_volume = (payload.unit_volume or 0.0) * payload.quantity
    if wh.used_capacity + added_volume > wh.total_capacity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Adding this stock requires {added_volume} capacity units, exceeding available capacity ({wh.total_capacity - wh.used_capacity})",
        )

    item = InventoryItem(
        warehouse_id=warehouse_id,
        sku=payload.sku,
        product_name=payload.product_name,
        category=payload.category,
        quantity=payload.quantity,
        reorder_level=payload.reorder_level,
        unit=payload.unit,
        unit_volume=payload.unit_volume,
    )
    db.add(item)
    wh.used_capacity = round(wh.used_capacity + added_volume, 2)

    db.commit()
    db.refresh(item)
    return InventoryItemRead.model_validate(item)

