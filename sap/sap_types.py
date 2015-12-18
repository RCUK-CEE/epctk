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