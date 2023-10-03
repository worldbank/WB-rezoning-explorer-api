"""Filter endpoints."""
import json
import math
from rezoning_api.utils import read_dataset
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from rio_tiler.io import COGReader
from rio_tiler.utils import render
import numpy as np
import xarray as xr
from typing import Optional, Any

from rezoning_api.core.config import BUCKET
from rezoning_api.models.tiles import TileResponse
from rezoning_api.models.zone import Filters, RangeFilter
from rezoning_api.utils import _filter, LAYERS, filter_to_layer_name, get_layer_location, get_min_max
from rezoning_api.db.country import get_country_min_max, get_region_min_max, s3_get, get_country_geojson, get_region_geojson

router = APIRouter()


def nan_to_none(obj):
    if isinstance(obj, dict):
        return {k: nan_to_none(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [nan_to_none(v) for v in obj]
    elif isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        pass

    def encode(self, obj):
        obj = nan_to_none(obj)
        return super().encode(obj)

    def iterencode(self, obj, *args, **kwargs):
        obj = nan_to_none(obj)
        return super().iterencode(obj, *args, **kwargs)


class CustomJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=True,
            indent=None,
            separators=(",", ":"),
            cls=CustomJSONEncoder,
        ).encode("utf-8")


@router.get(
    "/filter/{z}/{x}/{y}.png",
    responses={
        200: dict(description="return a filtered tile given certain parameters")
    },
    response_class=TileResponse,
    name="filter",
)
@router.get(
    "/filter/{country_id}/{z}/{x}/{y}.png",
    responses={
        200: dict(
            description="return a filtered tile given certain parameters and country code"
        )
    },
    response_class=TileResponse,
    name="filter_country",
)
def filter(
    z: int,
    x: int,
    y: int,
    color: str,
    country_id: Optional[str] = None,
    filters: Filters = Depends(),
    offshore: bool = False,
):
    """Return filtered tile."""
    # find the required datasets to open
    sent_filters = [
        filter_to_layer_name(k) for k, v in filters.dict().items() if v is not None
    ]
    datasets = [
        k for k, v in LAYERS.items() if any([layer in sent_filters for layer in v])
    ]

    # potentially mask by country
    geometry = None
    if country_id:
        # TODO: early return for tiles outside country bounds
        if len(country_id) == 3:
            feat = get_country_geojson(country_id, offshore)
            geometry = feat.geometry.dict()
        else:
            feat = get_region_geojson(country_id, offshore)
            geometry = feat.geometry.dict()

    arrays = []
    for dataset in datasets:
        data, mask = read_dataset(
            f"s3://{BUCKET}/{dataset}.tif",
            LAYERS[dataset],
            x=x,
            y=y,
            z=z,
            geometry=geometry,
        )
        arrays.append(data)
    if arrays:
        arr = xr.concat(arrays, dim="layer")
        tile, new_mask = _filter(arr, filters)
    else:
        # if we didn't have anything to read, read gebco so we can mask
        # TODO: improve this
        data, mask = read_dataset(
            f"s3://{BUCKET}/raster/gebco/gebco_combined.tif",
            ["gebco"],
            x=x,
            y=y,
            z=z,
            geometry=geometry,
        )
        arrays.append(data)
        arr = xr.concat(arrays, dim="layer")
        filters.f_gebco = RangeFilter("0,10000000")
        tile, new_mask = _filter(arr, filters)

    # mask everything offshore with gebco
    if offshore:
        gloc, gidx = get_layer_location("gebco")
        with COGReader(gloc) as cog:
            gdata, _gmask = cog.tile(x, y, z, tilesize=256, indexes=[gidx + 1])
        mask = mask * (gdata <= 0).squeeze()

    # color like 45,39,88,178 (RGBA)
    color_list = list(map(lambda x: int(x), color.split(",")))
    color_tile = np.stack(
        [
            tile * color_list[0],
            tile * color_list[1],
            tile * color_list[2],
            (mask.squeeze() * new_mask * color_list[3]).astype(np.uint8),  # type: ignore
        ]
    )

    content = render(color_tile)
    return TileResponse(content=content)


@router.get("/filter/{country_id}/{resource}/layers")
def get_country_layers(country_id: str, resource: str):
    """Return min/max for country layers"""
    if len(country_id) == 3:
        minmax = get_country_min_max(country_id, resource)
    else:
        minmax = get_region_min_max(country_id, resource)
    # keys = list(minmax.keys())
    # [minmax.pop(key) for key in keys if key.startswith(("gwa", "gsa"))]
    return CustomJSONResponse(content=minmax)


@router.get("/filter/schema", name="filter_schema")
def get_filter_schema():
    """Return filter schema"""
    schema = Filters.schema()["properties"]
    for key in schema.keys():
        schema[key]["layer"] = filter_to_layer_name(key)
    return schema
