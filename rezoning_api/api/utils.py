"""api utility functions"""

import numpy as np
from rasterio import features

from rezoning_api.core.config import BUCKET
from rezoning_api.utils import read_dataset, min_max_scale
from rezoning_api.db.layers import get_layers
from rezoning_api.db.country import get_country_min_max
from rezoning_api.utils import get_distances, get_layer_location

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
    # cf = get_capacity_factor(aoi, lcoe.turbine_type, tilesize=tilesize)

    # lcoe component calculation
    # lg = lcoe_generation(lcoe, cf)
    # li = lcoe_interconnection(lcoe, cf, ds)
    # lr = lcoe_road(lcoe, cf, dr)

    # get regional min/max
    cmm = get_country_min_max(id)

    # zone score
    score_array = np.zeros((tilesize, tilesize))
    for weight in weights:
        layer = weight[0].replace("_", "-")
        print(layer)
        loc, idx = get_layer_location(layer)
        if loc:
            dataset = loc.replace(f"s3://{BUCKET}/", "").replace(".tif", "")
            data, _ = read_dataset(
                f"s3://{BUCKET}/{dataset}.tif",
                LAYERS[dataset],
                aoi,
                tilesize=tilesize,
            )
            try:
                if weight[1] > 0:
                    scaled_array = min_max_scale(
                        data.sel(layer=layer).values,
                        cmm[layer]["min"],
                        cmm[layer]["max"],
                    )
                    score_array += weight[1] * scaled_array
            except KeyError as e:
                print(e)
                print("Drew: add this key to the weights model")
        else:
            print(f"handle {layer}, non dataset")

    # non-layer zone score additions
    # TODO: need scaling
    # score_array += weights.lcoe_gen * lg
    # score_array += weights.lcoe_transmission * li
    # score_array += weights.lcoe_road * lr

    # TODO: uncomment things, add back mask
    # return (min_max_scale(score_array), mask)
    return min_max_scale(score_array), mask
