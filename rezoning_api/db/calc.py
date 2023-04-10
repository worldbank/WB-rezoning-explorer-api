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
import pyproj
from rasterio.features import shapes
from shapely.ops import unary_union, transform
from shapely.geometry import shape, mapping

from rezoning_api.utils import read_dataset
from rezoning_api.core.config import BUCKET, LCOE_MAX, IS_LOCAL_DEV, REZONING_LOCAL_DATA_PATH
from rezoning_api.db.country import get_country_geojson, get_region_geojson, world
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

from os.path import exists

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
            if len(f_key) == 3:
                aoi = get_country_geojson(f_key, offshore=offshore).geometry.dict()
            else:
                aoi = get_region_geojson(f_key, offshore=offshore).geometry.dict()

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
    if len(country_id) == 3:
        aoi = get_country_geojson(country_id, offshore=offshore).geometry.dict()
    else:
        aoi = get_region_geojson(country_id, offshore=offshore).geometry.dict()

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
    if IS_LOCAL_DEV:
        local_match_data = match_data.replace(f"s3://{BUCKET}/", REZONING_LOCAL_DATA_PATH)
        if exists(local_match_data):
            match_data = local_match_data

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
            dst.write_mask(mask.astype(np.bool_))

    print(f"elapsed: {time() - t1} seconds")


def single_country_score(
    dest_file: str,
    country_id,
    resource,
    lcoe=LCOE(),
    filters=Filters(),
    weights=Weights()
):
    # TODO: DRY
    """calculate score for single country"""
    t1 = time()
    offshore = True if resource == "offshore" else False
    if len(country_id) == 3:
        aoi = get_country_geojson(country_id, offshore=offshore).geometry.dict()
    else:
        aoi = get_region_geojson(country_id, offshore=offshore).geometry.dict()

    data, mask = calc_score(country_id, resource, lcoe, weights, filters, geometry=aoi)

    # normalize to 0-1
    data = linear_rescale(
        data, in_range=(data.min(), data.max()), out_range=(0, 1)
    ).astype(np.float32)

    # match with filter for src profile
    match_data = f"s3://{BUCKET}/multiband/filter.tif"
    if IS_LOCAL_DEV:
        local_match_data = match_data.replace(f"s3://{BUCKET}/", REZONING_LOCAL_DATA_PATH)
        if exists(local_match_data):
            match_data = local_match_data
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
            dst.write_mask(mask.astype(np.bool_))

    print(f"elapsed: {time() - t1} seconds")

def convert_geotiff_to_geojson( lcoe_file_path: str, geojson_file_path: str ):
    "Converts a LCOE geotiff to geojson"
    with rasterio.open(lcoe_file_path) as src:
        data = src.read(1, masked=True)    
        raster_vectorized = unary_union([shape(s) for s, v in shapes(data, transform=src.transform)] )
        project = pyproj.Transformer.from_crs( pyproj.CRS(src.profile["crs"]), pyproj.CRS('epsg:4326'), always_xy=True )
        raster_vectorized = transform( project.transform, raster_vectorized )
        raster_json = dict(properties={}, geometry=mapping(raster_vectorized), type="Feature")

        print( f"saving to {geojson_file_path}" )
        json.dump( raster_json, open( geojson_file_path, "w+" ) )
