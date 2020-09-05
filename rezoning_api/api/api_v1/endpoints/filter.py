"""Filter endpoints."""

from fastapi import APIRouter, Request
from rio_tiler.io import cogeo
from rio_tiler.utils import render
import numpy as np

from rezoning_api.core.config import BUCKET
from rezoning_api.models.filter import FilterResponse
from rezoning_api.api.utils import _filter

router = APIRouter()


@router.get(
    "/filter/{z}/{x}/{y}.png",
    responses={
        200: dict(description="return a filtered tile given certain parameters")
    },
    response_class=FilterResponse,
    name="filter",
)
def filter(z: int, x: int, y: int, filters: str, color: str):
    """Return dataset info."""
    arr, mask = cogeo.tile(
        f"s3://{BUCKET}/multiband/distance.tif", x, y, z, tilesize=256
    )

    # color like 45,39,88,178 (RGBA)
    color_list = list(map(lambda x: int(x), color.split(",")))

    tile, new_mask = _filter(arr, filters)
    color_tile = np.stack(
        [
            tile * color_list[0],
            tile * color_list[1],
            tile * color_list[2],
            (new_mask * color_list[3]).astype(np.uint8),
        ]
    )

    content = render(color_tile)
    return FilterResponse(content=content)
