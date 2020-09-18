"""LCOE endpoints."""

from fastapi import APIRouter, Depends
from mercantile import feature, Tile
from rio_tiler.colormap import cmap
from rio_tiler.utils import render, linear_rescale
import numpy as np

from rezoning_api.models.tiles import TileResponse
from rezoning_api.models.zone import LCOE
from rezoning_api.api.utils import (
    lcoe_generation,
    lcoe_interconnection,
    lcoe_road,
    get_capacity_factor,
    get_distances,
)

router = APIRouter()


@router.get(
    "/lcoe/{z}/{x}/{y}.png",
    responses={
        200: dict(description="return a filtered tile given certain parameters")
    },
    response_class=TileResponse,
    name="filter",
)
def lcoe(z: int, x: int, y: int, filters: str, colormap: str, lcoe: LCOE = Depends()):
    """Return LCOE tile."""
    # get AOI from tile
    aoi = feature(Tile(x, y, z))["geometry"]

    # calculate LCOE (from zone.py, TODO: DRY)
    # spatial temporal inputs
    ds, dr, _calc, mask = get_distances(aoi, filters)
    cf = get_capacity_factor(aoi, lcoe.turbine_type)

    # lcoe component calculation
    lg = lcoe_generation(lcoe, cf)
    li = lcoe_interconnection(lcoe, cf, ds)
    lr = lcoe_road(lcoe, cf, dr)
    lcoe = (lg + li + lr)[mask]

    tile = linear_rescale(lcoe, out_range=[0, 255]).astype(np.uint8)

    colormap = cmap.get(colormap)
    content = render(tile, mask=mask, colormap=colormap)
    return TileResponse(content=content)
