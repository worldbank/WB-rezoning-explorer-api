"""LCOE endpoints."""

from fastapi import APIRouter
from shapely.geometry import shape

from rezoning_api.models.zone import ZoneRequest
from rezoning_api.api.utils import (
    lcoe_generation,
    lcoe_interconnection,
    lcoe_road,
    get_capacity_factor,
    get_distances,
)

router = APIRouter()

@router.post(
    "/zone/",
    responses={200: dict(description="return an LCOE calculation for a given area")},
)
def zone(query: ZoneRequest, filters: str):
    """calculate LCOE, then weight for zone score"""
    # decide which capacity factor tif to pull from
    cf_tif_loc = "gsa.tif"
    if query.lcoe.turbine_type:
        cf_tif_loc = "gwa.tif"

    # aoi geometry
    geom = shape(query.aoi)

    # spatial temporal inputs
    ds, dr, mask = get_distances(geom, filters)
    cf = get_capacity_factor(cf_tif_loc, geom, query.lcoe.turbine_type)

    # lcoe component calculation
    lg = lcoe_generation(query.lcoe, cf)
    li = lcoe_interconnection(query.lcoe, cf, ds)
    lr = lcoe_road(query.lcoe, cf, dr)
    lcoe = (lg + li + lr)[mask]

    # zone score
    zone_score = (
        query.weights.lcoe_gen * lg.sum() +
        query.weights.lcoe_transmission * li.sum() +
        query.weights.lcoe_road * lr.sum() +
        query.weights.distance_load * ds.sum() +
        # technology_colocation: float = 0.5
        # human_footprint: float = 0.5
        # pop_density: float = 0.5
        # slope: float = 0.5
        # land_use: float = 0.5
        query.weights.capacity_value * cf.sum()
    )

    return dict(
        lcoe=float(lcoe.sum()) / 1000, # GWh
        lcoe_density=float(lcoe.mean()) / (500 ** 2), # kWh / sq. meter
        zone_score=zone_score
    ) 
