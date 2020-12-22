"""LCOE endpoints."""

from rezoning_api.db.country import get_country_min_max
from fastapi import APIRouter, Depends
from mercantile import feature, Tile
from rio_tiler.colormap import cmap
from rio_tiler.utils import render, linear_rescale
import numpy as np
from geojson_pydantic.geometries import Polygon

from rezoning_api.models.tiles import TileResponse
from rezoning_api.models.zone import LCOE, Filters
from rezoning_api.db.cf import get_capacity_factor_options
from rezoning_api.utils import (
    lcoe_generation,
    lcoe_interconnection,
    lcoe_road,
    get_capacity_factor,
    get_distances,
)

router = APIRouter()


@router.get(
    "/lcoe/{country_id}/{z}/{x}/{y}.png",
    responses={200: dict(description="return an LCOE tile given certain parameters")},
    response_class=TileResponse,
    name="lcoe",
)
def lcoe(
    z: int,
    x: int,
    y: int,
    colormap: str,
    country_id: str,
    filters: Filters = Depends(),
    lcoe: LCOE = Depends(),
):
    """Return LCOE tile."""
    # get AOI from tile
    aoi = Polygon(**feature(Tile(x, y, z))["geometry"])

    # calculate LCOE (from zone.py, TODO: DRY)
    # spatial temporal inputs
    ds, dr, _calc, mask = get_distances(aoi.dict(), filters, tilesize=256)
    cf = get_capacity_factor(aoi.dict(), lcoe.capacity_factor, tilesize=256)

    # lcoe component calculation
    lg = lcoe_generation(lcoe, cf)
    li = lcoe_interconnection(lcoe, cf, ds)
    lr = lcoe_road(lcoe, cf, dr)
    lcoe_total = lg + li + lr

    # get country min max for scaling
    country_min_max = get_country_min_max(country_id)
    lcoe_min_max = country_min_max["lcoe"][lcoe.capacity_factor]["total"]

    tile = linear_rescale(
        lcoe_total.values,
        in_range=[lcoe_min_max["min"], lcoe_min_max["max"]],
        out_range=[0, 255],
    ).astype(np.uint8)

    colormap = cmap.get(colormap)
    content = render(tile, mask=mask.squeeze() * 255, colormap=colormap)
    return TileResponse(content=content)


@router.get("/lcoe/schema", name="lcoe_schema")
def get_filter_schema():
    """Return lcoe schema"""
    schema = LCOE.schema()["properties"]
    schema["capacity_factor"]["options"] = get_capacity_factor_options()
    return schema
