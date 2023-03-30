import json
import sys
import boto3
import xml.etree.ElementTree as ET

BUCKET = "gre-processed-data"

s3 = boto3.client("s3")

def s3_get(bucket: str, key: str, full_response=False, customClient=None):
    """Get AWS S3 Object."""
    if not customClient:
        customClient = s3
    response = customClient.get_object(Bucket=bucket, Key=key)
    if full_response:
        return response
    return response["Body"].read()


def get_min_max(xml):
    """get minimum and maximum values from VRT"""
    root = ET.fromstring(xml)
    mins = get_stat(root, "STATISTICS_MINIMUM")
    maxs = get_stat(root, "STATISTICS_MAXIMUM")
    return (mins, maxs)


def get_stat(root, attrib_key):
    """get from XML"""
    return [
        float(elem.text)
        for elem in root.iterfind(".//MDI")
        if elem.attrib.get("key") == attrib_key
    ]

def get_layers():
    """get saved layer json"""
    with open("./db_layers.json") as lf:
        layers = json.load(lf)
    return layers

LAYERS = get_layers()
def get_layer_location(id):
    """get layer location and dataset index"""
    loc = [(k, int(v.index(id))) for k, v in LAYERS.items() if id in v]
    if loc:
        return (f"s3://{BUCKET}/{loc[0][0]}.tif", loc[0][1])
    else:
        return (None, None)

minmax_file = open( sys.argv[-1] )

minmax_json = json.load( minmax_file )

country_code = sys.argv[-2][:3]
offshore = len( sys.argv[-2] ) > 3

print( "Parsing ", country_code, offshore )
# print( json.dumps( minmax_json, indent=1 ) )

for layer_id, minmax_dict in  minmax_json.items():
    # print( layer_id )
    if layer_id == "worldpop":
        continue

    loc, idx = get_layer_location(layer_id)
    if loc == None:
        # print( "Failed for ", layer_id )
        continue
    key = loc.replace(f"s3://{BUCKET}/", "").replace("tif", "vrt")
    # print( loc, idx, loc, key )
    try:
        layer_min_arr, layer_max_arr = get_min_max(s3_get(BUCKET, key))
    except:
        continue
    # print( layer_min_arr[idx], layer_max_arr[idx], "vs", minmax_dict["min"], minmax_dict["max"] )
    if minmax_dict["min"] < layer_min_arr[idx]:
        print( "Updating min of ", layer_id, country_code, offshore )
        minmax_json[layer_id]["min"] = layer_min_arr[idx]
    if minmax_dict["max"] > layer_max_arr[idx]:
        print( "Updating max of ", layer_id, country_code, offshore )
        minmax_json[layer_id]["max"] = layer_max_arr[idx]

minmax_file_out = open( sys.argv[-1], "w" )
json.dump( minmax_json, minmax_file_out )

    # minmax[layer_id]["min"] = max( minmax_dict["min"], layer_min_arr[idx] )
    # minmax[layer_id]["max"] = min( minmax_dict["max"], layer_max_arr[idx] )