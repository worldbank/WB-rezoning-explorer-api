"""utility functions"""
import boto3

from typing import List
from geojson_pydantic import Feature

from rio_tiler.io import COGReader
from rio_tiler.utils import create_cutline
from rasterio.features import bounds as featureBounds

import numpy.ma as ma
import xarray as xr

s3 = boto3.client("s3")


def s3_get(bucket: str, key: str):
    """Get AWS S3 Object."""
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def read_dataset(
    dataset: str,
    layers: List,
    aoi: Feature,
    band=None,
    tilesize=None,
):
    """read a dataset in a given area"""
    bbox = featureBounds(aoi)
    with COGReader(dataset) as cog:
        # Create WTT Cutline
        cutline = create_cutline(cog.dataset, aoi, geometry_crs="epsg:4326")

        # Read part of the data (bbox) and use the cutline to mask the data
        data, mask = cog.part(
            bbox, vrt_options={"cutline": cutline}, width=tilesize, height=tilesize
        )

        # return as xarray
        return xr.DataArray(
            ma.array(data, mask=~mask),
            dims=("layer", "x", "y"),
            coords=dict(layer=layers),
        )
