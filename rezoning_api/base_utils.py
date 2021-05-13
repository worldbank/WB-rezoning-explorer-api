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
        lcoe_generation(lr, cf)
        + lcoe_interconnection(lr, cf, ds)
        + lcoe_road(lr, cf, dr)
    )
