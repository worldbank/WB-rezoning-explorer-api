"""utility functions"""
import xml.etree.ElementTree as ET
import boto3
import math
import hashlib
import json
from typing import Union, List, Optional, Any
from geojson_pydantic.geometries import Polygon, MultiPolygon
import numpy as np
import numpy.ma as ma
import xarray as xr
from pydantic import create_model
from rio_tiler.io import COGReader
from rio_tiler.utils import create_cutline


from rezoning_api.core.config import BUCKET
from rezoning_api.models.zone import LCOE, Weights
from rezoning_api.db.layers import get_layers
from rezoning_api.db.country import get_country_min_max, match_gsa_dailies

LAYERS = get_layers()
MAX_DIST = 1000000  # meters

s3 = boto3.client("s3")


def s3_get(bucket: str, key: str, full_response=False):
    """Get AWS S3 Object."""
        response = s3.get_object(Bucket=bucket, Key=key)
    if full_response:
        return response
    return response["Body"].read()


def s3_head(bucket: str, key: str):
    """Head request on S3 Object."""
    return s3.head_object(Bucket=bucket, Key=key)


def read_dataset(
    dataset: str,
    layers: List,
    x: Optional[int] = None,
    y: Optional[int] = None,
    z: Optional[int] = None,
    geometry: Optional[Union[Polygon, MultiPolygon]] = None,
    max_size=None,
):
    """read a dataset in a given area"""
    with COGReader(dataset) as cog:
        vrt_options = None
        indexes = list(range(1, len(layers) + 1))

        # for tiles
        if x:
            if geometry:
                cutline = create_cutline(
                    cog.dataset, geometry, geometry_crs="epsg:4326"
                )
                vrt_options = {"cutline": cutline}

            data, mask = cog.tile(
                x, y, z, tilesize=256, indexes=indexes, vrt_options=vrt_options
            )
        else:
            data, mask = cog.feature(geometry, indexes=indexes, max_size=max_size)

        # return as xarray + mask
        return (
            xr.DataArray(
                ma.array(
                    data,
                    mask=np.broadcast_to(~mask, data.shape),
                ),
                dims=("layer", "x", "y"),
                coords=dict(layer=layers),
            ),
            mask / 256,
        )


def filter_to_layer_name(flt):
    """filter name helper"""
    return flt[2:].replace("_", "-")


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
    return (numerator / denominator) * 1000 + lr.omvg


def lcoe_interconnection(lr: LCOE, cf, ds):
    """Calculate LCOE from Interconnection"""
    numerator = ds / 1000 * (lr.ct * calc_crf(lr) + lr.omft) + lr.cs * calc_crf(lr)
    denominator = cf * 8760
    return numerator / denominator


def lcoe_road(lr: LCOE, cf, dr):
    """Calculate LCOE from Roads"""
    numerator = dr / 1000 * (lr.cr * calc_crf(lr) + lr.omfr)
    denominator = cf * 50 * 8760
    return numerator / denominator


def get_capacity_factor(
    capacity_factor: str,
    loss_factor: float,
    availabity_factor: float,
    x: Optional[int] = None,
    y: Optional[int] = None,
    z: Optional[int] = None,
    geometry: Union[Polygon, MultiPolygon] = None,
    max_size=None,
):
    """Calculate Capacity Factor"""
    # decide which capacity factor tif to pull from
    cf_tif_loc, cf_idx = get_layer_location(capacity_factor)
    dataset = cf_tif_loc.replace(f"s3://{BUCKET}/", "").replace(".tif", "")

    if not cf_tif_loc:
        raise Exception("invalid capacity factor")

    cf, _ = read_dataset(
        cf_tif_loc,
        layers=LAYERS[dataset],
        x=x,
        y=y,
        z=z,
        geometry=geometry,
        max_size=max_size,
    )

    # get our selected layer
    sel_cf = cf.sel(layer=LAYERS[dataset][cf_idx])

    if capacity_factor == "gsa-pvout":
        # convert daily to hourly
        sel_cf = sel_cf / 24
        # backout the technical loss factor applied
        sel_cf = sel_cf * (1 / (1 - 0.095))

    # apply loss factor and availability factor
    sel_cf = sel_cf * (1 - loss_factor) * (1 - availabity_factor)

    return sel_cf


def get_distances(
    filters,
    x: Optional[int] = None,
    y: Optional[int] = None,
    z: Optional[int] = None,
    geometry: Optional[Union[Polygon, MultiPolygon]] = None,
    max_size=None,
):
    """Get filtered masks and distance arrays"""
    # find the required datasets to open
    sent_filters = [
        filter_to_layer_name(k) for k, v in filters.dict().items() if v is not None
    ]
    # we require grid and roads for calculations
    sent_filters += ["grid", "roads"]

    datasets = [
        k for k, v in LAYERS.items() if any([layer in sent_filters for layer in v])
    ]

    arrays = []
    for dataset in datasets:
        data, mask = read_dataset(
            f"s3://{BUCKET}/{dataset}.tif",
            LAYERS[dataset],
            x=x,
            y=y,
            z=z,
            geometry=geometry,
            max_size=max_size,
        )
        arrays.append(data)

    data = xr.concat(arrays, dim="layer")

    _, filter_mask = _filter(data, filters)

    return (
        data.sel(layer="grid"),
        data.sel(layer="roads"),
        data,
        # filter_mask,
        np.logical_and(mask, filter_mask),
    )


def _filter(array, filters):
    """
    filter xarray based on per-band ranges, supplied as path parameter
    filters look like ?f_roads=0,10000&f_grid=0,10000...
    """
    # TODO: make this more readable
    # the condition is "no filter has a value which isn't none"
    if not any([True for filter in filters.dict().values() if filter is not None]):
        trues = np.prod(array.values, axis=0) > 0
        return (trues.astype(np.uint8), trues.astype(np.bool))

    np_filters = []
    for f_layer, filt in filters.dict().items():
        if filt is not None:
            filter_type = filters.schema()["properties"][f_layer].get("pattern")
            layer_name = filter_to_layer_name(f_layer)
            single_layer = array.sel(layer=layer_name).values.squeeze()
            if filter_type == "range_filter":
                lower_bound = float(filt.split(",")[0])
                upper_bound = float(filt.split(",")[1])
                if layer_name == "slope":
                    # convert slope from % values to degrees
                    lower_bound = math.atan(lower_bound / 100) * 180 / math.pi
                    upper_bound = math.atan(upper_bound / 100) * 180 / math.pi
                if match_gsa_dailies(layer_name):
                    lower_bound = lower_bound / 365
                    upper_bound = upper_bound / 365

                tmp = np.logical_and(
                    single_layer >= lower_bound,
                    single_layer <= upper_bound,
                )
            elif filter_type == "categorical_filter":
                # multiply by ten to get land cover class
                indices = [10 * int(option) for option in filt.split(",")]
                tmp = np.isin(single_layer, indices)
            else:
                # filter types without a pattern are boolean
                # rasters are stored as binary so we convert input to integers
                # for wwf-glw-3 (wetlands), we have special handling
                # https://www.worldwildlife.org/publications/global-lakes-and-wetlands-database-lakes-and-wetlands-grid-level-3
                if layer_name == "wwf-glw-3":
                    tmp = ~np.logical_and(single_layer >= 4, single_layer <= 10)
                elif layer_name == "waterbodies":
                    # booleans are only sent when false, match non values
                    # http://maps.elie.ucl.ac.be/CCI/viewer/download.php
                    # 0=ocean, 1=land, 2=inland water
                    tmp = single_layer != 2
                elif layer_name in ["pp-whs", "unep-coral", "unesco-ramsar"]:
                    # these are really distance layers that we treat as boolean
                    # This is allowing things as long as they're a meter away.
                    tmp = single_layer > 1
                else:
                    # booleans are only sent when false, match non values
                    # Protected areas are true, we want non-protected areas.
                    tmp = single_layer == 0
            np_filters.append(tmp)

    all_true = np.prod(np.stack(np_filters), axis=0).astype(np.uint8)
    return (all_true, all_true != 0)


def flat_layers():
    """flatten layer list"""
    return [flat for layer in LAYERS.values() for flat in layer]


def get_layer_location(id):
    """get layer location and dataset index"""
    loc = [(k, int(v.index(id))) for k, v in LAYERS.items() if id in v]
    if loc:
        return (f"s3://{BUCKET}/{loc[0][0]}.tif", loc[0][1])
    else:
        return (None, None)


LayerNames = create_model("LayerNames", **dict(zip(flat_layers(), flat_layers())))


def min_max_scale(arr, scale_min=None, scale_max=None, flip=False):
    """returns a normalized ~0.0-1.0 array from optional min/maxes"""
    if not scale_min:
        scale_min = arr.min()
    if not scale_max:
        scale_max = arr.max()

    # flip min/max if requested
    if flip:
        temp = scale_max
        scale_max = scale_min
        scale_min = temp

    # to prevent divide by zero errors
    scale_max = max(scale_max, 1e-5)

    return (arr - scale_min) / (scale_max - scale_min)


def get_min_max(xml):
    """get minimum and maximum values from VRT"""
    root = ET.fromstring(xml)
    mins = get_stat(root, "STATISTICS_MINIMUM")
    maxs = get_stat(root, "STATISTICS_MAXIMUM")
    return (mins, maxs)


def get_stat(root, attrib_key):
    """get from XML"""
    return [
        float(elem.text)
        for elem in root.iterfind(".//MDI")
        if elem.attrib.get("key") == attrib_key
    ]


def get_hash(**kwargs: Any) -> str:
    """Create hash from kwargs."""
    return hashlib.sha224(json.dumps(kwargs, sort_keys=True).encode()).hexdigest()


def calc_score(
    id,
    resource,
    lcoe,
    weights,
    filters,
    x: Optional[int] = None,
    y: Optional[int] = None,
    z: Optional[int] = None,
    geometry: Optional[Union[Polygon, MultiPolygon]] = None,
    max_size=None,
    ret_extras=False,
):
    """
    calculate a "zone score" from the provided LCOE, weight, and filter inputs
    the function returns a pixel array of scored values which can later be
    aggregated into zones so here we refer to the function as a "score" calculation
    """
    # spatial temporal inputs
    ds, dr, calc, mask = get_distances(filters, x=x, y=y, z=z, geometry=geometry)

    # if the entire area is filtered out, return early and fail early
    if mask.sum() == 0:
        score_array = np.zeros(mask.shape)
        cf = np.zeros(mask.shape)
        lcoe_t = np.zeros(mask.shape)
        if ret_extras:
            return score_array, mask, dict(lcoe=lcoe_t, cf=cf)
        else:
            return score_array, mask

    cf = get_capacity_factor(
        lcoe.capacity_factor, lcoe.tlf, lcoe.af, x=x, y=y, z=z, geometry=geometry
    )

    # lcoe component calculation
    lg = lcoe_generation(lcoe, cf)
    li = lcoe_interconnection(lcoe, cf, ds)
    lr = lcoe_road(lcoe, cf, dr)

    # make sure nothing is infinity
    lg = ma.masked_invalid(lg)
    li = ma.masked_invalid(li)
    lr = ma.masked_invalid(lr)

    # get regional min/max
    try:
        cmm = get_country_min_max(id, resource)
    except Exception:
        cmm = None

    # normalize weights
    scale_max = sum([wv for wn, wv in weights])
    temp_weights = weights.dict()
    for weight_name, weight_value in temp_weights.items():
        temp_weights[weight_name] = weight_value / scale_max
    weights = Weights(**temp_weights)

    # zone score
    shape = (256, 256) if x else cf.shape
    score_array = np.zeros(shape)

    weight_count = 0
    for weight_name, weight_value in weights:
        layer = weight_name.replace("_", "-")
        loc, idx = get_layer_location(layer)
        if (loc and weight_value > 0) or weight_name == "lcoe_gen":
            # valid weight
            weight_count += 1

            # flip min/max for certain weights
            flip = True
            if weight_name == "airports":
                flip = False

            # handle LCOE generation differently
            if weight_name == "lcoe_gen":
                lcoe_gen_scaled = min_max_scale(
                    lg,
                    cmm["lcoe"]["min"],
                    cmm["lcoe"]["max"],
                    flip=True,
                )
                lcoe_gen_scaled = np.clip(lcoe_gen_scaled, 0, 1)
                score_array += lcoe_gen_scaled * weights.lcoe_gen
            else:
                dataset = loc.replace(f"s3://{BUCKET}/", "").replace(".tif", "")
                data, _ = read_dataset(
                    f"s3://{BUCKET}/{dataset}.tif",
                    LAYERS[dataset],
                    x=x,
                    y=y,
                    z=z,
                    geometry=geometry,
                    max_size=max_size,
                )

                # if we don't have country min/max, use layer
                if cmm:
                    layer_min = cmm[layer]["min"]
                    layer_max = cmm[layer]["max"]
                if not cmm or layer_min == layer_max:
                    key = loc.replace(f"s3://{BUCKET}/", "").replace("tif", "vrt")
                    layer_min_arr, layer_max_arr = get_min_max(s3_get(BUCKET, key))
                    layer_min = layer_min_arr[idx]
                    layer_max = layer_max_arr[idx]

                scaled_array = min_max_scale(
                    np.nan_to_num(data.sel(layer=layer).values, nan=0),
                    layer_min,
                    layer_max,
                    flip=flip,
                )
                score_array += weight_value * scaled_array

    # final normalization
    score_array /= weight_count

    lcoe_t = lg + li + lr
    lcoe_t = ma.masked_invalid(lcoe_t)
    score_array = ma.masked_invalid(score_array)
    if ret_extras:
        return score_array, mask, dict(lcoe=lcoe_t, cf=cf)
    else:
        return score_array, mask
