from typing import Optional
from pydantic import BaseModel
from geojson_pydantic.geometries import Polygon
from fastapi import Request

class LCOERequest(BaseModel):
    """Levelized cost of energy request."""
    turbine_type: Optional[int] # Turbine Type or Solar Unit Type
    crf: float = 1 # capital recovery factor (CRF)
    cg: int = 2000 # Generation – capital [USD/kW] (Cg)
    omfg: int = 50000 # Generation – fixed O&M [USD/MW/y] (OMf,g)
    omvg: float = 4 # Generation – variable O&M [USD/MWh] (OMv,g)
    ct: int = 990 # Transmission (land cabling) – capital [USD/MW/km] (Ct)
    omft: int = 0 # Transmission – fixed O&M [USD/km] (OMf,t)
    cs: float = 71000 # Substation – capital [USD / two substations (per new transmission connection) ] (Cs)
    cr: float = 407000 # Road – capital [USD/km] (Cr)
    omfr: float = 0 # Road – fixed O&M [USD/km] (OMf,r)
    decom: float = 0 # Decommission % rate (Decom)
    i: float = 0.1 # Economic discount rate (i)
    n: float = 25 # Lifetime [years] (N)
    aoi: Polygon
