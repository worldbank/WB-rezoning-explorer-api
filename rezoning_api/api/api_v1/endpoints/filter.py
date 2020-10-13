"""Filter endpoints."""

from fastapi import APIRouter
from rio_tiler.io import cogeo
from rio_tiler.utils import render
import numpy as np
import json

from rezoning_api.core.config import BUCKET
from rezoning_api.models.tiles import TileResponse
from rezoning_api.api.utils import _filter, s3_get, get_min_max

router = APIRouter()


@router.get(
    "/filter/{z}/{x}/{y}.png",
    responses={
        200: dict(description="return a filtered tile given certain parameters")
    },
    response_class=TileResponse,
    name="filter",
)
def filter(z: int, x: int, y: int, filters: str, color: str):
    """Return filtered tile."""
    filter_arr, _mask = cogeo.tile(
        f"s3://{BUCKET}/multiband/distance.tif", x, y, z, tilesize=256
    )
    calc_arr, _mask2 = cogeo.tile(
        f"s3://{BUCKET}/multiband/calc.tif", x, y, z, tilesize=256
    )
    arr = np.concatenate([filter_arr, calc_arr], axis=0)

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
    return TileResponse(content=content)


@router.get("/filter/layers/")
def get_layers():
    """Return layers list for filters"""
    distance_layers = s3_get(BUCKET, "multiband/distance.json")
    calc_layers = s3_get(BUCKET, "multiband/calc.json")

    distance_min, distance_max = get_min_max(s3_get(BUCKET, "multiband/distance.vrt"))
    calc_min, calc_max = get_min_max(s3_get(BUCKET, "multiband/calc.vrt"))

    # combine distance and calc
    layers = json.loads(distance_layers).get("layers") + json.loads(calc_layers).get(
        "layers"
    )
    minmaxes = zip(
        distance_min + calc_min,
        distance_max + calc_max,
    )

    return {
        layer: dict(min=minmax[0], max=minmax[1])
        for layer, minmax in zip(layers, minmaxes)
    }
