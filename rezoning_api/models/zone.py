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


def FilterField(title=None):
    """filter field defaults"""
    return Field(None, description=f"filter on the {title} parameter", title=title)


class Weights(BaseModel):
    """User provided weights"""

    lcoe_gen: float = WeightField(title="LCOE Generation")
    lcoe_transmission: float = WeightField(title="LCOE Transmission")
    lcoe_road: float = WeightField(title="LCOE Road")
    grid: float = WeightField(title="Distance to Grid")
    worldpop: float = WeightField(title="Population Density")
    slope: float = WeightField(title="Slope")
    capacity_value: float = WeightField(title="Capacity Value")
    airports: float = WeightField(title="Distanct to Airports")


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
    landuse: float = Field(0, title="Land use score")
    tlf: float = Field(0, title="Technical Loss Factor")
    af: float = Field(1, title="Availability Factor")


class Filters(BaseModel):
    """filter properties"""

    f_worldpop: Optional[str] = FilterField(title="Population Density")
    f_slope: Optional[str] = FilterField(title="Slope")

    f_grid: Optional[str] = FilterField(title="Distance to Grid")
    f_airports: Optional[str] = FilterField(title="Distanct to Airports")
    f_ports: Optional[str] = FilterField(title="")
    f_anchorages: Optional[str] = FilterField(title="")
    f_roads: Optional[str] = FilterField(title="Distance to Roads")

    f_pp_whs: Optional[str] = FilterField(title="")
    f_unep_coral: Optional[str] = FilterField(title="")
    f_unesco: Optional[str] = FilterField(title="")
    f_unesco_ramsar: Optional[str] = FilterField(title="")
    f_wwf_glw_1: Optional[str] = FilterField(title="")
    f_wwf_glw_2: Optional[str] = FilterField(title="")

    f_jrc_gsw: Optional[str] = FilterField(title="")
    f_pp_marine_protected: Optional[str] = FilterField(title="")
    f_unep_tidal: Optional[str] = FilterField(title="")
    f_wwf_glw_3: Optional[str] = FilterField(title="")

    f_capacity_value: Optional[str] = FilterField(title="Capacity Value")
    f_lcoe_gen: Optional[str] = FilterField(title="LCOE Generation")
    f_lcoe_transmission: Optional[str] = FilterField(title="LCOE Transmission")
    f_lcoe_road: Optional[str] = FilterField(title="LCOE Road")


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
