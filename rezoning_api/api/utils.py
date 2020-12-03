"""api utility functions"""

import numpy as np
from rasterio import features

from rezoning_api.core.config import BUCKET
from rezoning_api.utils import read_dataset, min_max_scale
from rezoning_api.db.layers import get_layers
from rezoning_api.db.country import get_country_min_max

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
