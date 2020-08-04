from fastapi import APIRouter

from rezoning_api.api.api_v1.endpoints import filter, demo, layers

api_router = APIRouter()
api_router.include_router(filter.router, tags=["filter"])
api_router.include_router(layers.router, tags=["layers"])
api_router.include_router(demo.router, tags=["demo"])