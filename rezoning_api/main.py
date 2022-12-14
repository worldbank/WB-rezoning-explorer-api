"""rezoning_api app."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from rezoning_api import version
from rezoning_api.core import config
from rezoning_api.api.api_v1.api import api_router

app = FastAPI(
    title=config.PROJECT_NAME,
    openapi_url="/api/v1/openapi.json",
    description="Server for filtering and statistics on Renewable Energy Data (test)",
    version=version,
)

# Set all CORS enabled origins
if config.BACKEND_CORS_ORIGINS:
    origins = [origin.strip() for origin in config.BACKEND_CORS_ORIGINS.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        max_age=86400
    )


# force cache the cors options request using middleware
@app.middleware("http")
async def cache_options(request: Request, call_next):
    """ cache options """
    response = await call_next(request)
    if request.method == 'OPTIONS':
        # expires is ignored with a cache control header.
        response.headers['Cache-Control'] = "public, max-age=86400"
        response.headers['vary'] = 'origin'

    return response


app.add_middleware(GZipMiddleware, minimum_size=0)
app.include_router(api_router, prefix=config.API_VERSION_STR)


@app.get("/ping", description="Health Check")
def ping():
    """Health check."""
    return {"ping": "pong!"}
