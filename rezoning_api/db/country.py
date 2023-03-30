"""functions for gathering data on countries"""
from os import path as op
import json
import math
from geojson_pydantic.features import Feature
import boto3
from shapely.ops import unary_union
from shapely.geometry import shape, mapping

from rezoning_api.core.config import BUCKET

with open(op.join(op.dirname(__file__), "countries.geojson"), "r") as f:
    world = json.load(f)

with open(op.join(op.dirname(__file__), "eez.geojson"), "r") as f:
    eez = json.load(f)


# duplicated to prevent circular import
# TODO: fix someday
s3 = boto3.client("s3")


def s3_get(bucket: str, key: str, full_response=False, customClient=None):
    """Get AWS S3 Object."""
    if not customClient:
        customClient = s3
    response = customClient.get_object(Bucket=bucket, Key=key)
    if full_response:
        return response
    return response["Body"].read()


def match_gsa_dailies(id):
    """returns a boolean representing whether this is a GSA daily value"""
    return "gsa" in id and id != "gsa-temp"


def get_country_geojson(id, offshore=False):
    """get geojson for a single country or eez"""
    vector_data = eez if offshore else world
    key = "ISO_TER1" if offshore else "GID_0"

    filtered = [
        feature
        for feature in vector_data["features"]
        if feature["properties"][key].lower() == id.lower()
    ]
    try:
        if offshore:
            geom = unary_union([shape(f["geometry"]) for f in filtered]).convex_hull
            feat = dict(properties={}, geometry=mapping(geom), type="Feature")
            return Feature(**feat)
        return Feature(**filtered[0])
    except Exception:
        return None

def get_region_geojson(id, offshore=False):
    """get geojson for a single region or eez"""
    source_dir = "regions_eez" if offshore else "regions"
    region_json = json.load(open(op.join(op.dirname(__file__), f"{source_dir}/{id}.geojson"), "r"))
    geom = shape( region_json["geometry"] ).convex_hull
    feat = dict(properties=region_json["properties"], geometry=mapping(geom), type="Feature")
    return Feature(**feat)


def get_country_min_max(id, resource, customClient=None):
    """get minmax for country and resource"""
    if not customClient:
        customClient = s3
    if resource == "offshore":
        # fetch another JSON (there is probably a better way to handle this)
        try:
            mm = open( f"rezoning_api/db/api/minmax/{id}_offshore.json" )
            mm_obj = json.load(mm)
        except Exception:
            try:
                mm = open( f"rezoning_api/db/api/minmax/{id}_offshore.json" )
                mm_obj = json.load(mm)
            except Exception:
                mm = open( f"rezoning_api/db/api/minmax/AFG_offshore.json" )
                mm_obj = json.load(mm)
    else:
        try:
            mm = open( f"rezoning_api/db/api/minmax/{id}.json" )
            mm_obj = json.load(mm)
        except Exception:
            mm = open( f"rezoning_api/db/api/minmax/AFG.json" )
            mm_obj = json.load(mm)

    # bathymetry data should never filter below -1000: https://github.com/developmentseed/rezoning-api/issues/91
    # don't display on land: https://github.com/developmentseed/rezoning-api/issues/103
    mm_obj["gebco"]["min"] = -1000
    mm_obj["gebco"]["max"] = 0

    # slope is converted from degrees to slope on the frontend
    mm_obj["slope"]["min"] = round(
        math.tan(mm_obj["slope"]["min"] / 180 * math.pi) * 100
    )
    mm_obj["slope"]["max"] = round(
        math.tan(mm_obj["slope"]["max"] / 180 * math.pi) * 100
    )

    # some nodata is in the population data set
    mm_obj["worldpop"]["min"] = 0

    # GSA layers converted from daily (data layer) to annual for the front end
    for key, mm in mm_obj.items():
        if match_gsa_dailies(key):
            mm["min"] = mm["min"] * 365
            mm["max"] = mm["max"] * 365

    # replace lcoe object with hardcoded minmax
    mm_obj["lcoe"] = dict(min=80, max=300)

    return mm_obj
