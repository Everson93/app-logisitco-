from fastapi import APIRouter

from app.api.v1 import allocation_rules, calculations, dashboard, dimensions, health, imports

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(dimensions.router)
api_router.include_router(imports.router)
api_router.include_router(allocation_rules.router)
api_router.include_router(calculations.router)
api_router.include_router(dashboard.router)
