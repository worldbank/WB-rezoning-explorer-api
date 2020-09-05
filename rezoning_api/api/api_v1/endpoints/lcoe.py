"""LCOE endpoints."""

from fastapi import APIRouter
import numpy as np
from shapely.geometry import shape
import time


from rezoning_api.core.config import BUCKET
from rezoning_api.models.lcoe import LCOERequest
from rezoning_api.api.utils import (
    lcoe_generation,
    lcoe_interconnection,
    lcoe_road,
    get_capacity_factor,
    get_distances,
)

router = APIRouter()


@router.post(
    "/lcoe/",
    responses={200: dict(description="return an LCOE calculation for a given area")},
)
def lcoe(query: LCOERequest, filters: str):
    # decide which capacity factor tif to pull from
    cf_tif_loc = "gsa.tif"
    if query.turbine_type:
        cf_tif_loc = "gwa.tif"

    # aoi geometry
    geom = shape(query.aoi)

    # spatial temporal inputs
    ds, dr, mask = get_distances(geom, filters)
    cf = get_capacity_factor(cf_tif_loc, geom, query.turbine_type)

    # lcoe component calculation + histogram
    lcoe = (
        lcoe_generation(query, cf)
        + lcoe_interconnection(query, cf, ds)
        + lcoe_road(query, cf, dr)
    )

    return dict(lcoe=float(lcoe[mask].sum()))
