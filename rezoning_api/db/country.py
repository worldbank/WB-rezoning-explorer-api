"""functions for gathering data on countries"""
from os import path as op
import json
import math
from geojson_pydantic.features import Feature
from shapely.geometry import shape, mapping, box
import boto3

from rezoning_api.core.config import BUCKET

with open(op.join(op.dirname(__file__), "countries.geojson"), "r") as f:
    world = json.load(f)

with open(op.join(op.dirname(__file__), "eez.geojson"), "r") as f:
    eez = json.load(f)


# duplicated to prevent circular import
# TODO: fix someday
s3 = boto3.client("s3")


def s3_get(bucket: str, key: str, full_response=False):
    """Get AWS S3 Object."""
    response = s3.get_object(Bucket=bucket, Key=key)
    if full_response:
        return response
    return response["Body"].read()


def match_gsa_dailies(id):
    """returns a boolean representing whether this is a GSA daily value"""
    return "gsa" in id and id != "gsa-temp"


def get_country_geojson(id, offshore=False):
    """get geojson for a single country or eez"""
    vector_data = eez if offshore else world
    key = "ISO_SOV1" if offshore else "GID_0"

    filtered = [
        feature
        for feature in vector_data["features"]
        if feature["properties"][key].lower() == id.lower()
    ]
    try:
        if offshore:
            double_filt = [
                feature
                for feature in filtered
                if feature["properties"]["ISO_TER1"]
                == feature["properties"]["ISO_SOV1"]
            ]
            geom = box(*shape(double_filt[0]["geometry"]).bounds)
            feat = dict(properties={}, geometry=mapping(geom), type="Feature")
            return Feature(**feat)
        return Feature(**filtered[0])
    except IndexError:
        return None


def get_country_min_max(id):
    """get minmax for country"""
    # TODO: calculate and use offshore minmax when requested
    try:
        minmax = s3_get(BUCKET, f"api/minmax/{id}.json")
        mm = minmax.decode("utf-8").replace("Infinity", "1000000")
        mm_obj = json.loads(mm)
    except Exception:
        mm_obj = json.loads(s3_get(BUCKET, "api/minmax/AFG.json"))

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

    return mm_obj
