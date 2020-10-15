"""layer functions"""
import json
from time import time

from rezoning_api.utils import s3_get, read_dataset
from rezoning_api.core.config import BUCKET
from rezoning_api.db.country import world

datasets = ["calc", "distance", "filter", "filter-byte", "gsa", "gwa"]


def refresh_layers():
    """refresh the list of dataset layers"""
    layers = dict()
    for dataset in datasets:
        layers[dataset] = json.loads(s3_get(BUCKET, f"multiband/{dataset}.json"))[
            "layers"
        ]

    return layers


def get_layers():
    """get saved layer json"""
    return json.load(open("layers.json"))
    # return json.loads(s3_get(BUCKET, 'api/layers.json'))


def refresh_country_extrema():
    """refresh the country minima and maxima per layer"""
    layers = get_layers()
    for feature in world["features"]:
        t1 = time()
        print(f"reading values for {feature['properties']['NAME_0']}")
        extrema = dict()
        for dataset in datasets:
            print(f"read {dataset}")
            ds = read_dataset(
                f"s3://{BUCKET}/multiband/{dataset}.tif",
                layers[dataset],
                feature["geometry"],
            )
            for layer in layers[dataset]:
                extrema[layer] = dict(
                    min=float(ds.sel(layer=layer).min()),
                    max=float(ds.sel(layer=layer).max()),
                )
        with open(f"temp/{feature['properties']['GID_0']}.json", "w") as out:
            json.dump(extrema, out)
        print(f"elapsed: {time() - t1} seconds")
