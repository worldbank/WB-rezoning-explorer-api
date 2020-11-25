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
from rio_tiler.colormap import cmap
from rio_tiler.utils import linear_rescale

from rezoning_api.utils import read_dataset
from rezoning_api.core.config import BUCKET
from rezoning_api.db.country import get_country_geojson, world
from rezoning_api.models.zone import LCOE, Filters
from rezoning_api.utils import (
    get_capacity_factor,
    get_distances,
    lcoe_generation,
    lcoe_interconnection,
    lcoe_road,
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
        # default inputs
        print("calc LCOE extrema")
        try:
            lcoe = LCOE()
            filters = Filters()

            # spatial temporal inputs
            ds, dr, _calc, _mask = get_distances(aoi, filters, tilesize=64)
            cf = get_capacity_factor(aoi, lcoe.turbine_type, tilesize=64)

            # lcoe component calculation
            lg = lcoe_generation(lcoe, cf)
            li = lcoe_interconnection(lcoe, cf, ds)
            lr = lcoe_road(lcoe, cf, dr)
            lcoe_total = lg + li + lr

            # add to extrema
            extrema["lg"] = dict(
                min=float(lg.min()),
                max=float(lg.max()),
            )
            extrema["li"] = dict(
                min=float(li.min()),
                max=float(li.max()),
            )
            extrema["lr"] = dict(
                min=float(lr.min()),
                max=float(lr.max()),
            )
            extrema["lcoe_total"] = dict(
                min=float(lcoe_total.min()),
                max=float(lcoe_total.max()),
            )
        except Exception:
            print("lcoe error")

        with open(fname, "w") as out:
            json.dump(extrema, out)
        # except Exception:
        #     print("error, skipping")
        print(f"elapsed: {time() - t1} seconds")


def single_country_lcoe(id, lcoe=LCOE(), filters=Filters(), colormap="viridis"):
    """calculate lcoe for single country"""
    t1 = time()
    aoi = get_country_geojson(id).geometry.dict()

    # spatial temporal inputs
    ds, dr, _calc, _mask = get_distances(aoi, filters)
    cf = get_capacity_factor(aoi, lcoe.turbine_type)

    # lcoe component calculation
    lg = lcoe_generation(lcoe, cf)
    li = lcoe_interconnection(lcoe, cf, ds)
    lr = lcoe_road(lcoe, cf, dr)
    lcoe_total = lg + li + lr

    # match with filter for src profile
    match_data = f"s3://{BUCKET}/multiband/filter.tif"
    with rasterio.open(match_data) as src:
        g2 = transform_geom(PLATE_CARREE, src.crs, aoi)
        bounds = shape(g2).bounds
        window = from_bounds(*bounds, transform=src.transform)

        profile = src.profile
        profile.update(
            dtype=rasterio.uint8,
            count=1,
            compress="lzw",
            transform=src.window_transform(window),
            height=window.height,
            width=window.width,
        )

        data = linear_rescale(
            lcoe_total.values,
            in_range=(
                float(lcoe_total.min(skipna=True)),
                float(lcoe_total.max(skipna=True)),
            ),
            out_range=(1, 255),
        ).astype(np.uint8)

        # write out
        with rasterio.open(f"LCOE_{id}.tif", "w", **profile) as dst:
            dst.write(data, 1)
            dst.write_colormap(1, cmap.get(colormap))

    print(f"elapsed: {time() - t1} seconds")
