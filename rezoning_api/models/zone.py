"""LCOE models"""
from typing import Optional
from pydantic import BaseModel, Field
from geojson_pydantic.geometries import Polygon

def WeightField(title=None):
    return Field(0.5, gt=0, lt=1, description=f'weight assigned to {title} parameter', title=title)


class Weights(BaseModel):
    Field()
    lcoe_gen: float = WeightField(title="LCOE Generation")
    lcoe_transmission: float = WeightField(title="LCOE Transmission")
    lcoe_road: float = WeightField(title="LCOE Road")
    distance_load: float = WeightField(title="Distance to Load")
    technology_colocation: float = WeightField(title="Technology Colocation")
    human_footprint: float = WeightField(title="Human Footprint")
    pop_density: float = WeightField(title="Population Density")
    slope: float = WeightField(title="Slope")
    land_use: float = WeightField(title="Land Use Score")
    capacity_value: float = WeightField(title="Capacity Value")

class LCOE(BaseModel):
    """Levelized cost of energy request."""

    turbine_type: Optional[int] = Field(None, title="Turbine Type or Solar Unit Type")
    crf: float = Field(1, title="Capital Recovery Factor (CRF)")
    cg: int = Field(2000, title="Generation – capital [USD/kW] (Cg)")
    omfg: int = Field(50000, title="Generation – fixed O&M [USD/MW/y] (OMf,g)")
    omvg: float = Field(4, title="Generation – variable O&M [USD/MWh] (OMv,g)")
    ct: int = Field(990, title="Transmission (land cabling) – capital [USD/MW/km] (Ct)")
    omft: int = Field(0, title="Transmission – fixed O&M [USD/km] (OMf,t)")
    cs: float = Field(71000, title="Substation – capital [USD / two substations (per new transmission connection) ] (Cs)")
    cr: float = Field(407000, title="Road – capital [USD/km] (Cr)")
    omfr: float = Field(0, title="Road – fixed O&M [USD/km] (OMf,r)")
    decom: float = Field(0, title="Decommission % rate (Decom)")
    i: float = Field(0.1, title="Economic discount rate (i)")
    n: float = Field(25, title="Lifetime [years] (N)")

class ZoneRequest(BaseModel):
    aoi: Polygon
    lcoe: LCOE = LCOE()
    weights: Weights = Weights()
