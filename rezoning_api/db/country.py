"""functions for gathering data on countries"""
from os import path as op
import json
from geojson_pydantic.features import Feature

with open(op.join(op.dirname(__file__), "countries.geojson"), "r") as f:
    world = json.load(f)


def get_country_geojson(id):
    """get geojson for a single country"""
    filtered = [
        feature for feature in world["features"] if feature["properties"]["GID_0"] == id
    ]
    try:
        return Feature(**filtered[0])
    except IndexError:
        return None


# def get_
