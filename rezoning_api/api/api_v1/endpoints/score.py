"""score endpoints."""

from fastapi import APIRouter, Depends
from rio_tiler.colormap import cmap
from rio_tiler.utils import render, linear_rescale
import numpy as np

from rezoning_api.models.tiles import TileResponse
from rezoning_api.models.zone import LCOE, Weights, Filters
from rezoning_api.utils import calc_score
from rezoning_api.db.country import get_country_geojson, get_region_geojson

router = APIRouter()


@router.get(
    "/score/{country_id}/{resource}/{z}/{x}/{y}.png",
    responses={200: dict(description="return a score tile given certain parameters")},
    response_class=TileResponse,
    name="score",
)
def score(
    country_id: str,
    z: int,
    x: int,
    y: int,
    colormap: str,
    resource: str,
    filters: Filters = Depends(),
    lcoe: LCOE = Depends(),
    weights: Weights = Depends(),
    offshore: bool = False,
):
    """Return score tile."""
    # potentially mask by country
    geometry = None
    if country_id:
        # TODO: early return for tiles outside country bounds
        if len(country_id) == 3:
            feat = get_country_geojson(country_id, offshore)
        else:
            feat = get_region_geojson(country_id, offshore)
        geometry = feat.geometry.dict()

    data, mask = calc_score(
        country_id, resource, lcoe, weights, filters, x=x, y=y, z=z, geometry=geometry
    )

    tile = linear_rescale(data, in_range=[0, 1], out_range=[0, 255]).astype(np.uint8)

    colormap = cmap.get(colormap)
    content = render(tile, mask=mask.squeeze() * 255, colormap=colormap)
    return TileResponse(content=content)
