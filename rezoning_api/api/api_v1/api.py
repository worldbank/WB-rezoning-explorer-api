from fastapi import APIRouter

from rezoning_api.api.api_v1.endpoints import filter, demo

api_router = APIRouter()
api_router.include_router(filter.router, tags=["filter"])
api_router.include_router(demo.router, tags=["demo"])