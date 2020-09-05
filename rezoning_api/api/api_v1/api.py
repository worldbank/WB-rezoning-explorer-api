from fastapi import APIRouter

from rezoning_api.api.api_v1.endpoints import demo, layers, lcoe, filter

api_router = APIRouter()
api_router.include_router(filter.router, tags=["filter"])
api_router.include_router(layers.router, tags=["layers"])
api_router.include_router(demo.router, tags=["demo"])
api_router.include_router(lcoe.router, tags=["lcoe"])
