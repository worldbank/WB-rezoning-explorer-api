"""capacity factor function"""
import json


def get_capacity_factor_options():
    """get all available capacity factor choices per energy type"""
    with open("rezoning_api/db/cf.json") as cf:
        capacity_factors = json.load(cf)
    return capacity_factors
