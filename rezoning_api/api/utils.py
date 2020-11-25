"""api utility functions"""
import xml.etree.ElementTree as ET

import numpy as np
from pydantic import create_model
from rasterio import features

from rezoning_api.core.config import BUCKET
from rezoning_api.utils import read_dataset
from rezoning_api.db.layers import get_layers
from rezoning_api.db.country import get_country_min_max

LAYERS = get_layers()


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
            f"s3://{BUCKET}/{dataset}.tif",
            layers,
            aoi,
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
        return (f"s3://{BUCKET}/{loc[0][0]}.tif", loc[0][1])
    else:
        return (None, None)


LayerNames = create_model("LayerNames", **dict(zip(flat_layers(), flat_layers())))
