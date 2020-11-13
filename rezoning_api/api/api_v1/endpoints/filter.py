"""Filter endpoints."""

from fastapi import APIRouter
from rio_tiler.io import COGReader
from rio_tiler.utils import render
import numpy as np

from rezoning_api.core.config import BUCKET
from rezoning_api.models.tiles import TileResponse
from rezoning_api.api.utils import _filter, flat_layers
from rezoning_api.db.country import get_country_min_max

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
    with COGReader(f"s3://{BUCKET}/multiband/distance.tif") as cog:
        filter_arr, _mask = cog.tile(x, y, z, tilesize=256)
    with COGReader(f"s3://{BUCKET}/multiband/calc.tif") as cog:
        calc_arr, _mask2 = cog.tile(x, y, z, tilesize=256)
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
    return [layer for layer in flat_layers() if not layer.startswith(("gwa", "gsa"))]


@router.get("/filter/{country_id}/layers")
def get_country_layers(country_id: str):
    """Return min/max for country layers"""
    minmax = get_country_min_max(country_id)
    keys = list(minmax.keys())
    [minmax.pop(key) for key in keys if key.startswith(("gwa", "gsa"))]
    return minmax
