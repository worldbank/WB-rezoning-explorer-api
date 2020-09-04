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

    all_true = np.prod(np.stack(np_filters), axis=0).astype(np.uint8)
    return (all_true, all_true != 0)

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
    # temporary handling of incorrect nodata value
    arr[arr == 65535] = 500000

    tile, new_mask = _filter(arr, filters)
    purple_tile = np.stack([
        tile * 45,
        tile * 39,
        tile * 88,
        (new_mask * 178).astype(np.uint8)
    ])

    content = render(purple_tile)
    return FilterResponse(content=content)
