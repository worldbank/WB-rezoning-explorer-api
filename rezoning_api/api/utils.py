import numpy as np
import rasterio
from rasterio.windows import from_bounds
from shapely.ops import transform 
import pyproj

from rezoning_api.models.lcoe import LCOERequest
from rezoning_api.core.config import BUCKET

def crf(l: LCOERequest):
    # https://www.nrel.gov/analysis/tech-lcoe-documentation.html
    return (l.i * (1 + l.i) ** l.n) / (((1 + l.i) ** l.n) - 1)

def lcoe_gen(l: LCOERequest, cf):
    numerator = l.lf * (1 - l.ldf) * (l.cg * crf(l) + l.omfg)
    denominator = l.lf * (1 - l.ldf) * cf * 8760
    return (numerator / denominator) + l.omvg

def lcoe_inter(l: LCOERequest, cf, ds):
    numerator = l.lf * (1 - l.ldf) * (ds * (l.ct * crf(l) + l.omft) + l.cs * crf(l))
    denominator = l.lf * (1 - l.ldf) * cf * 8760
    return numerator / denominator

def lcoe_road(l: LCOERequest, cf, dr):
    numerator = dr * (l.cr * crf(l) + l.omfr)
    denominator = cf * 50 * 8760
    return numerator / denominator

def get_cf(cf_tif_loc, geom):
    with rasterio.open(f's3://{BUCKET}/multiband/{cf_tif_loc}') as cf_tif:
        # find the window of our aoi
        project = pyproj.Transformer.from_proj(
            pyproj.Proj('epsg:4326'), # source coordinate system
            pyproj.Proj(cf_tif.crs), # destination coordinate system
        )
        g2 = transform(project.transform, geom)
        window = from_bounds(*g2.bounds, cf_tif.transform) 

        return cf_tif.read(1, window=window)

def get_dist(geom):
    with rasterio.open(f's3://{BUCKET}/multiband/distance.tif') as distance:
        # find the window of our aoi
        project = pyproj.Transformer.from_proj(
            pyproj.Proj('epsg:4326'), # source coordinate system
            pyproj.Proj(distance.crs), # destination coordinate system
        )
        g2 = transform(project.transform, geom)
        window = from_bounds(*g2.bounds, distance.transform)
        
        # distance from grid
        ds = np.nan_to_num(distance.read(4, window=window))  
        # distance from road
        dr = np.nan_to_num(distance.read(5, window=window))

        return (ds, dr)