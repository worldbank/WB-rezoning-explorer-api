"""Filter endpoints."""
from rezoning_api.db.country import get_country_geojson, get_country_min_max
from fastapi import APIRouter
from rio_tiler.io import COGReader
from rio_tiler.utils import render, linear_rescale, create_cutline
from rio_tiler.colormap import cmap
import numpy as np

from rezoning_api.models.tiles import TileResponse
from rezoning_api.models.zone import Filters
from rezoning_api.utils import (
    get_layer_location,
    flat_layers,
    get_min_max,
    s3_get,
    filter_to_layer_name,
)
from rezoning_api.core.config import BUCKET
from rezoning_api.db.cf import get_capacity_factor_options

router = APIRouter()


@router.get(
    "/layers/{id}/{z}/{x}/{y}.png",
    responses={200: dict(description="return a tile for a given layer")},
    response_class=TileResponse,
    name="layers",
)
@router.get(
    "/layers/{country_id}/{id}/{z}/{x}/{y}.png",
    responses={
        200: dict(description="return a tile for a given layer, filtered by country")
    },
    response_class=TileResponse,
    name="layers",
)
def layers(
    id: str,
    z: int,
    x: int,
    y: int,
    colormap: str,
    country_id: str = None,
    offshore: bool = False,
):
    """Return a tile from a layer."""
    loc, idx = get_layer_location(id)
    key = loc.replace(f"s3://{BUCKET}/", "").replace("tif", "vrt")

    with COGReader(loc) as cog:
        vrt_options = None
        if country_id:
            aoi = get_country_geojson(country_id, offshore)
            cutline = create_cutline(cog.dataset, aoi.dict(), geometry_crs="epsg:4326")
            vrt_options = {"cutline": cutline}

        data, mask = cog.tile(
            x, y, z, tilesize=256, indexes=[idx + 1], vrt_options=vrt_options
        )

    try:
        if country_id:
            minmax = get_country_min_max(country_id)
            layer_min = minmax[id]["min"]
            layer_max = minmax[id]["max"]
        else:
            layer_min_arr, layer_max_arr = get_min_max(s3_get(BUCKET, key))
            layer_min = layer_min_arr[idx]
            layer_max = layer_max_arr[idx]
    except Exception:
        layer_min = data.min()
        layer_max = data.max()

    if id != "land-cover":
        data = linear_rescale(
            data, in_range=(layer_min, layer_max), out_range=(0, 255)
        ).astype(np.uint8)
        colormap_dict = cmap.get(colormap)
    else:
        data = data.astype(np.uint8)
        colormap_dict = {
            0: [0, 0, 0, 255],
            10: [255, 255, 100, 255],
            20: [170, 240, 240, 255],
            30: [220, 240, 100, 255],
            40: [200, 200, 100, 255],
            50: [0, 100, 0, 255],
            60: [0, 160, 0, 255],
            70: [0, 60, 0, 255],
            80: [40, 80, 0, 255],
            90: [120, 130, 0, 255],
            100: [140, 160, 0, 255],
            110: [190, 150, 0, 255],
            120: [150, 100, 0, 255],
            130: [255, 180, 50, 255],
            140: [255, 220, 210, 255],
            150: [255, 235, 175, 255],
            160: [0, 120, 90, 255],
            170: [0, 150, 120, 255],
            180: [0, 220, 130, 255],
            190: [195, 20, 0, 255],
            200: [255, 245, 215, 255],
            210: [0, 70, 200, 255],
            220: [255, 255, 255, 255],
        }

    content = render(data, mask, colormap=colormap_dict)
    return TileResponse(content=content)


@router.get("/layers/", name="layer_list")
def get_layers():
    """Return layers list"""
    layers = {layer: {} for layer in flat_layers()}

    # for later matching
    cfo = get_capacity_factor_options()
    cfo_flat = cfo["solar"] + cfo["wind"] + cfo["offshore"]

    for lkey, layer in layers.items():
        # add descriptions, categories, and titles from matching titles
        matching_filters = [
            filter
            for key, filter in Filters.schema()["properties"].items()
            if filter_to_layer_name(key) == lkey
        ]
        if matching_filters:
            mf = matching_filters[0]
            layer["description"] = mf.get("description", None)
            layer["category"] = mf.get("category", None)
            layer["title"] = mf.get("title", None)
        elif lkey in cfo_flat:
            cf_params = lkey.split("-")
            if len(cf_params) == 2:
                title = f"IEC Class {'I' * int(cf_params[1][3])}"
            else:
                main = f"{' '.join([s.capitalize() if len(s) > 4 else s.upper() for s in cf_params[1:-1]])}"
                height = cf_params[-1]
                title = f"{main} @ {height}m"
                title = title.replace("Mode0", "Mode 0")
            layer["description"] = f"Capacity Factor derived from {title} input"
            layer["category"] = "capacity-factor"
            layer["title"] = title
        elif lkey.startswith("gwa"):
            _, kind, height = lkey.split("-")
            layer["description"] = None
            layer["category"] = "additional-wind"
            layer["title"] = f"Mean Wind {kind.capitalize()} @ {height}m "
        elif lkey == "gsa-gti":
            layer["description"] = None
            layer["category"] = "additional-solar"
            layer["title"] = "Global Titled Irradiation"
        elif lkey == "gsa-ghi":
            layer["description"] = None
            layer["category"] = "additional-solar"
            layer["title"] = "Global Horizontal Irradiation"
        elif lkey == "gsa-temp":
            layer["description"] = None
            layer["category"] = "additional-solar"
            layer["title"] = "Air Temperature"
        else:
            layer["description"] = None
            layer["category"] = "additional"
            layer["title"] = lkey

    # add some non-raster layers
    layers["grid"]["tiles"] = [
        "http://107.22.154.146/services/grid/tiles/{z}/{x}/{y}.pbf"
    ]

    layers["anchorages"]["tiles"] = [
        "http://107.22.154.146/services/anchorages/tiles/{z}/{x}/{y}.pbf"
    ]

    layers["airports"]["tiles"] = [
        "http://107.22.154.146/services/airports/tiles/{z}/{x}/{y}.pbf"
    ]

    layers["ports"]["tiles"] = [
        "http://107.22.154.146/services/ports/tiles/{z}/{x}/{y}.pbf"
    ]

    layers["roads"]["tiles"] = [
        "http://107.22.154.146/services/roads/tiles/{z}/{x}/{y}.pbf"
    ]

    # for now, remove excess manually
    layers.pop("wwf-glw-1", None)
    layers.pop("wwf-glw-2", None)
    layers.pop("jrc-gsw", None)

    return layers
