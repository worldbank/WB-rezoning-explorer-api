"""api utility functions"""

import numpy as np
from rasterio import features

from rezoning_api.core.config import BUCKET
from rezoning_api.models.zone import Weights
from rezoning_api.utils import read_dataset, min_max_scale
from rezoning_api.db.layers import get_layers
from rezoning_api.db.country import get_country_min_max
from rezoning_api.utils import (
    get_distances,
    get_layer_location,
    get_capacity_factor,
    lcoe_generation,
    lcoe_interconnection,
    lcoe_road,
)

LAYERS = get_layers()


def _rasterize_geom(geom, shape, affinetrans, all_touched):
    indata = [(geom, 1)]
    rv_array = features.rasterize(
        indata, out_shape=shape, transform=affinetrans, fill=0, all_touched=all_touched
    )
    return rv_array


def calc_score(id, aoi, lcoe, weights, filters, tilesize=None):
    """
    calculate a "zone score" from the provided LCOE, weight, and filter inputs
    the function returns a pixel array of scored values which can later be
    aggregated into zones so here we refer to the function as a "score" calculation
    """
    # spatial temporal inputs
    ds, dr, calc, mask = get_distances(aoi, filters, tilesize=tilesize)
    cf = get_capacity_factor(aoi, lcoe.capacity_factor, tilesize=tilesize)

    # lcoe component calculation
    lg = lcoe_generation(lcoe, cf)
    li = lcoe_interconnection(lcoe, cf, ds)
    lr = lcoe_road(lcoe, cf, dr)

    # get regional min/max
    cmm = get_country_min_max(id)

    # normalize weights
    scale_max = sum([wv for wn, wv in weights])
    temp_weights = weights.dict()
    for weight_name, weight_value in temp_weights.items():
        temp_weights[weight_name] = weight_value / scale_max
    weights = Weights(**temp_weights)

    # zone score
    score_array = np.zeros((tilesize, tilesize))
    for weight_name, weight_value in weights:
        layer = weight_name.replace("_", "-")
        loc, _idx = get_layer_location(layer)
        if loc and weight_value > 0:
            dataset = loc.replace(f"s3://{BUCKET}/", "").replace(".tif", "")
            data, _ = read_dataset(
                f"s3://{BUCKET}/{dataset}.tif",
                LAYERS[dataset],
                aoi,
                tilesize=tilesize,
            )

            scaled_array = min_max_scale(
                np.nan_to_num(data.sel(layer=layer).values, nan=0),
                cmm[layer]["min"],
                cmm[layer]["max"],
            )
            score_array += weight_value * scaled_array

        # non-layer zone score additions
        score_array += (
            min_max_scale(
                lg.values,
                cmm["lcoe"][lcoe.capacity_factor]["lg"]["min"],
                cmm["lcoe"][lcoe.capacity_factor]["lg"]["max"],
            )
            * weights.lcoe_gen
        )

        score_array += (
            min_max_scale(
                li.values,
                cmm["lcoe"][lcoe.capacity_factor]["li"]["min"],
                cmm["lcoe"][lcoe.capacity_factor]["li"]["max"],
            )
            * weights.lcoe_transmission
        )

        score_array += (
            min_max_scale(
                lr.values,
                cmm["lcoe"][lcoe.capacity_factor]["lr"]["min"],
                cmm["lcoe"][lcoe.capacity_factor]["lr"]["max"],
            )
            * weights.lcoe_road
        )

    print(score_array.max())

    # TODO: uncomment things, add back mask
    return score_array, mask
