"""score endpoints."""

from fastapi import APIRouter, Depends
from mercantile import feature, Tile
from rio_tiler.colormap import cmap
from rio_tiler.utils import render, linear_rescale
import numpy as np
from geojson_pydantic.geometries import Polygon

from rezoning_api.models.tiles import TileResponse
from rezoning_api.models.zone import LCOE, Weights
from rezoning_api.api.utils import calc_score

router = APIRouter()


@router.get(
    "/score/{country}/{z}/{x}/{y}.png",
    responses={200: dict(description="return a score tile given certain parameters")},
    response_class=TileResponse,
    name="score",
)
def score(
    country: str,
    z: int,
    x: int,
    y: int,
    filters: str,
    colormap: str,
    lcoe: LCOE = Depends(),
    weights: Weights = Depends(),
):
    """Return score tile."""
    # get AOI from tile
    aoi = Polygon(**feature(Tile(x, y, z))["geometry"])

    data, mask = calc_score(country, aoi.dict(), lcoe, weights, filters, tilesize=256)
    print(data.shape, mask.shape)
    tile = linear_rescale(data, in_range=[0, 1], out_range=[0, 255]).astype(np.uint8)
    print(tile.shape)
    colormap = cmap.get(colormap)
    content = render(tile, mask=~mask * 255, colormap=colormap)
    return TileResponse(content=content)
