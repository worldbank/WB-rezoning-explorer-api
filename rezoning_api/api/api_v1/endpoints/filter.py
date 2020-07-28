"""Filter endpoints."""

from fastapi import APIRouter, Request
from rio_tiler.io import cogeo
from rio_tiler.utils import render
import numpy as np

from rezoning_api.core.config import BUCKET
from rezoning_api.models.filter import FilterResponse

router = APIRouter()

def _filter(array, filters):
    # filters look like ?filters=0,10000|0,10000...
    arr_filters = filters.split('|')
    np_filters = []
    for i, af in enumerate(arr_filters):
        tmp = np.logical_and(
            array[i] >= int(af.split(',')[0]),
            array[i] <= int(af.split(',')[1]),
        )
        np_filters.append(tmp)

    return np.prod(np.stack(np_filters), axis=0)

@router.get(
    "/filter/{country}/{z}/{x}/{y}.png",
    responses={200: dict(description="return a filtered tile given certain parameters")},
    response_class=FilterResponse,
    name="filter"
)
def filter(country: str, z: int, x: int, y:int, filters: str):
    """Return dataset info."""
    arr, mask = cogeo.tile(
        f's3://{BUCKET}/multiband/distance.tif',
        x,
        y,
        z,
        tilesize=256
    )

    tile = _filter(arr, filters)
    content = render(tile.astype(np.uint8) * 255)
    return FilterResponse(content=content)
