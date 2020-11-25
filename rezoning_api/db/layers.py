"""layer functions"""
import json


def get_layers():
    """get saved layer json"""
    with open("rezoning_api/db/layers.json") as lf:
        layers = json.load(lf)
    return layers
