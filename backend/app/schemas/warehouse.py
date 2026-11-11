from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.warehouse import MovementType, WarehouseStatus, WarehouseType
from app.schemas.network import NetworkNodeRead


class WarehouseBase(BaseModel):
    warehouse_code: str = Field(..., min_length=2, max_length=32)
    warehouse_type: WarehouseType = WarehouseType.DISTRIBUTION_CENTER
    total_capacity: float = Field(..., gt=0, description="Total storage volume/capacity in cubic meters or units")
    status: WarehouseStatus = WarehouseStatus.OPERATIONAL
    manager_name: Optional[str] = Field(None, max_length=128)
    contact_number: Optional[str] = Field(None, max_length=32)
    operating_hours: Optional[Dict[str, Any]] = None


class WarehouseCreate(WarehouseBase):
    network_node_id: str = Field(..., description="ID of an existing NetworkNode with type WAREHOUSE")


class WarehouseUpdate(BaseModel):
    warehouse_type: Optional[WarehouseType] = None
    total_capacity: Optional[float] = Field(None, gt=0)
    status: Optional[WarehouseStatus] = None
    manager_name: Optional[str] = Field(None, max_length=128)
    contact_number: Optional[str] = Field(None, max_length=32)
    operating_hours: Optional[Dict[str, Any]] = None


class WarehouseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    network_node_id: str
    warehouse_code: str
    warehouse_type: str
    total_capacity: float
    used_capacity: float
    status: str
    manager_name: Optional[str] = None
    contact_number: Optional[str] = None
    operating_hours: Optional[Dict[str, Any]] = None
    network_node: Optional[NetworkNodeRead] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @computed_field
    def available_capacity(self) -> float:
        return max(0.0, round(self.total_capacity - self.used_capacity, 2))

    @computed_field
    def utilization_percentage(self) -> float:
        if self.total_capacity <= 0:
            return 0.0
        return round((self.used_capacity / self.total_capacity) * 100, 2)


class PaginatedWarehousesResponse(BaseModel):
    items: List[WarehouseRead]
    total: int
    skip: int
    limit: int


class InventoryItemCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=64, description="Stock Keeping Unit")
    product_name: str = Field(..., min_length=1, max_length=128)
    category: Optional[str] = Field(None, max_length=64)
    quantity: int = Field(default=0, ge=0)
    reorder_level: int = Field(default=10, ge=0)
    unit: str = Field(default="units", max_length=32)
    unit_volume: Optional[float] = Field(None, gt=0, description="Volume per unit to calculate warehouse capacity")


class InventoryItemUpdate(BaseModel):
    product_name: Optional[str] = Field(None, min_length=1, max_length=128)
    category: Optional[str] = Field(None, max_length=64)
    reorder_level: Optional[int] = Field(None, ge=0)
    unit: Optional[str] = Field(None, max_length=32)
    unit_volume: Optional[float] = Field(None, gt=0)


class InventoryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    warehouse_id: str
    sku: str
    product_name: str
    category: Optional[str] = None
    quantity: int
    reorder_level: int
    unit: str
    unit_volume: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @computed_field
    def status(self) -> Literal["OUT_OF_STOCK", "LOW_STOCK", "IN_STOCK"]:
        if self.quantity == 0:
            return "OUT_OF_STOCK"
        elif self.quantity <= self.reorder_level:
            return "LOW_STOCK"
        return "IN_STOCK"


class PaginatedInventoryResponse(BaseModel):
    items: List[InventoryItemRead]
    total: int
    skip: int
    limit: int


class StockMovementCreate(BaseModel):
    movement_type: MovementType
    quantity: int = Field(..., gt=0, description="Magnitude of units to receive, dispatch, or adjust")
    adjustment_type: Optional[Literal["INCREASE", "DECREASE"]] = Field(
        None,
        description="Must be provided when movement_type is STOCK_ADJUSTMENT ('INCREASE' or 'DECREASE')",
    )
    reference: Optional[str] = Field(None, max_length=128, description="PO/Invoice/Order reference")
    notes: Optional[str] = Field(None, max_length=255)


class StockMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    inventory_item_id: str
    movement_type: str
    quantity: int
    previous_quantity: int
    new_quantity: int
    reference: Optional[str] = None
    notes: Optional[str] = None
    created_by_user_id: Optional[str] = None
    created_at: datetime


class PaginatedMovementsResponse(BaseModel):
    items: List[StockMovementRead]
    total: int
    skip: int
    limit: int


class WarehouseSummaryResponse(BaseModel):
    total_warehouses: int
    operational_warehouses: int
    degraded_warehouses: int
    closed_warehouses: int
    total_storage_capacity: float
    used_storage_capacity: float
    available_storage_capacity: float
    average_utilization_percentage: Optional[float] = None
    total_inventory_records: int
    low_stock_items: int
    out_of_stock_items: int
    generated_at: str
    data_source: Literal["SIMULATED"] = "SIMULATED"

