""" utility functions for IRENA data """
import os
from os import path as op
import json
import requests

# on startup, load pre-fetched IRENA data
with open(op.join(op.dirname(__file__), "irena.json"), "r") as f:
    irena_data = json.load(f)


def request_irena_data(resource, records=[], offset=""):
    """helper for fetching data + pagination"""
    headers = {"Authorization": f"Bearer {os.environ['AIRTABLE_KEY']}"}
    AIRTABLE_URL = (
        f"https://api.airtable.com/v0/appU0YP4QVGcBpiLU/{resource}?offset={offset}"
    )
    r = requests.get(AIRTABLE_URL, headers=headers)
    data = r.json()

    offset = data.get("offset", None)
    if offset:
        return request_irena_data(resource, records + data["records"], offset)
    else:
        return records + data["records"]


def fetch_irena_data_table(resource):
    """create a lookup table for IRENA data from Airtable"""
    records = request_irena_data(resource)
    table = dict()
    for record in records:
        try:
            table[record["fields"]["ISO3"]] = record["fields"]
        except KeyError:
            pass

    return table


def fetch_irena_data():
    """fetch all IRENA data"""
    return dict(
        solar=fetch_irena_data_table("solar"),
        wind=fetch_irena_data_table("wind"),
    )


def get_irena_defaults(resource: str, country: str):
    """return relevant defaults for a given country and resource """
    try:
        match = irena_data[resource][country]
        return dict(
            cg=match["cg"],
            omfg=match["omfg"],
        )
    except KeyError:
        return None
