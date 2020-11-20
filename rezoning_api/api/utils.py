"""api utility functions"""
from typing import Union
import xml.etree.ElementTree as ET

import numpy as np
import xarray as xr
from pydantic import create_model
from rasterio import features
from geojson_pydantic.geometries import Polygon, MultiPolygon

from rezoning_api.models.zone import LCOE
from rezoning_api.core.config import BUCKET
from rezoning_api.utils import read_dataset
from rezoning_api.db.layers import get_layers
from rezoning_api.db.country import get_country_min_max

LAYERS = get_layers()

MAX_DIST = 1000000  # meters


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


def get_capacity_factor(
    aoi: Union[Polygon, MultiPolygon], turbine_type=None, tilesize=None
):
    """Calculate Capacity Factor"""
    # decide which capacity factor tif to pull from
    cf_tif_loc = "gsa"
    if turbine_type:
        cf_tif_loc = "gwa"

    cf, _ = read_dataset(
        f"s3://{BUCKET}/multiband/{cf_tif_loc}.tif",
        layers=LAYERS[cf_tif_loc],
        aoi=aoi.dict(),
        tilesize=tilesize,
    )

    return cf.sel(layer=LAYERS[cf_tif_loc][0])  # TODO: which layer to read from


def get_distances(aoi: Union[Polygon, MultiPolygon], filters, tilesize=None):
    """Get filtered masks and distance arrays"""
    # find the required datasets to open
    sent_filters = [filter_to_layer_name(k) for k, v in filters.dict().items() if v]
    # we require grid and roads for calculations
    sent_filters += ["grid", "roads"]

    datasets = [
        k for k, v in LAYERS.items() if any([layer in sent_filters for layer in v])
    ]

    arrays = []
    for dataset in datasets:
        data, _ = read_dataset(
            f"s3://{BUCKET}/multiband/{dataset}.tif",
            LAYERS[dataset],
            aoi=aoi.dict(),
            tilesize=tilesize,
        )
        arrays.append(data)

    data = xr.concat(arrays, dim="layer")

    _, filter_mask = _filter(data, filters)

    return (
        data.sel(layer="grid"),
        data.sel(layer="roads"),
        data,
        filter_mask,
        # TODO: restore data mask
        # np.logical_or(
        #     ~mask, filter_mask
        # ),  # NOTE: we flip to a "true mask" here (True is valid)
    )


def get_stat(root, attrib_key):
    """get from XML"""
    return [
        float(elem.text)
        for elem in root.iterfind(".//MDI")
        if elem.attrib.get("key") == attrib_key
    ]


def get_min_max(xml):
    """get minimum and maximum values from VRT"""
    root = ET.fromstring(xml)
    mins = get_stat(root, "STATISTICS_MINIMUM")
    maxs = get_stat(root, "STATISTICS_MAXIMUM")
    return (mins, maxs)


def _filter(array, filters):
    """
    filter xarray based on per-band ranges, supplied as path parameter
    filters look like ?f_roads=0,10000&f_grid=0,10000...
    """
    # temporary handling of incorrect nodata value
    # array[array == 65535] = MAX_DIST

    np_filters = []
    for f_layer, filt in filters.dict().items():
        if filt:
            filter_type = filters.schema()["properties"][f_layer].get("pattern")
            layer_name = filter_to_layer_name(f_layer)
            single_layer = array.sel(layer=layer_name).values.squeeze()
            if filter_type == "range_filter":
                tmp = np.logical_and(
                    single_layer >= int(filt.split(",")[0]),
                    single_layer <= int(filt.split(",")[1]),
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
                    tmp = single_layer > 4 & single_layer < 10
                else:
                    tmp = single_layer == int(filt)
            print(layer_name, tmp.shape, array.sel(layer=layer_name).shape)
            np_filters.append(tmp)

    all_true = np.prod(np.stack(np_filters), axis=0).astype(np.uint8)
    return (all_true, all_true != 0)


def _rasterize_geom(geom, shape, affinetrans, all_touched):
    indata = [(geom, 1)]
    rv_array = features.rasterize(
        indata, out_shape=shape, transform=affinetrans, fill=0, all_touched=all_touched
    )
    return rv_array


def min_max_scale(arr, scale_min=None, scale_max=None):
    """returns a normalized ~0.0-1.0 array from optional min/maxes"""
    if not scale_min:
        scale_min = arr.min()
    if not scale_max:
        scale_max = arr.max()

    return (arr - scale_min) / (scale_max - scale_min)


def calc_score(id, aoi, lcoe, weights, filters, tilesize=None):
    """
    calculate a "zone score" from the provided LCOE, weight, and filter inputs
    the function returns a pixel array of scored values which can later be
    aggregated into zones so here we refer to the function as a "score" calculation
    """
    # spatial temporal inputs
    # ds, dr, calc, mask = get_distances(aoi, filters, tilesize=tilesize)
    # cf = get_capacity_factor(aoi, lcoe.turbine_type, tilesize=tilesize)

    # lcoe component calculation
    # lg = lcoe_generation(lcoe, cf)
    # li = lcoe_interconnection(lcoe, cf, ds)
    # lr = lcoe_road(lcoe, cf, dr)

    # get regional min/max
    cmm = get_country_min_max(id)

    # zone score
    score_array = np.zeros((tilesize, tilesize))
    for dataset, layers in LAYERS.items():
        data, _ = read_dataset(
            f"s3://{BUCKET}/multiband/{dataset}.tif",
            layers,
            aoi.dict(),
            tilesize=tilesize,
        )
        for layer in layers:
            ll = layer.replace("-", "_")
            try:
                if weights.dict()[ll] > 0:
                    scaled_array = min_max_scale(
                        data.sel(layer=layer).values,
                        cmm[layer]["min"],
                        cmm[layer]["max"],
                    )
                    score_array += weights.dict()[ll] * scaled_array
            except KeyError as e:
                print(e)
                print("Drew: add this key to the weights model")

    # non-layer zone score additions
    # TODO: need scaling
    # score_array += weights.lcoe_gen * lg
    # score_array += weights.lcoe_transmission * li
    # score_array += weights.lcoe_road * lr

    # TODO: uncomment things, add bask mask
    # return (min_max_scale(score_array), mask)
    return min_max_scale(score_array)


def flat_layers():
    """flatten layer list"""
    return [flat for layer in LAYERS.values() for flat in layer]


def get_layer_location(id):
    """get layer location and dataset index"""
    loc = [(k, int(v.index(id))) for k, v in LAYERS.items() if id in v]
    if loc:
        return (f"s3://{BUCKET}/multiband/{loc[0][0]}.tif", loc[0][1])
    else:
        return (None, None)


LayerNames = create_model("LayerNames", **dict(zip(flat_layers(), flat_layers())))
