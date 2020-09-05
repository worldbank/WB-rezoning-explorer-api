import numpy as np
import rasterio
from rasterio.windows import from_bounds
from shapely.ops import transform
import pyproj

from rezoning_api.models.lcoe import LCOERequest
from rezoning_api.core.config import BUCKET


def calc_crf(l: LCOERequest):
    # https://www.nrel.gov/analysis/tech-lcoe-documentation.html
    return (l.i * (1 + l.i) ** l.n) / (((1 + l.i) ** l.n) - 1)


def lcoe_generation(l: LCOERequest, cf):
    numerator = l.cg * calc_crf(l) + l.omfg
    denominator = cf * 8760
    return (numerator / denominator) + l.omvg


def lcoe_interconnection(l: LCOERequest, cf, ds):
    numerator = ds * (l.ct * calc_crf(l) + l.omft) + l.cs * calc_crf(l)
    denominator = cf * 8760
    return numerator / denominator


def lcoe_road(l: LCOERequest, cf, dr):
    numerator = dr * (l.cr * calc_crf(l) + l.omfr)
    denominator = cf * 50 * 8760
    return numerator / denominator


def get_capacity_factor(cf_tif_loc: str, geom, turbine_type=None):
    with rasterio.open(f"s3://{BUCKET}/multiband/{cf_tif_loc}") as cf_tif:
        # find the window of our aoi
        project = pyproj.Transformer.from_proj(
            pyproj.Proj("epsg:4326"),  # source coordinate system
            pyproj.Proj(cf_tif.crs),  # destination coordinate system
        )
        g2 = transform(project.transform, geom)
        window = from_bounds(*g2.bounds, cf_tif.transform)

        # capacity factor band for solar (1)
        # for wind, use turbine_type
        cfb = 1 if not turbine_type else turbine_type

        return cf_tif.read(cfb, window=window)


def get_distances(geom, filters: str):
    with rasterio.open(f"s3://{BUCKET}/multiband/distance.tif") as distance:
        # find the window of our aoi
        project = pyproj.Transformer.from_proj(
            pyproj.Proj("epsg:4326"),  # source coordinate system
            pyproj.Proj(distance.crs),  # destination coordinate system
        )
        g2 = transform(project.transform, geom)
        window = from_bounds(*g2.bounds, distance.transform)

        # read all bands and filter
        data = np.nan_to_num(distance.read(window=window))
        _, mask = _filter(data, filters)

        # distance from grid, TODO: remove hardcoded band number
        ds = data[3]
        # distance from road, TODO: remove hardcoded band number
        dr = data[4]

        return (ds, dr, mask)


def _filter(array, filters: str):
    # temporary handling of incorrect nodata value
    array[array == 65535] = 500000
    # filters look like ?filters=0,10000|0,10000...

    arr_filters = filters.split("|")
    np_filters = []
    for i, af in enumerate(arr_filters):
        tmp = np.logical_and(
            array[i] >= int(af.split(",")[0]), array[i] <= int(af.split(",")[1]),
        )
        np_filters.append(tmp)

    all_true = np.prod(np.stack(np_filters), axis=0).astype(np.uint8)
    return (all_true, all_true != 0)
