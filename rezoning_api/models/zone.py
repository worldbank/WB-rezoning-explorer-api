"""LCOE models"""
from enum import Enum
import re
from typing import Optional, Union, List
from pydantic import BaseModel, Field
from geojson_pydantic.geometries import Polygon, MultiPolygon

range_filter_regex = re.compile(r"-?[\d\.]+,-?[\d\.]+")
categorical_filter_regex = re.compile(r"(\w+,)*\w+")

LAND_COVER_OPTIONS = [
    "No Data",
    "Cropland",
    "Cropland, irrigated",
    "Mosaic cropland (>50%) / natural vegetation (<50%)",
    "Mosaic natural vegetation (>50%) / cropland (<50%)",
    "Tree cover, broadleaved, evergreen, closed to open (>15%)"
    "Tree cover, broadleaved, deciduous, closed to open (>15%)",
    "Tree cover, needleleaved, evergreen, closed to open (>15%)",
    "Tree cover, needleleaved, deciduous, closed to open (>15%)",
    "Tree cover, mixed leaf type (broadleaved and needleleaved)",
    "Mosaic tree and shrub (>50%) / herbaceous cover (<50%)",
    "Mosaic herbaceous cover (>50%) / tree and shrub (<50%)",
    "Shrubland",
    "Grassland",
    "Lichens and mosses",
    "Sparse vegetation (tree, shrub, herbaceous cover) (<15%)",
    "Tree cover, flooded, fresh or brackish water",
    "Tree cover, flooded, saline water",
    "Shrub or herbaceous cover, flooded, fresh/saline/brackish water",
    "Urban areas",
    "Bare areas",
    "Water bodies",
    "Permanent snow and ice",
]


class Category(Enum):
    """options for category"""

    BASIC = "BASIC"
    ADVANCED = "ADVANCED"


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
        m = categorical_filter_regex.fullmatch(v)
        if not m:
            raise ValueError("invalid categorical filter format")
        return cls(v)

    def __repr__(self):
        """string representation"""
        return f"CategoricalFilter({super().__repr__()})"


def WeightField(default: float = 0, title=None):
    """weight field defaults"""
    return Field(
        default,
        gte=0,
        lte=1,
        description=f"weight assigned to {title} parameter",
        title=title,
    )


def FilterField(
    default=None,
    title=None,
    description=None,
    unit=None,
    energy_type: List = ["solar", "wind", "offshore"],
    category=None,
    options=None,
    priority=False,
):
    """filter field defaults"""
    # TODO: evaulate whether we need this now that everything gets passed straight down
    return Field(
        default,
        description=description,
        title=title,
        unit=unit,
        energy_type=energy_type,
        category=category,
        options=options,
        priority=priority,
    )


class Weights(BaseModel):
    """User provided weights"""

    lcoe_gen: float = WeightField(0.4, title="LCOE Generation")
    lcoe_transmission: float = WeightField(0.05, title="LCOE Transmission")
    lcoe_road: float = WeightField(0.02, title="LCOE Road")
    grid: float = WeightField(0.15, title="Distance to Grid")
    worldpop: float = WeightField(0.05, title="Population Density")
    slope: float = WeightField(0.08, title="Slope")
    # capacity_value: float = WeightField(title="Capacity Value")
    airports: float = WeightField(title="Distance to Airports")
    ports: float = WeightField(title="Distance to Ports")
    anchorages: float = WeightField(title="Distance to Anchorages")
    roads: float = WeightField(title="Distance to Roads")
    pp_whs: float = WeightField(title="Protected Areas")
    unep_coral: float = WeightField(title="Coral")
    unesco: float = WeightField(title="UNESCO")
    unesco_ramsar: float = WeightField(title="Ramsar")
    wwf_glw_3: float = WeightField(title="Wetlands")
    pp_marine_protected: float = WeightField(title="Marine Protected")
    unep_tidal: float = WeightField(title="UNEP Tidal")
    gsa_gti: float = WeightField(title="GSA GTI")
    gsa_pvout: float = WeightField(title="GSA PVOUT")
    srtm90: float = WeightField(title="Elevation")
    gebco: float = WeightField(title="Bathymetry")
    waterbodies: float = WeightField(title="Waterbodies")


class LCOE(BaseModel):
    """User provided Levelized cost of energy inputs."""

    capacity_factor: str = Field(
        None,
        title="Turbine Type or Solar Unit Type",
        description="Annual capacity factor is a unitless ratio of the actual electrical energy output over a given period of time to the maximum possible electrical energy output over that period.",
    )
    crf: float = Field(
        1,
        title="Capital Recovery Factor (CRF)",
        description="A capital recovery factor is the ratio of a constant annuity to the present value of receiving that annuity for a given length of time.",
    )
    cg: int = Field(
        2000,
        title="Generation – capital [USD/kW] (Cg)",
        description="Capital expenditure for generation, per unit of capacity.",
    )
    omfg: int = Field(
        40,
        title="Generation – fixed O&M [USD/kW/y] (OMf,g)",
        description="Fixed Operation and Maintenance costs for the generation part of the system, per unit of capacity, per year.",
    )
    omvg: float = Field(
        4,
        title="Generation – variable O&M [USD/MWh] (OMv,g)",
        description="Variable Operation and Maintenance costs for generation, per unit of energy produced.",
    )
    ct: int = Field(
        1000,
        title="Transmission (land cabling) – capital [USD/MW/km] (Ct)",
        description="Capital expenditure for transmission (land cabling), per unit of capacity and distance.",
    )
    omft: int = Field(
        0,
        title="Transmission – fixed O&M [USD/MW/km] (OMf,t)",
        description="Fixed Operation and Maintenance costs for the transmission, per unit of distance, per year.",
    )
    cs: float = Field(
        70000,
        title="Substation – capital [USD / MW / two substations (per new transmission connection) ] (Cs)",
        description="Capital expenditure for new substations or upgrades per transmission connection.",
    )
    cr: float = Field(
        407000,
        title="Road – capital [USD/km] (Cr)",
        description="Capital expenditure for road infrastructure, per unit of distance. One road assumed for every 50 MW of installed capacity",
    )
    omfr: float = Field(
        0,
        title="Road – fixed O&M [USD/km] (OMf,r)",
        description="Fixed Operation and Maintenance costs for road infrastructure, per unit of distance, per year.",
    )
    decom: float = Field(
        0,
        title="Decommission % rate (Decom)",
        description="Decommissioning costs incurred at end of lifetime as a share of capital costs of generation.",
    )
    i: float = Field(
        0.1,
        title="Economic discount rate [%] (i)",
        description="Rate of return used to discount future cash flows back to their present value. This rate is often a company’s Weighted Average Cost of Capital (WACC), required rate of return, or the hurdle rate that investors expect to earn relative to the risk of the investment.",
    )
    n: float = Field(
        25, title="Lifetime [years] (N)", description="Lifetime of the power plant"
    )
    landuse: float = Field(
        0,
        title="Land Use Factor [MW/km2]",
        description="Land use factor is the average land area occupied by a power plant. More information: https://www.nrel.gov/analysis/tech-size.html ",
    )
    tlf: float = Field(
        0,
        title="Technical Loss Factor",
        description="Percentage of gross energy generation lost due to technical losses (e.g. wake effects for wind turbines; wiring and inverter losses for solar PV systems)",
    )
    af: float = Field(
        1,
        title="Unavailability Factor",
        description="Percentage of energy generation lost due to forced or scheduled outages (Applied after technical losses).",
    )


class Filters(BaseModel):
    """filter properties"""

    f_worldpop: Optional[RangeFilter] = FilterField(
        title="Population Density",
        unit="ppl/km²",
        category=Category.BASIC,
        description="Set a minimum and maximum value to the population density that will be in proximity to the suitable areas.",
        energy_type=["solar", "wind"],
    )
    f_slope: Optional[RangeFilter] = FilterField(
        title="Slope",
        unit="degrees",
        category=Category.BASIC,
        description="Set minimum and maximum slope to be included in the analysis.",
        energy_type=["solar", "wind"],
    )
    f_land_cover: Optional[CategorialFilter] = FilterField(
        title="Land Cover",
        category=Category.ADVANCED,
        options=LAND_COVER_OPTIONS,
        description="Select land cover type(s) to include in zone analysis.",
        energy_type=["solar", "wind"],
    )
    f_grid: Optional[RangeFilter] = FilterField(
        title="Transmission Lines (Distance to)",
        unit="meters",
        category=Category.BASIC,
        description="Set a minimum and maximum distance to transmission lines from suitable areas.",
        energy_type=["solar", "wind"],
    )
    f_airports: Optional[RangeFilter] = FilterField(
        title="Airports (Distance to)",
        unit="meters",
        category=Category.ADVANCED,
        description="Set the minimum and maximum distance to airports from suitable areas",
    )
    f_ports: Optional[RangeFilter] = FilterField(
        title="Ports (Distance to)",
        unit="meters",
        category=Category.ADVANCED,
        energy_type=["offshore"],
        description="Set a minimum and maximum distance to ports from suitable areas.",
    )
    f_anchorages: Optional[RangeFilter] = FilterField(
        title="Anchorages (Distance to)",
        unit="meters",
        category=Category.BASIC,
        energy_type=["offshore"],
        description="Set a minimum and maximum distance to anchorages from suitable areas.",
    )
    f_roads: Optional[RangeFilter] = FilterField(
        title="Roads (Distance to)",
        unit="meters",
        category=Category.ADVANCED,
        description="Areas within a defined distance to roads.",
        energy_type=["solar", "wind"],
    )
    f_pp_whs: Optional[bool] = FilterField(
        title="Protected Areas",
        category=Category.ADVANCED,
        description="Unselect this option to exclude protected areas from the analysis.",
        energy_type=["solar", "wind"],
    )
    f_unep_coral: Optional[bool] = FilterField(
        title="Coral Reefs",
        category=Category.ADVANCED,
        description="Unselect this option to exclude coral reefs from the analysis.",
        energy_type=["offshore"],
    )
    f_unesco: Optional[RangeFilter] = FilterField(
        title="UNESCO World Heritage Sites",
        unit="meters",
        category=Category.ADVANCED,
        description="Set a minimum distance to World Heritage Sites from suitable areas.",
    )
    f_unesco_ramsar: Optional[bool] = FilterField(
        title="Ramsar Sites",
        category=Category.ADVANCED,
        description="Unselect this option to exclude RAMSAR sites from the analysis.",
        energy_type=["offshore"],
    )
    f_wwf_glw_3: Optional[bool] = FilterField(
        title="Wetlands",
        category=Category.ADVANCED,
        description="Unselect this option to exclude wetlands from the analysis.",
        energy_type=["offshore"],
    )
    f_pp_marine_protected: Optional[bool] = FilterField(
        title="Protected Areas",
        category=Category.ADVANCED,
        description="Unselect this option to exclude protected areas from the analysis.",
        energy_type=["offshore"],
    )
    f_unep_tidal: Optional[bool] = FilterField(
        title="Intertidal Areas",
        category=Category.ADVANCED,
        description="Unselect this option to exclude intertidal areas from the analysis.",
        energy_type=["offshore"],
    )
    # f_capacity_value: Optional[RangeFilter] = FilterField(
    #     title="Capacity Value", category=Category.ZONE_PARAMETERS
    # )
    # f_lcoe_gen: Optional[RangeFilter] = FilterField(
    #     title="LCOE Generation", unit="$/MWh", category=Category.ZONE_PARAMETERS
    # )
    # f_lcoe_transmission: Optional[RangeFilter] = FilterField(
    #     title="LCOE Transmission", unit="$/MWh", category=Category.ZONE_PARAMETERS
    # )
    # f_lcoe_road: Optional[RangeFilter] = FilterField(
    #     title="LCOE Road", unit="$/MWh", category=Category.ZONE_PARAMETERS
    # )
    # f_gsa_gti: Optional[RangeFilter] = FilterField(
    #     title="Solar Radiation",
    #     unit="kWh/m²",
    #     category=Category.NATURAL,
    #     energy_type=["solar"],
    #     description="The solar resource, or electromagnetic radiation, emitted by the sun in a geographic location.",
    #     priority=True,
    # )
    f_gsa_pvout: Optional[RangeFilter] = FilterField(
        title="Solar PVOut",
        unit="kWh/m2/y",
        category=Category.BASIC,
        energy_type=["solar"],
        description="Set mimumum and maximum solar generation potential to be included in the analysis.",
        priority=True,
    )
    f_srtm90: Optional[RangeFilter] = FilterField(
        title="Elevation",
        unit="meters",
        category=Category.BASIC,
        energy_type=["solar", "wind"],
        description="Set minimum and maximum elevation to be included in the analysis.",
    )
    f_gebco: Optional[RangeFilter] = FilterField(
        title="Bathymetry",
        unit="meters",
        category=Category.BASIC,
        energy_type=["offshore"],
        description="Set minimum and maximum water depth for floating foundation technology. Floating foundations begin at below 50 meters.",
    )
    f_waterbodies: Optional[bool] = FilterField(
        title="Water Bodies",
        category=Category.ADVANCED,
        description="Unselect this option to exclude water bodies from the analysis.",
        energy_type=["solar", "wind"],
    )
    f_gwa_speed_100: Optional[RangeFilter] = FilterField(
        title="Wind Speed",
        category=Category.BASIC,
        energy_type=["wind", "offshore"],
        unit="m/s",
        description="Set mimumum and maximum wind speed to be included in the analysis.",
        priority=True,
    )
    # f_air_density: Optional[RangeFilter] = FilterField(
    #     title="Air Density",
    #     category=Category.NATURAL,
    #     energy_type=["offshore", "wind"],
    #     unit="kg/m³",
    #     description="The density of air, or atmospheric density, is the mass per unit volume of Earth's atmosphere.",
    #     priority=True,
    # )


class ZoneRequest(BaseModel):
    """Zone POST request"""

    aoi: Union[Polygon, MultiPolygon]
    lcoe: LCOE
    weights: Weights = Weights()


class ExportRequest(BaseModel):
    """Export POST request"""

    lcoe: LCOE
    weights: Weights = Weights()
    filters: Filters = Filters()


class ZoneResponse(BaseModel):
    """Zone POST response"""

    lcoe: float = Field(..., title="Levelized Cost of Electrification ($USD / GWh)")
    zone_score: float = Field(..., title="Zone Score")
    zone_output: float = Field(..., title="Zone Output (GWh)")
    zone_output_density: float = Field(..., title="Zone Output Density (kWh / m2)")
