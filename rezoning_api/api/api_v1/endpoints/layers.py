"""Filter endpoints."""

from fastapi import APIRouter
from rio_tiler.io import COGReader
from rio_tiler.utils import render, linear_rescale
from rio_tiler.colormap import cmap
import numpy as np

from rezoning_api.models.tiles import TileResponse
from rezoning_api.api.utils import get_layer_location

router = APIRouter()


@router.get(
    "/layers/{id}/{z}/{x}/{y}.png",
    responses={200: dict(description="return a tile for a given layer")},
    response_class=TileResponse,
    name="layers",
)
def filter(id: str, z: int, x: int, y: int, colormap: str):
    """Return a tile from a layer."""
    loc, idx = get_layer_location(id)
    with COGReader(loc) as cog:
        data, mask = cog.tile(x, y, z, tilesize=256, indexes=[idx + 1])

    scaled = linear_rescale(data, out_range=(0, 255)).astype(np.uint8)
    colormap = cmap.get(colormap)
    content = render(scaled, mask, colormap=colormap)
    return TileResponse(content=content)
