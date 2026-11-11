from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.session import get_db
from app.models.order import Customer
from app.models.user import User, UserRole
from app.schemas.order import (
    CustomerCreate,
    CustomerRead,
    CustomerUpdate,
    PaginatedCustomersResponse,
)

router = APIRouter(prefix="/customers", tags=["Customer Management"])

ALL_CUSTOMER_READ_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
    UserRole.WAREHOUSE_MANAGER,
    UserRole.FLEET_MANAGER,
    UserRole.ANALYST,
)

CUSTOMER_MANAGE_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
)


@router.get(
    "",
    response_model=PaginatedCustomersResponse,
    summary="List customers with search and pagination",
)
def list_customers(
    search: Optional[str] = Query(None, description="Search by customer name, code, or city"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles(*ALL_CUSTOMER_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedCustomersResponse:
    query = select(Customer)

    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Customer.name.ilike(pattern),
                Customer.customer_code.ilike(pattern),
                Customer.city.ilike(pattern),
            )
        )
    if is_active is not None:
        query = query.where(Customer.is_active == is_active)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    customers = list(db.execute(query.order_by(Customer.customer_code.asc()).offset(skip).limit(limit)).scalars().all())

    return PaginatedCustomersResponse(
        items=[CustomerRead.model_validate(c) for c in customers],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "",
    response_model=CustomerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new customer",
)
def create_customer(
    payload: CustomerCreate,
    current_user: User = Depends(require_roles(*CUSTOMER_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> CustomerRead:
    existing = db.execute(select(Customer).where(Customer.customer_code == payload.customer_code)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Customer with code '{payload.customer_code}' already exists",
        )

    customer = Customer(
        customer_code=payload.customer_code,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        address_line=payload.address_line,
        city=payload.city,
        state=payload.state,
        postal_code=payload.postal_code,
        latitude=payload.latitude,
        longitude=payload.longitude,
        is_active=payload.is_active,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return CustomerRead.model_validate(customer)


@router.get(
    "/{customer_id}",
    response_model=CustomerRead,
    summary="Get customer details by ID",
)
def get_customer(
    customer_id: str,
    current_user: User = Depends(require_roles(*ALL_CUSTOMER_READ_ROLES)),
    db: Session = Depends(get_db),
) -> CustomerRead:
    customer = db.execute(select(Customer).where(Customer.id == customer_id)).scalar_one_or_none()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' not found",
        )
    return CustomerRead.model_validate(customer)


@router.patch(
    "/{customer_id}",
    response_model=CustomerRead,
    summary="Update customer details",
)
def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    current_user: User = Depends(require_roles(*CUSTOMER_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> CustomerRead:
    customer = db.execute(select(Customer).where(Customer.id == customer_id)).scalar_one_or_none()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' not found",
        )

    if payload.name is not None:
        customer.name = payload.name
    if payload.email is not None:
        customer.email = payload.email
    if payload.phone is not None:
        customer.phone = payload.phone
    if payload.address_line is not None:
        customer.address_line = payload.address_line
    if payload.city is not None:
        customer.city = payload.city
    if payload.state is not None:
        customer.state = payload.state
    if payload.postal_code is not None:
        customer.postal_code = payload.postal_code
    if payload.latitude is not None:
        customer.latitude = payload.latitude
    if payload.longitude is not None:
        customer.longitude = payload.longitude
    if payload.is_active is not None:
        customer.is_active = payload.is_active

    db.commit()
    db.refresh(customer)
    return CustomerRead.model_validate(customer)

