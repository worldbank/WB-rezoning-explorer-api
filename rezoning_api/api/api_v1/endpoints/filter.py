"""Filter endpoints."""

from rezoning_api.utils import read_dataset
from fastapi import APIRouter, Depends
from rio_tiler.utils import render
import numpy as np
from mercantile import feature, Tile
from geojson_pydantic.geometries import Polygon
import xarray as xr

from rezoning_api.core.config import BUCKET
from rezoning_api.models.tiles import TileResponse
from rezoning_api.models.zone import Filters
from rezoning_api.api.utils import _filter, flat_layers, LAYERS, filter_to_layer_name
from rezoning_api.db.country import get_country_min_max

router = APIRouter()


@router.get(
    "/filter/{z}/{x}/{y}.png",
    responses={
        200: dict(description="return a filtered tile given certain parameters")
    },
    response_class=TileResponse,
    name="filter",
)
def filter(
    z: int,
    x: int,
    y: int,
    color: str,
    filters: Filters = Depends(),
):
    """Return filtered tile."""
    # find the required datasets to open
    sent_filters = [filter_to_layer_name(k) for k, v in filters.dict().items() if v]
    datasets = [
        k for k, v in LAYERS.items() if any([layer in sent_filters for layer in v])
    ]

    # find the tile
    aoi = Polygon(**feature(Tile(x, y, z))["geometry"]).dict()

    arrays = []
    for dataset in datasets:
        data, _ = read_dataset(
            f"s3://{BUCKET}/multiband/distance.tif",
            LAYERS[dataset],
            aoi=aoi,
            tilesize=256,
        )
        arrays.append(data)

    arr = xr.concat(arrays, dim="layers").sel(layer=sent_filters)
    # color like 45,39,88,178 (RGBA)
    color_list = list(map(lambda x: int(x), color.split(",")))

    tile, new_mask = _filter(arr, filters)
    print(tile.shape, new_mask.shape)

    color_tile = np.stack(
        [
            tile * color_list[0],
            tile * color_list[1],
            tile * color_list[2],
            (new_mask * color_list[3]).astype(np.uint8),
        ]
    )

    content = render(color_tile)
    return TileResponse(content=content)


@router.get("/filter/layers/")
def get_layers():
    """Return layers list for filters"""
    return [layer for layer in flat_layers() if not layer.startswith(("gwa", "gsa"))]


@router.get("/filter/{country_id}/layers")
def get_country_layers(country_id: str):
    """Return min/max for country layers"""
    minmax = get_country_min_max(country_id)
    keys = list(minmax.keys())
    [minmax.pop(key) for key in keys if key.startswith(("gwa", "gsa"))]
    return minmax
