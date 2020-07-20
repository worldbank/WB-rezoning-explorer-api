"""Filter endpoints."""

from fastapi import APIRouter, Request
from rio_tiler.io import cogeo
from rio_tiler.utils import render
import numpy as np

from rezoning_api.models.filter import FilterRequest, FilterResponse

router = APIRouter()

def _filter(array, query):
    return np.multiply(
        np.logical_and(
            array[0] > query.road_distance_min,
            array[0] < query.road_distance_max,
        ),
        np.logical_and(
            array[1] > query.port_distance_min,
            array[1] < query.port_distance_max,
        ),
    )

@router.post(
    "/filter/{country}/{z}/{x}/{y}.png",
    responses={200: dict(description="return a filtered tile given certain parameters")},
    response_class=FilterResponse,
)
def get_dataset(query: FilterRequest, z: int, x: int, y:int):
    """Return dataset info."""
    arr, mask = cogeo.tile(
        's3://gre-processed-data/multiband/mb.tif',
        x,
        y,
        z,
        tilesize=256
    )

    tile = _filter(arr, query)

    content = render(tile.astype(np.uint8) * 255)

    return FilterResponse(content=content)
