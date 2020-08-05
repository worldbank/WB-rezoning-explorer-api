"""LCOE endpoints."""

from fastapi import APIRouter
import numpy as np
from shapely.geometry import shape


from rezoning_api.core.config import BUCKET
from rezoning_api.models.lcoe import LCOERequest
from rezoning_api.api.utils import crf, lcoe_gen, lcoe_inter, lcoe_road, get_cf, get_dist

router = APIRouter()


@router.post(
    "/lcoe/",
    responses={200: dict(description="return an LCOE calculation for a given area")},
)
def lcoe(query: LCOERequest):
    # decide which capacity factor tif to pull from
    cf_tif_loc = 'gsa.tif'
    # if LCOERequest.turbine_type:
    #     cf_tif_loc = 'gwa.tif'

    # aoi geometry
    geom = shape(query.aoi)

    # spatial temporal inputs
    cf = get_cf(cf_tif_loc, geom)
    ds, dr = get_dist(geom)    

    # lcoe component calculation + histogram
    lcoe = lcoe_gen(query, cf) + lcoe_inter(query, cf, ds) + lcoe_road(query, cf, dr)
    hist, bins = np.histogram(lcoe)

    return dict(
        lcoe=lcoe.sum(),
        hist=list(hist.astype(np.float)),
        bins=list(bins.astype(np.float))
    )