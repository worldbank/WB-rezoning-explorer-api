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


def read_dataset(
    dataset: str,
    layers: List,
    aoi: Union[Polygon, MultiPolygon],
    tilesize=None,
    nan=0,
):
    """read a dataset in a given area"""
    with rasterio.open(dataset) as src:
        # find the window of our aoi
        g2 = transform_geom(PLATE_CARREE, src.crs, aoi)
        bounds = shape(g2).bounds
        window = from_bounds(*bounds, transform=src.transform)

        # be careful with the window
        window = window.round_shape().round_offsets()

        # read overviews if specified
        out_shape = (tilesize, tilesize) if tilesize else None

        # read data
        data = src.read(window=window, out_shape=out_shape, masked=True)

        # for non-tiles, mask with geometry
        mask = data.mask
        if not out_shape:
            mask = np.logical_or(
                features.geometry_mask(
                    [g2],
                    out_shape=data.shape[1:],
                    transform=src.window_transform(window),
                    all_touched=True,
                ),
                mask,
            )

        # return as xarray + mask
        return (
            xr.DataArray(
                ma.array(
                    data.data,
                    mask=np.broadcast_to(mask, data.shape),
                    fill_value=data.fill_value,
                ),
                dims=("layer", "x", "y"),
                coords=dict(layer=layers),
            ),
            mask,
        )
