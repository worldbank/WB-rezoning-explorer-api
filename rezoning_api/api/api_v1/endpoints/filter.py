"""Filter endpoints."""

from fastapi import APIRouter
from rio_tiler.io import cogeo
from rio_tiler.utils import render
import numpy as np
import json

from rezoning_api.core.config import BUCKET
from rezoning_api.models.filter import FilterResponse
from rezoning_api.api.utils import _filter, s3_get

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
    arr, _mask = cogeo.tile(
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


@router.get("/filter/layers/")
def get_layers():
    """Return layers list for filters"""
    layers = s3_get(BUCKET, "multiband/distance.json")
    calc_layers = s3_get(BUCKET, "multiband/calc.json")
    return json.loads(layers).get("layers") + json.loads(calc_layers).get("layers")
