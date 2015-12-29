class WallTypes(object):
    MASONRY = 1
    OTHER = 2


class FloorTypes(object):
    SUSPENDED_TIMBER_UNSEALED = 1
    SUSPENDED_TIMBER_SEALED = 2
    NOT_SUSPENDED_TIMBER = 3
    OTHER = 4


class ImmersionTypes(object):
    SINGLE = 1
    DUAL = 2


class TerrainTypes(object):
    DENSE_URBAN = 1
    SUBURBAN = 2
    RURAL = 3


class FuelTypes(object):
    GAS = 1
    OIL = 2
    SOLID = 3
    ELECTRIC = 4
    COMMUNAL = 5


class CylinderInsulationTypes:
    NONE = 0
    FOAM = 1
    JACKET = 2


class GlazingTypes:
    SINGLE = 1
    DOUBLE = 2
    TRIPLE = 3
    SECONDARY = 4


light_transmittance = {
    GlazingTypes.SINGLE: 0.9,
    GlazingTypes.DOUBLE: 0.8,
    GlazingTypes.TRIPLE: 0.7,
    GlazingTypes.SECONDARY: 0.8
}

class OpeningType:
    def __init__(self, glazing_type, gvalue, frame_factor, Uvalue, roof_window, bfrc_data=False):
        self.gvalue = gvalue
        self.light_transmittance = light_transmittance[glazing_type] # will raise KeyError if wrong glazing type
        self.frame_factor = frame_factor
        self.Uvalue = Uvalue
        self.roof_window = roof_window
        self.bfrc_data = bfrc_data
        self.glazing_type = glazing_type


class ThermalStoreTypes(object):
    HW_ONLY = 1
    INTEGRATED = 2


class OvershadingTypes(object):
    HEAVY = 0
    MORE_THAN_AVERAGE = 1
    AVERAGE = 2
    VERY_LITTLE = 3


class SHWCollectorTypes(object):
    EVACUATED_TUBE = 1
    FLAT_PLATE_GLAZED = 2
    UNGLAZED = 3


class HeatingTypes:
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


class PVOvershading(object):
    HEAVY = 1
    SIGNIFICANT = 2
    MODEST = 3
    NONE_OR_VERY_LITTLE = 4


class OpeningTypeDataSource:
    SAP = 1
    BFRC = 2
    MANUFACTURER = 3


class HeatLossElementTypes:
    EXTERNAL_WALL = 1
    PARTY_WALL = 2
    EXTERNAL_FLOOR = 3
    EXTERNAL_ROOF = 4
    OPAQUE_DOOR = 5
    GLAZING = 6

#
# def light_transmittance_from_glazing_type(glazing_type):
#     if glazing_type == GlazingTypes.SINGLE:
#         return 0.9
#     elif glazing_type == GlazingTypes.DOUBLE:
#         return 0.8
#     elif glazing_type == GlazingTypes.TRIPLE:
#         return 0.7
#     elif glazing_type == GlazingTypes.SECONDARY:
#         return .8
#     else:
#         raise RuntimeError("unknown glazing type %s" % glazing_type)

# Table 4c
class HeatEmitters(object):
    RADIATORS = 1
    UNDERFLOOR_TIMBER = 2
    UNDERFLOOR_SCREED = 3
    UNDERFLOOR_CONCRETE = 4
    RADIATORS_UNDERFLOOR_TIMBER = 5
    RADIATORS_UNDERFLOOR_SCREED = 6
    RADIATORS_UNDERFLOOR_CONCRETE = 7
    FAN_COILS = 8


class LoadCompensators(object):
    LOAD_COMPENSATOR = 1
    ENHANCED_LOAD_COMPENSATOR = 2
    WEATHER_COMPENSATOR = 3


class VentilationTypes:
    NATURAL = 0
    MEV_CENTRALISED = 1
    MEV_DECENTRALISED = 2
    MVHR = 3
    MV = 4
    PIV_FROM_OUTSIDE = 5


class DuctTypes:
    FLEXIBLE = 1
    RIGID = 2
    FLEXIBLE_INSULATED = 3  # For use with mvhr
    RIGID_INSULATED = 4  # For use with mvhr
    NONE = 5


class BoilerTypes:
    REGULAR=1
    COMBI=2
    CPSU=3
    OTHER=4


class CommunityDistributionTypes:
    PRE_1990_UNINSULATED = 1
    PRE_1990_INSULATED = 2
    MODERN_HIGH_TEMP = 3
    MODERN_LOW_TEMP = 4


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