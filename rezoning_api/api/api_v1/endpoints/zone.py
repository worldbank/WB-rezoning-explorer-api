"""LCOE endpoints."""

from fastapi import APIRouter, Depends, HTTPException
import numpy as np
import numpy.ma as ma
from shapely.geometry import shape

from rezoning_api.models.zone import ZoneRequest, ZoneResponse, Filters, Weights
from rezoning_api.utils import calc_score

router = APIRouter()


@router.post(
    "/zone/",
    responses={200: dict(description="return an LCOE calculation for a given area")},
    response_model=ZoneResponse,
)
@router.post(
    "/zone/{country_id}",
    responses={200: dict(description="return an LCOE calculation for a given area")},
    response_model=ZoneResponse,
)
def zone(query: ZoneRequest, country_id: str = "AFG", filters: Filters = Depends()):
    """calculate LCOE and weight for zone score"""
    data, mask, extras = calc_score(
        country_id,
        query.lcoe,
        query.weights,
        filters,
        geometry=query.aoi.dict(),
        ret_extras=True,
    )

    lcoe = extras["lcoe"]
    cf = extras["cf"]

    # mask everything with filters
    lcoe_m = ma.masked_array(lcoe, ~mask)
    cf_m = ma.masked_array(cf, ~mask)
    data_m = ma.masked_array(data, ~mask)

    # installed capacity potential
    icp = query.lcoe.landuse * shape(query.aoi.dict()).area

    # annual energy generation potential (divide by 1000 for GWh)
    generation_potential = query.lcoe.landuse * cf_m.sum() * 8760 / 1000

    # zone score
    zs = data_m.mean()
    zs = 0.00001 if np.isnan(zs) else zs

    # suitable area
    suitable_area = mask.sum() * (500 ** 2)

    if not lcoe_m.mean():
        raise HTTPException(status_code=404, detail="No suitable area after filtering")

    return dict(
        lcoe=lcoe_m.mean(),
        zone_score=zs,
        generation_potential=generation_potential,
        icp=icp,
        cf=cf_m.mean(),
        zone_output_density=generation_potential / suitable_area,
        suitable_area=suitable_area,
    )


@router.get("/zone/schema", name="weights_schema")
def get_filter_schema():
    """Return weights schema"""
    return Weights.schema()["properties"]
