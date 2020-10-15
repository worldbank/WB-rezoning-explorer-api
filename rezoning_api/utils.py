"""utility functions"""
import boto3
import rasterio
from typing import Union, List
from geojson_pydantic.geometries import Polygon, MultiPolygon
from shapely.geometry import shape
from rasterio.windows import from_bounds
from rasterio.warp import transform_geom
from rasterio.crs import CRS
from rasterio import features
import numpy as np
import numpy.ma as ma
import xarray as xr

PLATE_CARREE = CRS.from_epsg(4326)

s3 = boto3.client("s3")


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


def read_dataset(
    dataset: str,
    layers: List,
    aoi: Union[Polygon, MultiPolygon],
    band=None,
    tilesize=None,
    nan=0,
):
    """read a dataset in a given area"""
    with rasterio.open(dataset) as src:
        # find the window of our aoi
        g2 = transform_geom(PLATE_CARREE, src.crs, aoi)
        bounds = shape(g2).bounds
        window = from_bounds(*bounds, transform=src.transform)

        # read overviews if specified
        out_shape = (tilesize, tilesize) if tilesize else None

        # read data
        data = np.nan_to_num(
            src.read(band, window=window, out_shape=out_shape), nan=nan
        )

        # mask with geometry
        mask = _rasterize_geom(
            g2, data.shape[1:], src.window_transform(window), all_touched=True
        )

        # return as xarray
        return xr.DataArray(
            ma.array(data, mask=np.broadcast_to(mask, data.shape)),
            dims=("layer", "x", "y"),
            coords=dict(layer=layers),
        )
