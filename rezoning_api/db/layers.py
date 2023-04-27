"""layer functions"""
import json
from os import path as op

def get_layers():
    """get saved layer json"""
    with open(op.join(op.dirname(__file__), "layers.json"), "r") as lf:
        layers = json.load(lf)
    return layers
