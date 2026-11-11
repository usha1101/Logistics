from fastapi import APIRouter
from app.api.admin import router as admin_router
from app.api.agents import router as agents_router
from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router
from app.api.customers import router as customers_router
from app.api.dashboard import router as dashboard_router
from app.api.disruptions import router as disruptions_router
from app.api.fleet import router as fleet_router
from app.api.health import router as health_router
from app.api.inventory import router as inventory_router
from app.api.network import router as network_router
from app.api.orders import router as orders_router
from app.api.recovery import router as recovery_router
from app.api.reports import router as reports_router
from app.api.simulations import router as simulations_router
from app.api.warehouses import router as warehouses_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="", tags=["Health"])
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(network_router)
api_router.include_router(dashboard_router)
api_router.include_router(warehouses_router)
api_router.include_router(inventory_router)
api_router.include_router(fleet_router)
api_router.include_router(customers_router)
api_router.include_router(orders_router)
api_router.include_router(simulations_router)
api_router.include_router(disruptions_router)
api_router.include_router(agents_router)
api_router.include_router(recovery_router)
api_router.include_router(analytics_router)
api_router.include_router(reports_router)

__all__ = ["api_router"]

