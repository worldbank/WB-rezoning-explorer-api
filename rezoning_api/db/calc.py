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
from rio_tiler.utils import linear_rescale

from rezoning_api.utils import read_dataset
from rezoning_api.core.config import BUCKET, LCOE_MAX
from rezoning_api.db.country import get_country_geojson, world
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


def refresh_country_extrema(partial=False, offshore=False):
    """refresh the country minima and maxima per layer"""
    layers = get_layers()
    datasets = layers.keys()
    for feature in world["features"]:
        f_key = feature["properties"]["GID_0"]
        fname = f"temp/{f_key}.json"
        if offshore:
            fname = f"temp/{f_key}_offshore.json"
        t1 = time()
        if partial and os.path.exists(fname):
            print(f"skipping {fname} already exists")
            continue
        print(f"reading values for {feature['properties']['NAME_0']}")
        try:
            aoi = get_country_geojson(f_key, offshore=offshore).geometry.dict()
        except Exception:
            print(f"no valid geometry for {f_key}, offshore = {offshore}")
            continue

        extrema = dict()
        for dataset in datasets:
            print(f"reading {dataset}")
            try:
                ds, _ = read_dataset(
                    f"s3://{BUCKET}/{dataset}.tif",
                    layers[dataset],
                    x=None,
                    y=None,
                    z=None,
                    geometry=aoi,
                    max_size=1024,
                )
                for layer in layers[dataset]:
                    extrema[layer] = dict(
                        min=float(ds.sel(layer=layer).min()),
                        max=float(ds.sel(layer=layer).max()),
                    )
            except Exception as e:
                print(e)
                print(f"could not read {dataset}")

        with open(fname, "w") as out:
            json.dump(extrema, out)
        # except Exception:
        #     print("error, skipping")
        print(f"elapsed: {time() - t1} seconds")


def single_country_lcoe(
    dest_file: str, country_id, resource, lcoe=LCOE(), filters=Filters()
):
    """calculate lcoe for single country"""
    t1 = time()
    offshore = True if resource == "offshore" else False
    aoi = get_country_geojson(country_id, offshore=offshore).geometry.dict()

    # spatial inputs
    print("getting spatial inputs")
    ds, dr, _calc, mask = get_distances(filters, geometry=aoi)
    cf = get_capacity_factor(lcoe.capacity_factor, lcoe.tlf, lcoe.af, geometry=aoi)
    print("capacity factor shape", cf.shape)

    # lcoe component calculation
    lg = lcoe_generation(lcoe, cf)
    li = lcoe_interconnection(lcoe, cf, ds)
    lr = lcoe_road(lcoe, cf, dr)
    lcoe_total = lg + li + lr
    print(f"lcoe calculated: {float(lcoe_total.min())} - {float(lcoe_total.max())}")

    # cap lcoe components + total
    lg = np.clip(lg, None, LCOE_MAX)
    li = np.clip(li, None, LCOE_MAX)
    lr = np.clip(lr, None, LCOE_MAX)
    lcoe_total = np.clip(lcoe_total, None, LCOE_MAX)

    # match with filter for src profile
    print("begin write out process")
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
            dst.write_mask(mask.astype(np.bool))

    print(f"elapsed: {time() - t1} seconds")


def single_country_score(
    dest_file: str,
    country_id,
    resource,
    lcoe=LCOE(),
    filters=Filters(),
    weights=Weights(),
):
    # TODO: DRY
    """calculate score for single country"""
    t1 = time()
    offshore = True if resource == "offshore" else False
    aoi = get_country_geojson(country_id, offshore=offshore).geometry.dict()

    data, mask = calc_score(country_id, resource, lcoe, weights, filters, geometry=aoi)

    # normalize to 0-1
    data = linear_rescale(
        data, in_range=(data.min(), data.max()), out_range=(0, 1)
    ).astype(np.float32)

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

        # write out
        with rasterio.open(dest_file, "w", **profile) as dst:
            print(f"saving to {dest_file}")
            dst.write(data.astype(np.float32), 1)
            dst.write_mask(mask.astype(np.bool))

    print(f"elapsed: {time() - t1} seconds")
