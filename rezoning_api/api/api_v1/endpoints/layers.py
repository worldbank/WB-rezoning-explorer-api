"""Filter endpoints."""
from fastapi import APIRouter
from rio_tiler.io import COGReader
from rio_tiler.utils import render, linear_rescale
from rio_tiler.colormap import cmap
import numpy as np


from rezoning_api.models.tiles import TileResponse
from rezoning_api.api.utils import get_layer_location, flat_layers, get_min_max
from rezoning_api.utils import s3_get
from rezoning_api.core.config import BUCKET

router = APIRouter()


@router.get(
    "/layers/{id}/{z}/{x}/{y}.png",
    responses={200: dict(description="return a tile for a given layer")},
    response_class=TileResponse,
    name="layers",
)
def layers(id: str, z: int, x: int, y: int, colormap: str):
    """Return a tile from a layer."""
    loc, idx = get_layer_location(id)
    key = loc.replace(f"s3://{BUCKET}/", "").replace("tif", "vrt")
    with COGReader(loc) as cog:
        data, mask = cog.tile(x, y, z, tilesize=256, indexes=[idx + 1])

    layer_min_arr, layer_max_arr = get_min_max(s3_get(BUCKET, key))
    layer_min = layer_min_arr[idx]
    layer_max = layer_max_arr[idx]

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
    return [layer for layer in flat_layers()]
