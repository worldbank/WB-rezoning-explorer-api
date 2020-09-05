"""api utility functions"""
import boto3
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio import features
from shapely.ops import transform
import pyproj

from rezoning_api.models.zone import LCOE
from rezoning_api.core.config import BUCKET

s3 = boto3.client("s3")


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
    return (numerator / denominator) + lr.omvg


def lcoe_interconnection(lr: LCOE, cf, ds):
    """Calculate LCOE from Interconnection"""
    numerator = ds * (lr.ct * calc_crf(lr) + lr.omft) + lr.cs * calc_crf(lr)
    denominator = cf * 8760
    return numerator / denominator


def lcoe_road(lr: LCOE, cf, dr):
    """Calculate LCOE from Roads"""
    numerator = dr * (lr.cr * calc_crf(lr) + lr.omfr)
    denominator = cf * 50 * 8760
    return numerator / denominator


def get_capacity_factor(cf_tif_loc: str, geom, turbine_type=None):
    """Calculate Capacity Factor"""
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
    """Get filtered masks and distance arrays"""
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

        # mask by geometry
        geom_mask = _rasterize_geom(
            g2, mask.shape, distance.window_transform(window), all_touched=True
        )
        final_mask = (mask & geom_mask).astype(np.bool)

        # distance from grid, TODO: remove hardcoded band number
        ds = data[3]
        # distance from road, TODO: remove hardcoded band number
        dr = data[4]

        return (ds, dr, final_mask)


def _filter(array, filters: str):
    """
    filter array based on per-band ranges, supplied as path parameter
    filters look like ?filters=0,10000|0,10000...
    """
    # temporary handling of incorrect nodata value
    array[array == 65535] = 500000

    arr_filters = filters.split("|")
    np_filters = []
    for i, af in enumerate(arr_filters):
        tmp = np.logical_and(
            array[i] >= int(af.split(",")[0]), array[i] <= int(af.split(",")[1]),
        )
        np_filters.append(tmp)

    all_true = np.prod(np.stack(np_filters), axis=0).astype(np.uint8)
    return (all_true, all_true != 0)


def s3_get(bucket: str, key: str):
    """Get AWS S3 Object."""
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def _rasterize_geom(geom, shape, affinetrans, all_touched):
    indata = [(geom, 1)]
    rv_array = features.rasterize(
        indata, out_shape=shape, transform=affinetrans, fill=0, all_touched=all_touched
    )
    return rv_array
