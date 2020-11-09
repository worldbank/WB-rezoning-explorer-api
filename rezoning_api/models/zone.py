"""LCOE models"""
from typing import Optional, Union
from pydantic import BaseModel, Field
from geojson_pydantic.geometries import Polygon, MultiPolygon


def WeightField(title=None):
    """weight field defaults"""
    return Field(
        0.5,
        gte=0,
        lte=1,
        description=f"weight assigned to {title} parameter",
        title=title,
    )


class Weights(BaseModel):
    """User provided weights"""

    lcoe_gen: float = WeightField(title="LCOE Generation")
    lcoe_transmission: float = WeightField(title="LCOE Transmission")
    lcoe_road: float = WeightField(title="LCOE Road")
    grid: float = WeightField(title="Distance to Grid")
    worldpop: float = WeightField(title="Population Density")
    slope: float = WeightField(title="Slope")
    capacity_value: float = WeightField(title="Capacity Value")
    aipports: float = WeightField(title="Distanct to Airports")


class LCOE(BaseModel):
    """User provided Levelized cost of energy inputs."""

    turbine_type: Optional[int] = Field(None, title="Turbine Type or Solar Unit Type")
    crf: float = Field(1, title="Capital Recovery Factor (CRF)")
    cg: int = Field(2000, title="Generation – capital [USD/kW] (Cg)")
    omfg: int = Field(50000, title="Generation – fixed O&M [USD/MW/y] (OMf,g)")
    omvg: float = Field(4, title="Generation – variable O&M [USD/MWh] (OMv,g)")
    ct: int = Field(990, title="Transmission (land cabling) – capital [USD/MW/km] (Ct)")
    omft: int = Field(0, title="Transmission – fixed O&M [USD/km] (OMf,t)")
    cs: float = Field(
        71000,
        title="Substation – capital [USD / two substations (per new transmission connection) ] (Cs)",
    )
    cr: float = Field(407000, title="Road – capital [USD/km] (Cr)")
    omfr: float = Field(0, title="Road – fixed O&M [USD/km] (OMf,r)")
    decom: float = Field(0, title="Decommission % rate (Decom)")
    i: float = Field(0.1, title="Economic discount rate (i)")
    n: float = Field(25, title="Lifetime [years] (N)")


class ZoneRequest(BaseModel):
    """Zone POST request"""

    aoi: Union[Polygon, MultiPolygon]
    lcoe: LCOE = LCOE()
    weights: Weights = Weights()


class ZoneResponse(BaseModel):
    """Zone POST response"""

    lcoe: float = Field(..., title="Levelized Cost of Electrification ($USD / GWh)")
    zone_score: float = Field(..., title="Zone Score")
    zone_output: float = Field(..., title="Zone Output (GWh)")
    zone_output_density: float = Field(..., title="Zone Output Density (kWh / m2)")
