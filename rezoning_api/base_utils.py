"""base utility functions"""
from rezoning_api.models.zone import LCOE


def calc_crf(lr: LCOE):
    """
    Calculate Capital Recovery Factor (CRF)
    https://www.nrel.gov/analysis/tech-lcoe-documentation.html
    """
    return (lr.i * (1 + lr.i) ** lr.n) / (((1 + lr.i) ** lr.n) - 1)


def lcoe_generation(lr: LCOE, cf):
    """Calculate LCOE from Generation"""
    numerator = lr.cg * calc_crf(lr) + lr.omfg
    denominator = cf * 8760
    return (numerator / denominator) * 1000 + lr.omvg


def lcoe_interconnection(lr: LCOE, cf, ds):
    """Calculate LCOE from Interconnection"""
    numerator = ds / 1000 * (lr.ct * calc_crf(lr) + lr.omft) + lr.cs * calc_crf(lr)
    denominator = cf * 8760
    return numerator / denominator


def lcoe_road(lr: LCOE, cf, dr):
    """Calculate LCOE from Roads"""
    numerator = dr / 1000 * (lr.cr * calc_crf(lr) + lr.omfr)
    denominator = cf * 50 * 8760
    return numerator / denominator


def lcoe_total(lr: LCOE, cf, ds, dr):
    """Calculate total LCOE"""
    return (
        lcoe_generation(lr, cf) + lcoe_interconnection(lr, cf, ds) + lcoe_road(lr, cf, dr)
    )


def get_lcoe_min_max(cmm, filters, lcoe):
    """Calculate LCOE min max based on other input data"""
    if filters.f_roads:
        road_min = max(cmm["roads"]["min"], float(filters.f_roads.split(",")[0]))
        road_max = min(cmm["roads"]["max"], float(filters.f_roads.split(",")[1]))
    else:
        road_min = cmm["roads"]["min"]
        road_max = cmm["roads"]["max"]

    if filters.f_grid:
        grid_min = max(cmm["grid"]["min"], float(filters.f_grid.split(",")[0]))
        grid_max = min(cmm["grid"]["max"], float(filters.f_grid.split(",")[1]))
    else:
        grid_min = cmm["grid"]["min"]
        grid_max = cmm["grid"]["max"]

    return dict(
        min=lcoe_total(lcoe, cmm[lcoe.capacity_factor]["max"], grid_min, road_min),
        max=lcoe_total(
            lcoe, 0.25 * cmm[lcoe.capacity_factor]["max"], grid_max, road_max
        ),
    )
