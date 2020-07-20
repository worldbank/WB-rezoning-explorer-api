"""Filter endpoints."""

from fastapi import APIRouter, Request
from rio_tiler.io import cogeo
from rio_tiler.utils import render
import numpy as np

from rezoning_api.models.filter import FilterResponse

router = APIRouter()

def _filter(array, filters):
    # filters look like ?filters=0,10000|0,10000
    arr_filters = filters.split('|')

    return np.multiply(
        np.logical_and(
            array[0] > int(arr_filters[0].split(',')[0]),
            array[0] < int(arr_filters[0].split(',')[1]),
        ),
        np.logical_and(
            array[1] > int(arr_filters[1].split(',')[0]),
            array[1] < int(arr_filters[1].split(',')[1]),
        ),
    )

@router.get(
    "/filter/{country}/{z}/{x}/{y}.png",
    responses={200: dict(description="return a filtered tile given certain parameters")},
    response_class=FilterResponse,
    name="filter"
)
def filter(country: str, z: int, x: int, y:int, filters: str):
    """Return dataset info."""
    arr, mask = cogeo.tile(
        's3://gre-processed-data/multiband/mb.tif',
        x,
        y,
        z,
        tilesize=256
    )

    tile = _filter(arr, filters)

    content = render(tile.astype(np.uint8) * 255)

    return FilterResponse(content=content)
