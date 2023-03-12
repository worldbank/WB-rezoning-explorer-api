"""Filter endpoints."""
from rezoning_api.db.country import get_country_geojson, get_country_min_max, get_region_geojson
from fastapi import APIRouter, Depends
from typing import Optional

from rio_tiler.io import COGReader
from rio_tiler.utils import render, linear_rescale, create_cutline
from rio_tiler.colormap import cmap
import numpy as np
import xarray as xr

from os.path import exists

from rezoning_api.models.tiles import TileResponse
from rezoning_api.models.zone import Filters, RangeFilter
from rezoning_api.utils import (
    get_layer_location,
    flat_layers,
    get_min_max,
    s3_get,
    filter_to_layer_name,
    _filter,
    LAYERS,
    read_dataset,
)
from rezoning_api.core.config import BUCKET, IS_LOCAL_DEV, REZONING_LOCAL_DATA_PATH
from rezoning_api.db.cf import get_capacity_factor_options
from rezoning_api.db.country import get_country_min_max, s3_get, get_country_geojson, get_region_geojson, match_gsa_dailies

router = APIRouter()

TILE_URL = "https://reztileserver.com/services/{layer}/tiles/{{z}}/{{x}}/{{y}}.pbf"

# TODO: refactor creating the filter mask (share same code between filter and layers endpoints)
def getFilterMask( 
    z: int,
    x: int,
    y: int,
    layer_id: Optional[str] = None,
    country_id: Optional[str] = None,
    filters: Filters = Depends(),
    offshore: bool = False,
 ):
    """Return filtered tile."""
    # find the required datasets to open
    print( [filter_to_layer_name(k) for k, v in filters.dict().items() if v is not None] )
    sent_filters = [
        filter_to_layer_name(k) for k, v in filters.dict().items() if v is not None and filter_to_layer_name(k) == layer_id
    ]
    datasets = [
        k for k, v in LAYERS.items() if any([layer in sent_filters for layer in v])
    ]
    datasets_2 = [
        v for k, v in LAYERS.items() if any([layer in sent_filters for layer in v])
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
    return mask.squeeze() * new_mask

@router.get(  # noqa: C901
    "/layers/{id}/{z}/{x}/{y}.png",
    responses={200: dict(description="return a tile for a given layer")},
    response_class=TileResponse,
    name="layers",
)
@router.get(
    "/layers/{country_id}/{resource}/{id}/{z}/{x}/{y}.png",
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
    country_id: str,
    colormap: str,
    filters: Filters = Depends(),
    resource: str = None,
    offshore: bool = False,
):
    """Return a tile from a layer."""
    loc, idx = get_layer_location(id)
    key = loc.replace(f"s3://{BUCKET}/", "").replace("tif", "vrt")

    if IS_LOCAL_DEV:
        local_loc = loc.replace(f"s3://{BUCKET}/", REZONING_LOCAL_DATA_PATH)
        if exists(local_loc):
            loc = local_loc
        else:
            print( "File", local_loc, "doesn't exist" )

    with COGReader(loc) as cog:
        vrt_options = None
        if country_id:
            if len(country_id) == 3:
                aoi = get_country_geojson(country_id, offshore)
            else:
                aoi = get_region_geojson(country_id, offshore)
            cutline = create_cutline(cog.dataset, aoi.dict(), geometry_crs="epsg:4326")
            vrt_options = {"cutline": cutline}

        data, mask = cog.tile(
            x, y, z, tilesize=256, indexes=[idx + 1], vrt_options=vrt_options
        )

    # mask everything offshore with gebco
    if offshore:
        gloc, gidx = get_layer_location("gebco")
        with COGReader(gloc) as cog:
            gdata, _gmask = cog.tile(x, y, z, tilesize=256, indexes=[gidx + 1])
        mask = mask * (gdata <= 0).squeeze()

    is_country = country_id and len( country_id ) == 3
    try:
        if is_country:
            minmax = get_country_min_max(country_id, resource)
            layer_min = minmax[id]["min"]
            layer_max = minmax[id]["max"]
        else:
            layer_min_arr, layer_max_arr = get_min_max(s3_get(BUCKET, key))
            layer_min = layer_min_arr[idx]
            layer_max = layer_max_arr[idx]
    except Exception:
        layer_min = data.min()
        layer_max = data.max()

    if not is_country and id == "worldpop":
        layer_max = 1000

    if not is_country and "gwa-speed" in id:
        layer_max /= 3

    if not is_country and "gwa-power" in id:
        layer_max /= 100

    if id == "gebco":
        # no bathymetry on land: https://github.com/developmentseed/rezoning-api/issues/103
        mask[data.squeeze() > 0] = 0

    if id in ["pp-whs", "unep-coral", "unesco-ramsar"]:
        # convert these distance layers to boolean for display
        data = np.where(data <= 1000, 1, 0)
        layer_min, layer_max = (0, 1)

    if id == "wwf-glw-3":
        # wetlands layer converted to boolean
        # https://www.worldwildlife.org/publications/global-lakes-and-wetlands-database-lakes-and-wetlands-grid-level-3
        data = np.where(np.logical_and(data >= 4, data <= 10), 1, 0)
        layer_min, layer_max = (0, 1)

    if match_gsa_dailies(id):
        # annualize gsa layers to match min/max
        if country_id:
            data *= 365

    # Mask data that is out of [layer_min, layer_max] range
    mask = mask * (data >= layer_min).squeeze()
    mask = mask * (data <= layer_max).squeeze()

    if filters:
        filter_mask = getFilterMask(z, x, y, id, country_id, filters, offshore)
        mask = mask * filter_mask

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
    cfo_ids = [cf["id"] for cf in cfo_flat]

    for lkey, layer in layers.items():
        # everything starts as a raster
        layer["type"] = "raster"
        # add descriptions, categories, and titles from matching titles
        matching_filters = [
            filter
            for key, filter in Filters.schema()["properties"].items()
            if filter_to_layer_name(key) == lkey
        ]
        if matching_filters:
            mf = matching_filters[0]
            layer["description"] = mf.get("secondary_description", None)
            layer["category"] = mf.get("secondary_category", None)
            layer["title"] = mf.get("title", None)
            layer["energy_type"] = mf.get("energy_type", None)
            layer["units"] = mf.get("units", None)
            layer["source_url"] = mf.get("source_url", None)
        elif lkey in cfo_ids:
            # remove excess capacity factor layers
            layers[lkey] = {}
        elif lkey.startswith("gwa"):
            _, kind, height = lkey.split("-")
            layer["description"] = None
            layer["category"] = "additional-wind"
            layer["title"] = f"Mean Wind {kind.capitalize()} @ {height}m "
            layer["energy_type"] = ["offshore", "wind"]
            layer["units"] = "m/s" if kind == "speed" else "W/m²"
        elif lkey == "gsa-gti":
            layer["description"] = None
            layer["category"] = "additional-solar"
            layer["title"] = "Global Tilted Irradiation"
            layer["energy_type"] = ["solar"]
            layer["units"] = "kWh/m²"
        elif lkey == "gsa-ghi":
            layer["description"] = None
            layer["category"] = "additional-solar"
            layer["title"] = "Global Horizontal Irradiation"
            layer["energy_type"] = ["solar"]
            layer["units"] = "kWh/m²"
        elif lkey == "gsa-temp":
            layer["description"] = None
            layer["category"] = "additional-solar"
            layer["title"] = "Air Temperature"
            layer["energy_type"] = ["solar"]
            layer["units"] = "°C"
        elif lkey == "air-density":
            layer[
                "description"
            ] = "The density of air, or atmospheric density, is the mass per unit volume of Earth's atmosphere."
            layer["category"] = "additional-wind"
            layer["title"] = "Air Density"
            layer["energy_type"] = ["offshore", "wind"]
            layer["units"] = "kg/m³"
        else:
            layer["description"] = None
            layer["category"] = "additional"
            layer["title"] = lkey
        # rename vector layers
        if lkey in ["grid", "anchorages", "airports", "ports", "roads"]:
            layer["title"] = layer["title"].replace(" (Distance to)", "")
            layer["description"] = f"Location of {lkey.lower()}"

    # add some non-raster layers
    layers["grid"]["tiles"] = TILE_URL.format(layer="grid")
    layers["grid"]["type"] = "line"
    layers["grid"]["color"] = "#FABE21"

    layers["anchorages"]["tiles"] = TILE_URL.format(layer="anchorages")
    layers["anchorages"]["type"] = "symbol"
    layers["anchorages"]["symbol"] = "harbor-15"
    layers["anchorages"]["color"] = "#02577F"

    layers["airports"]["tiles"] = TILE_URL.format(layer="airports")
    layers["airports"]["type"] = "symbol"
    layers["airports"]["symbol"] = "airport-15"
    layers["airports"]["color"] = "#E47B2F"

    layers["ports"]["tiles"] = TILE_URL.format(layer="ports")
    layers["ports"]["type"] = "symbol"
    layers["ports"]["symbol"] = "ferry-15"
    layers["ports"]["color"] = "#538CF1"

    layers["roads"]["tiles"] = TILE_URL.format(layer="roads")
    layers["roads"]["type"] = "line"
    layers["roads"]["color"] = "#434343"

    # for now, remove excess manually
    layers.pop("wwf-glw-1", None)
    layers.pop("wwf-glw-2", None)
    layers.pop("jrc-gsw", None)

    # remove layers "marked for deletion"
    for key in list(layers.keys()):
        if not layers[key]:
            del layers[key]

    return layers
