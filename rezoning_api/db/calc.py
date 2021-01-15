"""functions for precalculating extrema"""

import os
import json
from time import time

import numpy as np
import rasterio
from shapely.geometry import shape
from rasterio.windows import from_bounds
from rasterio.warp import transform_geom
from rasterio.crs import CRS

from rezoning_api.utils import read_dataset
from rezoning_api.core.config import BUCKET, LCOE_MAX
from rezoning_api.db.country import get_country_geojson, world
from rezoning_api.db.cf import get_capacity_factor_options
from rezoning_api.models.zone import LCOE, Filters, Weights
from rezoning_api.utils import (
    get_capacity_factor,
    get_distances,
    lcoe_generation,
    lcoe_interconnection,
    lcoe_road,
    calc_score,
)
from rezoning_api.db.layers import get_layers

PLATE_CARREE = CRS.from_epsg(4326)


def refresh_country_extrema(partial=False):
    """refresh the country minima and maxima per layer"""
    layers = get_layers()
    datasets = layers.keys()
    for feature in world["features"]:
        fname = f"temp/{feature['properties']['GID_0']}.json"
        t1 = time()
        if partial and os.path.exists(fname):
            print(f"skipping {fname} already exists")
            continue
        print(f"reading values for {feature['properties']['NAME_0']}")
        # try:
        aoi = feature["geometry"]
        extrema = dict()
        for dataset in datasets:
            print(f"reading {dataset}")
            try:
                ds, _ = read_dataset(
                    f"s3://{BUCKET}/{dataset}.tif", layers[dataset], aoi, tilesize=64
                )
                for layer in layers[dataset]:
                    extrema[layer] = dict(
                        min=float(ds.sel(layer=layer).min()),
                        max=float(ds.sel(layer=layer).max()),
                    )
            except Exception:
                print(f"could not read {dataset}")

        # calculate LCOE (from zone.py, TODO: DRY)
        # default inputs + every cf combination
        print("calc LCOE extrema")
        cfo = get_capacity_factor_options()
        options = list(set([cf for cf_list in cfo.values() for cf in cf_list]))
        extrema["lcoe"] = dict()
        for option in options:
            print(f"LCOE extrema, cf: {option}")
            # try:
            lcoe = LCOE(capacity_factor=option)
            filters = Filters()

            # spatial temporal inputs
            ds, dr, _calc, _mask = get_distances(aoi, filters, tilesize=64)
            cf = get_capacity_factor(aoi, lcoe.capacity_factor, tilesize=64)

            # lcoe component calculation
            lg = lcoe_generation(lcoe, cf)
            li = lcoe_interconnection(lcoe, cf, ds)
            lr = lcoe_road(lcoe, cf, dr)
            lcoe_total = lg + li + lr

            # cap lcoe components + total
            lg = np.clip(lg, None, LCOE_MAX)
            li = np.clip(li, None, LCOE_MAX)
            lr = np.clip(lr, None, LCOE_MAX)
            lcoe_total = np.clip(lcoe_total, None, LCOE_MAX)

            # add to extrema
            extrema["lcoe"][option] = dict(
                lg=dict(
                    min=float(lg.min()),
                    max=float(lg.max()),
                ),
                li=dict(
                    min=float(li.min()),
                    max=float(li.max()),
                ),
                lr=dict(
                    min=float(lr.min()),
                    max=float(lr.max()),
                ),
                total=dict(
                    min=float(lcoe_total.min()),
                    max=float(lcoe_total.max()),
                ),
            )
            # except Exception as e:
            #     print(e)
            #     print("lcoe error")

        with open(fname, "w") as out:
            json.dump(extrema, out)
        # except Exception:
        #     print("error, skipping")
        print(f"elapsed: {time() - t1} seconds")


def single_country_lcoe(dest_file: str, country_id, lcoe=LCOE(), filters=Filters()):
    """calculate lcoe for single country"""
    t1 = time()
    aoi = get_country_geojson(country_id).geometry.dict()

    # spatial temporal inputs
    ds, dr, _calc, _mask = get_distances(aoi, filters)
    cf = get_capacity_factor(aoi, lcoe.capacity_factor)

    # lcoe component calculation
    lg = lcoe_generation(lcoe, cf)
    li = lcoe_interconnection(lcoe, cf, ds)
    lr = lcoe_road(lcoe, cf, dr)
    lcoe_total = lg + li + lr

    # cap lcoe components + total
    lg = np.clip(lg, None, LCOE_MAX)
    li = np.clip(li, None, LCOE_MAX)
    lr = np.clip(lr, None, LCOE_MAX)
    lcoe_total = np.clip(lcoe_total, None, LCOE_MAX)

    # match with filter for src profile
    match_data = f"s3://{BUCKET}/multiband/filter.tif"
    with rasterio.open(match_data) as src:
        g2 = transform_geom(PLATE_CARREE, src.crs, aoi)
        bounds = shape(g2).bounds
        window = from_bounds(*bounds, transform=src.transform)

        profile = src.profile
        profile.update(
            dtype=rasterio.float32,
            count=1,
            compress="deflate",
            transform=src.window_transform(window),
            height=window.height,
            width=window.width,
        )

        data = lcoe_total.values.astype(np.float32)

        # write out
        with rasterio.open(dest_file, "w", **profile) as dst:
            print(f"saving to {dest_file}")
            dst.write(data, 1)

    print(f"elapsed: {time() - t1} seconds")


def single_country_score(
    dest_file: str, country_id, lcoe=LCOE(), filters=Filters(), weights=Weights()
):
    # TODO: DRY
    """calculate score for single country"""
    t1 = time()
    aoi = get_country_geojson(country_id).geometry.dict()

    data, _mask = calc_score(country_id, aoi, lcoe, weights, filters)

    # match with filter for src profile
    match_data = f"s3://{BUCKET}/multiband/filter.tif"
    with rasterio.open(match_data) as src:
        g2 = transform_geom(PLATE_CARREE, src.crs, aoi)
        bounds = shape(g2).bounds
        window = from_bounds(*bounds, transform=src.transform)
        print(window)
        profile = src.profile
        profile.update(
            dtype=rasterio.float32,
            count=1,
            compress="deflate",
            transform=src.window_transform(window),
            height=window.height,
            width=window.width,
        )

        # write out
        with rasterio.open(dest_file, "w", **profile) as dst:
            print(f"saving to {dest_file}")
            dst.write(data.astype(np.float32), 1)

    print(f"elapsed: {time() - t1} seconds")
