from enum import Enum, IntEnum

from ..utils import SAPInputError


class DwellingType(Enum):
    HOUSE = 'house'
    FLAT = 'flat'
    BUNGALOW = 'bungalow'
    MAISONETTE = 'maisonette'


class DwellingSubType(IntEnum):
    DETACHED = 1
    SEMI_DETACHED = 2
    MID_TERRACE = 3
    END_TERRACE = 4
    ENCLOSED_MID_TERRACE = 5
    ENCLOSED_END_TERRACE = 6


class TerrainTypes(IntEnum):
    DENSE_URBAN = 1
    SUBURBAN = 2
    RURAL = 3


class WallTypes(IntEnum):
    MASONRY = 1
    OTHER = 2


class FloorTypes(IntEnum):
    SUSPENDED_TIMBER_UNSEALED = 1
    SUSPENDED_TIMBER_SEALED = 2
    NOT_SUSPENDED_TIMBER = 3
    OTHER = 4


class ImmersionTypes(IntEnum):
    SINGLE = 1
    DUAL = 2


class FuelTypes(IntEnum):
    GAS = 1
    OIL = 2
    SOLID = 3
    ELECTRIC = 4
    COMMUNAL = 5


class CylinderInsulationTypes(IntEnum):
    NONE = 0
    FOAM = 1
    JACKET = 2


class GlazingTypes(IntEnum):
    SINGLE = 1
    DOUBLE = 2
    TRIPLE = 3
    SECONDARY = 4


_light_transmittance = {
    GlazingTypes.SINGLE: 0.9,
    GlazingTypes.DOUBLE: 0.8,
    GlazingTypes.TRIPLE: 0.7,
    GlazingTypes.SECONDARY: 0.8
}


class ThermalStoreTypes(IntEnum):
    HW_ONLY = 1
    INTEGRATED = 2


class OvershadingTypes(IntEnum):
    HEAVY = 0
    MORE_THAN_AVERAGE = 1
    AVERAGE = 2
    VERY_LITTLE = 3


class SHWCollectorTypes(IntEnum):
    EVACUATED_TUBE = 1
    FLAT_PLATE_GLAZED = 2
    UNGLAZED = 3


class HeatingTypes(IntEnum):
    misc = 0
    combi = 1
    cpsu = 2
    storage_heater = 3
    integrated_system = 4
    electric_boiler = 5
    regular_boiler = 6
    heat_pump = 7
    room_heater = 8
    warm_air = 9
    off_peak_only = 10
    pcdf_heat_pump = 11
    community = 12
    storage_combi = 13
    microchp = 14


class PVOvershading(IntEnum):
    HEAVY = 1
    SIGNIFICANT = 2
    MODEST = 3
    NONE_OR_VERY_LITTLE = 4


class OpeningTypeDataSource(IntEnum):
    SAP = 1
    BFRC = 2
    MANUFACTURER = 3


class HeatLossElementTypes(IntEnum):
    EXTERNAL_WALL = 1
    PARTY_WALL = 2
    EXTERNAL_FLOOR = 3
    EXTERNAL_ROOF = 4
    OPAQUE_DOOR = 5
    GLAZING = 6


# Table 4c
class HeatEmitters(IntEnum):
    RADIATORS = 1
    UNDERFLOOR_TIMBER = 2
    UNDERFLOOR_SCREED = 3
    UNDERFLOOR_CONCRETE = 4
    RADIATORS_UNDERFLOOR_TIMBER = 5
    RADIATORS_UNDERFLOOR_SCREED = 6
    RADIATORS_UNDERFLOOR_CONCRETE = 7
    FAN_COILS = 8


class LoadCompensators(IntEnum):
    LOAD_COMPENSATOR = 1
    ENHANCED_LOAD_COMPENSATOR = 2
    WEATHER_COMPENSATOR = 3


class VentilationTypes(IntEnum):
    NATURAL = 0
    MEV_CENTRALISED = 1
    MEV_DECENTRALISED = 2
    MVHR = 3
    MV = 4
    PIV_FROM_OUTSIDE = 5


class DuctTypes(IntEnum):
    FLEXIBLE = 1
    RIGID = 2
    FLEXIBLE_INSULATED = 3  # For use with mvhr
    RIGID_INSULATED = 4  # For use with mvhr
    NONE = 5


class BoilerTypes(IntEnum):
    REGULAR = 1
    COMBI = 2
    CPSU = 3
    OTHER = 4


class CommunityDistributionTypes(IntEnum):
    PRE_1990_UNINSULATED = 1
    PRE_1990_INSULATED = 2
    MODERN_HIGH_TEMP = 3
    MODERN_LOW_TEMP = 4


class OpeningType(dict):
    """
    Contains opening type properties

    This is a thin wrapper for a dict, so that we can treat everything as
    semi-structured data, easily convertible to JSON or similar format.
    To maintain compatiblity with original code, add getattr override
    as for dwelling object
    """
    def __init__(self, glazing_type, gvalue, frame_factor, Uvalue, roof_window, bfrc_data=False):
        super().__init__(glazing_type=glazing_type, gvalue=gvalue,
                         light_transmittance=_light_transmittance[glazing_type], frame_factor=frame_factor,
                         Uvalue=Uvalue, roof_window=roof_window, bfrc_data=bfrc_data)
        self.gvalue = self['gvalue']
        self.light_transmittance = self['light_transmittance']
        self.frame_factor = self['frame_factor']
        self.Uvalue = self['Uvalue']
        self.roof_window = self['roof_window']
        self.bfrc_data = self['bfrc_data']
        self.glazing_type = self['glazing_type']

    # def __getattr__(self, item):
    #     """
    #     Make dict keys accessible as attributes. If an item is not in the
    #     dict, return it from the object `__dict__`
    #
    #     """
    #     try:
    #         return self[item]
    #     except KeyError:
    #         try:
    #             return self.__dict__[item]
    #         except KeyError:
    #             raise AttributeError(item)
class HeatLossElement:
    def __init__(self, area, Uvalue, is_external, element_type, name=""):
        self.area = area
        self.Uvalue = Uvalue
        self.is_external = is_external
        self.name = name
        self.element_type = element_type


class ThermalMassElement:
    def __init__(self, area, kvalue, name=""):
        self.area = area
        self.kvalue = kvalue
        self.name = name


class Opening:
    def __init__(self, area, orientation_degrees, opening_type, name=""):
        self.area = area
        self.orientation_degrees = orientation_degrees
        self.opening_type = opening_type
        self.name = name
