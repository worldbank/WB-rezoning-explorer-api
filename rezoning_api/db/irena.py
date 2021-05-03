""" utility functions for IRENA data """
import os
import requests

# on startup, fetch the IRENA data


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


def fetch_irena_data(resource):
    """create a lookup table for IRENA data from Airtable"""
    records = request_irena_data(resource)
    table = dict()
    for record in records:
        try:
            table[record["fields"]["ISO3"]] = record["fields"]
        except KeyError:
            pass

    return table


irena_data = dict(
    solar=fetch_irena_data("solar"),
    wind=fetch_irena_data("wind"),
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
