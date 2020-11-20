"""LCOE models"""
from enum import Enum
import re
from typing import Optional, Union, List
from pydantic import BaseModel, Field
from geojson_pydantic.geometries import Polygon, MultiPolygon

range_filter_regex = re.compile(r"[\d\.]+,[\d\.]+")
categorical_filter_regex = re.compile(r"(\w+,)*\w+")


class Category(Enum):
    """options for category"""

    NATURAL = "natural"
    INFRASTRUCTURE = "infrastructure"
    ENVIRONMENT = "environment"
    CULTURAL = "cultural"
    ZONE_PARAMETERS = "zone parameters"


class RangeFilter(str):
    """custom validator for range filters"""

    @classmethod
    def __get_validators__(cls):
        """validator"""
        yield cls.validate

    @classmethod
    def __modify_schema__(cls, field_schema):
        """update schema"""
        field_schema.update(
            pattern="range_filter",
            examples=["0,1000", "5,1000", "0,100"],
        )

    @classmethod
    def validate(cls, v):
        """validate inputs"""
        if not isinstance(v, str):
            raise TypeError("string required")
        m = range_filter_regex.fullmatch(v)
        if not m:
            raise ValueError("invalid range filter format")
        return cls(v)

    def __repr__(self):
        """string representation"""
        return f"RangeFilter({super().__repr__()})"


class CategorialFilter(str):
    """custom validator for range filters"""

    @classmethod
    def __get_validators__(cls):
        """validator"""
        yield cls.validate

    @classmethod
    def __modify_schema__(cls, field_schema):
        """update schema"""
        field_schema.update(
            pattern="categorical_filter",
            examples=["0,1,2,3,4", "1,3,5,7,8"],
        )

    @classmethod
    def validate(cls, v):
        """validate inputs"""
        if not isinstance(v, str):
            raise TypeError("string required")
        m = range_filter_regex.fullmatch(v)
        if not m:
            raise ValueError("invalid categorical filter format")
        return cls(v)

    def __repr__(self):
        """string representation"""
        return f"CategoricalFilter({super().__repr__()})"


def WeightField(title=None):
    """weight field defaults"""
    return Field(
        0.5,
        gte=0,
        lte=1,
        description=f"weight assigned to {title} parameter",
        title=title,
    )


def FilterField(
    default=None,
    title=None,
    unit=None,
    energy_type: List = ["solar", "wind", "offshore"],
    category=None,
):
    """filter field defaults"""
    return Field(
        default,
        description=f"filter on the {title} parameter",
        title=title,
        unit=unit,
        energy_type=energy_type,
        category=category,
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

    f_worldpop: Optional[RangeFilter] = FilterField(
        title="Population Density", unit="ppl/km²", category=Category.NATURAL
    )
    f_slope: Optional[RangeFilter] = FilterField(
        title="Slope", unit="degress", category=Category.NATURAL
    )
    f_land_cover: Optional[CategorialFilter] = FilterField(
        title="Land Cover", category=Category.NATURAL
    )

    f_grid: Optional[RangeFilter] = FilterField(
        title="Distance to Grid", unit="meters", category=Category.INFRASTRUCTURE
    )
    f_airports: Optional[RangeFilter] = FilterField(
        title="Distanct to Airports", unit="meters", category=Category.INFRASTRUCTURE
    )
    f_ports: Optional[RangeFilter] = FilterField(
        title="Distance to Ports",
        unit="meters",
        category=Category.INFRASTRUCTURE,
        energy_type=["offshore"],
    )
    f_anchorages: Optional[RangeFilter] = FilterField(
        title="Distance to Anchorages",
        unit="meters",
        category=Category.INFRASTRUCTURE,
        energy_type=["offshore"],
    )
    f_roads: Optional[RangeFilter] = FilterField(
        title="Distance to Roads", unit="meters", category=Category.INFRASTRUCTURE
    )

    f_pp_whs: Optional[RangeFilter] = FilterField(
        title="Distance to World Heritage Sites",
        unit="meters",
        category=Category.ENVIRONMENT,
    )
    f_unep_coral: Optional[RangeFilter] = FilterField(
        title="Distance to Coral", unit="meters", category=Category.ENVIRONMENT
    )
    f_unesco: Optional[RangeFilter] = FilterField(
        title="Distance to Cultural Sites", unit="meters", category=Category.CULTURAL
    )
    f_unesco_ramsar: Optional[RangeFilter] = FilterField(
        title="Distance to Ramsar Wetlands",
        unit="meters",
        category=Category.ENVIRONMENT,
    )
    f_wwf_glw_3: Optional[bool] = FilterField(
        title="Wetlands", category=Category.ENVIRONMENT
    )

    f_pp_marine_protected: Optional[bool] = FilterField(
        False, title="Marine Protected Zone", category=Category.ENVIRONMENT
    )
    f_unep_tidal: Optional[bool] = FilterField(
        False, title="Tidal Zone", category=Category.ENVIRONMENT
    )

    f_capacity_value: Optional[RangeFilter] = FilterField(
        title="Capacity Value", category=Category.ZONE_PARAMETERS
    )
    f_lcoe_gen: Optional[RangeFilter] = FilterField(
        title="LCOE Generation", unit="$/MWh", category=Category.ZONE_PARAMETERS
    )
    f_lcoe_transmission: Optional[RangeFilter] = FilterField(
        title="LCOE Transmission", unit="$/MWh", category=Category.ZONE_PARAMETERS
    )
    f_lcoe_road: Optional[RangeFilter] = FilterField(
        title="LCOE Road", unit="$/MWh", category=Category.ZONE_PARAMETERS
    )

    f_gsa_gti: Optional[RangeFilter] = FilterField(
        title="Solar Radiation",
        unit="kWh/m²",
        category=Category.NATURAL,
        energy_type=["solar"],
    )
    f_gsa_pvout: Optional[RangeFilter] = FilterField(
        title="Solar PVOut",
        unit="kWh/kWp",
        category=Category.NATURAL,
        energy_type=["solar"],
    )
    f_srtm90: Optional[RangeFilter] = FilterField(
        title="Elevation",
        unit="meters",
        category=Category.NATURAL,
        energy_type=["solar", "wind"],
    )
    f_gebco: Optional[RangeFilter] = FilterField(
        title="Bathymetry",
        unit="meters",
        category=Category.NATURAL,
        energy_type=["offshore"],
    )
    f_waterbodies: Optional[bool] = FilterField(
        title="Water Bodies", category=Category.NATURAL
    )


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
