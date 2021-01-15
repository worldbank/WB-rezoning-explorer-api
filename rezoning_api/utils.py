"""utility functions"""
import xml.etree.ElementTree as ET
import boto3
import rasterio
import hashlib
import json
from typing import Union, List, Optional, Any
from geojson_pydantic.geometries import Polygon, MultiPolygon
from shapely.geometry import shape
from rasterio.windows import from_bounds
from rasterio.warp import transform_geom
from rasterio.crs import CRS
from rasterio import features
from rasterio import Affine as A
import numpy as np
import numpy.ma as ma
import xarray as xr
from pydantic import create_model


from rezoning_api.core.config import BUCKET
from rezoning_api.models.zone import LCOE
from rezoning_api.db.layers import get_layers

LAYERS = get_layers()
PLATE_CARREE = CRS.from_epsg(4326)
MAX_DIST = 1000000  # meters

s3 = boto3.client("s3")


def s3_get(bucket: str, key: str, full_response=False):
    """Get AWS S3 Object."""
    response = s3.get_object(Bucket=bucket, Key=key)
    if full_response:
        return response
    return response["Body"].read()


def s3_head(bucket: str, key: str):
    """Head request on S3 Object."""
    return s3.head_object(Bucket=bucket, Key=key)


def read_dataset(
    dataset: str,
    layers: List,
    aoi: Union[Polygon, MultiPolygon],
    tilesize=None,
    nan=0,
    extra_mask_geometry: Optional[Union[Polygon, MultiPolygon]] = None,
):
    """read a dataset in a given area"""
    with rasterio.open(dataset) as src:
        # find the window of our aoi
        g2 = transform_geom(PLATE_CARREE, src.crs, aoi)
        bounds = shape(g2).bounds
        window = from_bounds(*bounds, transform=src.transform)

        # be careful with the window
        window = window.round_shape().round_offsets()

        # read overviews if specified
        out_shape = (tilesize, tilesize) if tilesize else None

        # read data
        data = src.read(window=window, out_shape=out_shape, masked=True)

        # for non-tiles, mask with geometry
        mask = data.mask
        if not out_shape or extra_mask_geometry:
            transform = src.window_transform(window)
            if extra_mask_geometry:
                g2 = transform_geom(PLATE_CARREE, src.crs, extra_mask_geometry)
                transform = transform * A.scale(
                    window.width / tilesize, window.height / tilesize
                )
            mask = np.logical_or(
                features.geometry_mask(
                    [g2],
                    out_shape=data.shape[1:],
                    transform=transform,
                    all_touched=True,
                ),
                mask,
            )

        # reduce mask to a single dimension
        mask = np.prod(mask, axis=0) > 0

        # return as xarray + mask
        return (
            xr.DataArray(
                ma.array(
                    data.data,
                    mask=np.broadcast_to(mask, data.shape),
                    fill_value=data.fill_value,
                ),
                dims=("layer", "x", "y"),
                coords=dict(layer=layers),
            ),
            mask,
        )


def filter_to_layer_name(flt):
    """filter name helper"""
    return flt[2:].replace("_", "-")


def calc_crf(lr: LCOE):
    """
    Calculate Capital Recovery Factor (CRF)
    https://www.nrel.gov/analysis/tech-lcoe-documentation.html
    """
    return (lr.i * (1 + lr.i) ** lr.n) / (((1 + lr.i) ** lr.n) - 1)


def lcoe_generation(lr: LCOE, cf):
    """Calculate LCOE from Generation"""
    numerator = lr.cg * calc_crf(lr) + lr.omfg
    denominator = cf * 8760
    return (numerator / denominator) * 1000 + lr.omvg


def lcoe_interconnection(lr: LCOE, cf, ds):
    """Calculate LCOE from Interconnection"""
    numerator = ds * (lr.ct * calc_crf(lr) + lr.omft) + lr.cs * calc_crf(lr)
    denominator = cf * 8760
    return numerator / denominator


def lcoe_road(lr: LCOE, cf, dr):
    """Calculate LCOE from Roads"""
    numerator = dr * (lr.cr * calc_crf(lr) + lr.omfr)
    denominator = cf * 50 * 8760
    return numerator / denominator


def get_capacity_factor(
    aoi: Union[Polygon, MultiPolygon], capacity_factor: str, tilesize=None
):
    """Calculate Capacity Factor"""
    # decide which capacity factor tif to pull from
    cf_tif_loc, cf_idx = get_layer_location(capacity_factor)
    dataset = cf_tif_loc.replace(f"s3://{BUCKET}/", "").replace(".tif", "")

    if not cf_tif_loc:
        raise Exception("invalid capacity factor")

    cf, _ = read_dataset(
        cf_tif_loc,
        layers=LAYERS[dataset],
        aoi=aoi,
        tilesize=tilesize,
    )

    return cf.sel(layer=LAYERS[dataset][cf_idx])


def get_distances(aoi: Union[Polygon, MultiPolygon], filters, tilesize=None):
    """Get filtered masks and distance arrays"""
    # find the required datasets to open
    sent_filters = [
        filter_to_layer_name(k) for k, v in filters.dict().items() if v is not None
    ]
    # we require grid and roads for calculations
    sent_filters += ["grid", "roads"]

    datasets = [
        k for k, v in LAYERS.items() if any([layer in sent_filters for layer in v])
    ]

    arrays = []
    for dataset in datasets:
        data, _ = read_dataset(
            f"s3://{BUCKET}/{dataset}.tif",
            LAYERS[dataset],
            aoi=aoi,
            tilesize=tilesize,
        )
        arrays.append(data)

    data = xr.concat(arrays, dim="layer")

    _, filter_mask = _filter(data, filters)

    return (
        data.sel(layer="grid"),
        data.sel(layer="roads"),
        data,
        filter_mask,
        # TODO: restore data mask
        # np.logical_or(
        #     ~mask, filter_mask
        # ),  # NOTE: we flip to a "true mask" here (True is valid)
    )


def _filter(array, filters):
    """
    filter xarray based on per-band ranges, supplied as path parameter
    filters look like ?f_roads=0,10000&f_grid=0,10000...
    """
    # TODO: make this more readable
    # the condition is "no filter has a value which isn't none"
    if not any([True for filter in filters.dict().values() if filter is not None]):
        trues = np.prod(array, axis=0) > 0
        return (trues.astype(np.uint8), trues.astype(np.bool))

    np_filters = []
    for f_layer, filt in filters.dict().items():
        if filt is not None:
            filter_type = filters.schema()["properties"][f_layer].get("pattern")
            layer_name = filter_to_layer_name(f_layer)
            single_layer = array.sel(layer=layer_name).values.squeeze()
            if filter_type == "range_filter":
                tmp = np.logical_and(
                    single_layer >= float(filt.split(",")[0]),
                    single_layer <= float(filt.split(",")[1]),
                )
            elif filter_type == "categorical_filter":
                # multiply by ten to get land cover class
                indices = [10 * int(option) for option in filt.split(",")]
                tmp = np.isin(single_layer, indices)
            else:
                # filter types without a pattern are boolean
                # rasters are stored as binary so we convert input to integers
                # for wwf-glw-3 (wetlands), we have special handling
                # https://www.worldwildlife.org/publications/global-lakes-and-wetlands-database-lakes-and-wetlands-grid-level-3
                if layer_name == "wwf-glw-3":
                    tmp = ~np.logical_and(single_layer > 4, single_layer < 10)
                elif layer_name == "waterbodies":
                    # booleans are only sent when false, match non values
                    tmp = single_layer != 2
                else:
                    # booleans are only sent when false, match non values
                    tmp = single_layer > 0
            np_filters.append(tmp)

    all_true = np.prod(np.stack(np_filters), axis=0).astype(np.uint8)
    return (all_true, all_true != 0)


def flat_layers():
    """flatten layer list"""
    return [flat for layer in LAYERS.values() for flat in layer]


def get_layer_location(id):
    """get layer location and dataset index"""
    loc = [(k, int(v.index(id))) for k, v in LAYERS.items() if id in v]
    if loc:
        return (f"s3://{BUCKET}/{loc[0][0]}.tif", loc[0][1])
    else:
        return (None, None)


LayerNames = create_model("LayerNames", **dict(zip(flat_layers(), flat_layers())))


def min_max_scale(arr, scale_min=None, scale_max=None, flip=False):
    """returns a normalized ~0.0-1.0 array from optional min/maxes"""
    if not scale_min:
        scale_min = arr.min()
    if not scale_max:
        scale_max = arr.max()

    # flip min/max if requested
    if flip:
        temp = scale_max
        scale_max = scale_min
        scale_min = temp

    # to prevent divide by zero errors
    scale_max = max(scale_max, 1e5)

    return (arr - scale_min) / (scale_max - scale_min)


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


def get_hash(**kwargs: Any) -> str:
    """Create hash from kwargs."""
    return hashlib.sha224(json.dumps(kwargs, sort_keys=True).encode()).hexdigest()
