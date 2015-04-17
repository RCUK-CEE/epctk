import csv
import math
import numpy
from . import sap_worksheet
import re
from . import pcdf
import logging
import types

DATA_FILE_LOCATION = './sap/'

Igh_heating = numpy.array([26, 54, 94, 150, 190, 201, 194, 164, 116, 68, 33, 21])
Texternal_heating = numpy.array([4.5, 5, 6.8, 8.7, 11.7, 14.6, 16.9, 16.9, 14.3, 10.8, 7, 4.9])
wind_speed = numpy.array([5.4, 5.1, 5.1, 4.5, 4.1, 3.9, 3.7, 3.7, 4.2, 4.5, 4.8, 5.1])


def float_or_zero(s):
    return float(s) if s != '' else 0


def float_or_none(s):
    return float(s) if s != '' else None


class SAPCalculationError(RuntimeError):
    pass


def csv_to_dict(filename, translator):
    results = {}
    with open(filename, 'r') as infile:
        reader = csv.reader(infile)
        for row in reader:
            if row[0][0] == '#':
                continue
            translator(results, row)
    return results


class FuelTypes(object):
    GAS = 1
    OIL = 2
    SOLID = 3
    ELECTRIC = 4
    COMMUNAL = 5


class FuelData:
    def __init__(self,
                 name,
                 fuel_id,
                 co2_factor,
                 fuel_factor,
                 emission_factor_adjustment,
                 price,
                 standing_charge,
                 primary_energy_factor,
                 fuel_type):
        self.name = name
        self.fuel_id = fuel_id
        self.co2_factor = co2_factor
        self.fuel_factor = fuel_factor
        self.emission_factor_adjustment = emission_factor_adjustment
        self.price = price
        self.standing_charge = standing_charge
        self.primary_energy_factor = primary_energy_factor
        self.fuel_type = fuel_type


def get_fuel_data_table_12(fuel_id):
    return TABLE_12_DATA[fuel_id]


import copy

PCDF_FUEL_PRICES = None


def get_fuel_data_pcdf(fuel_id):
    global PCDF_FUEL_PRICES
    if PCDF_FUEL_PRICES is None:
        PCDF_FUEL_PRICES = pcdf.get_fuel_prices()

    if fuel_id in PCDF_FUEL_PRICES:
        pcdf_data = PCDF_FUEL_PRICES[fuel_id]

        f = copy.deepcopy(get_fuel_data_table_12(fuel_id))
        f.standing_charge = pcdf_data['standing_charge']
        f.price = pcdf_data['price']

        return f
    elif fuel_id in [51, 52, 53, 54, 55, 41, 42, 43, 44, 45, 46]:
        # community heating - uses fuel code 47 in pcdf
        pcdf_data = PCDF_FUEL_PRICES[47]
        f = copy.deepcopy(get_fuel_data_table_12(fuel_id))
        f.standing_charge = pcdf_data['standing_charge']
        f.price = pcdf_data['price']
        return f
    else:
        return get_fuel_data_table_12(fuel_id)


get_fuel_data = get_fuel_data_table_12


class Fuel(object):
    def __init__(self,
                 fuel_id,
                 ):
        self.fuel_id = fuel_id
        self._fuel_data = None

    def __hash__(self):
        return self.fuel_id

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.fuel_id == other.fuel_id
        else:
            return False

    def unit_price(self):
        return self.fuel_data.price

    @property
    def standing_charge(self):
        return self.fuel_data.standing_charge

    @property
    def is_mains_gas(self):
        return self.fuel_id == 1 or self.fuel_id == 51

    @property
    def is_electric(self):
        return False

    @property
    def type(self):
        return self.fuel_data.fuel_type

    @property
    def co2_factor(self):
        return self.fuel_data.co2_factor

    @property
    def primary_energy_factor(self):
        return self.fuel_data.primary_energy_factor

    @property
    def fuel_factor(self):
        return self.fuel_data.fuel_factor

    @property
    def emission_factor_adjustment(self):
        return self.fuel_data.emission_factor_adjustment

    @property
    def name(self):
        return self.fuel_data.name

    @property
    def fuel_data(self):
        return get_fuel_data(self.fuel_id)

        # !!! Ideally instead of continually getting fuel data
        # !!! (above), would just load it at beginning of calc, as
        # !!! below, except that need to invalidate the fuel data in
        # !!! between calcs
        if self._fuel_data is None:
            self._fuel_data = get_fuel_data(self.fuel_id)
        return self._fuel_data


FUEL_TYPES = dict(
    GAS=FuelTypes.GAS,
    OIL=FuelTypes.OIL,
    SOLID=FuelTypes.SOLID,
    COMMUNAL=FuelTypes.COMMUNAL,
    ELECTRIC=FuelTypes.ELECTRIC,
)


def translate_12_row(fuels, row):
    # !!! Shouldn't allow None values for some of these columns
    f = FuelData(row[0],
                 int(row[1]),
                 float_or_none(row[2]),
                 float_or_none(row[3]),
                 float(row[4]) / float(row[5]) if row[4] != "" else None,
                 float_or_none(row[6]),
                 float_or_none(row[7]),
                 float_or_none(row[8]),
                 FUEL_TYPES[row[9]])

    fuels[f.fuel_id] = f


TABLE_12_DATA = csv_to_dict(DATA_FILE_LOCATION + 'table_12.csv', translate_12_row)


class ElectricityTariff(object):
    # !!! Assumes that emissions for on and off peak are same
    # !!! Assumes that on and off peak standing charge is same
    def __init__(self,
                 on_peak_fuel_code,
                 off_peak_fuel_code,
                 general_elec_on_peak_fraction,
                 mech_vent_on_peak_fraction):
        self.is_electric = True
        self.type = FuelTypes.ELECTRIC
        self.is_mains_gas = False

        self.general_elec_on_peak_fraction = general_elec_on_peak_fraction
        self.mech_vent_elec_on_peak_fraction = mech_vent_on_peak_fraction

        self.on_peak_fuel_code = on_peak_fuel_code
        self.off_peak_fuel_code = off_peak_fuel_code

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __hash__(self):
        return hash((self.is_electric, self.type, self.is_mains_gas, self.general_elec_on_peak_fraction,
                     self.mech_vent_elec_on_peak_fraction, self.on_peak_fuel_code, self.off_peak_fuel_code))

    def unit_price(self, onpeak_fraction=1):
        price_on_peak = self.on_peak_data.price
        price_off_peak = self.off_peak_data.price
        return (price_on_peak * onpeak_fraction
                + price_off_peak * (1 - onpeak_fraction))

    @property
    def co2_factor(self):
        return self.on_peak_data.co2_factor

    @property
    def primary_energy_factor(self):
        return self.on_peak_data.primary_energy_factor

    @property
    def fuel_factor(self):
        return self.on_peak_data.fuel_factor

    @property
    def emission_factor_adjustment(self):
        return self.on_peak_data.emission_factor_adjustment

    @property
    def standing_charge(self):
        return self.on_peak_data.standing_charge

    @property
    def on_peak_data(self):
        return get_fuel_data(self.on_peak_fuel_code)

    @property
    def off_peak_data(self):
        return get_fuel_data(self.off_peak_fuel_code)

    @property
    def name(self):
        on_peak_name = self.on_peak_data.name
        return on_peak_name.split("(")[0].strip()

# ELECTRICITY_FROM_CHP=Fuel(49,.529,None,None,None,106,2.92,FuelTypes.COMMUNAL)
#ELECTRICITY_FOR_DISTRIBUTION_NETWORK=Fuel(50,.517,None,None,None,106,2.92,FuelTypes.COMMUNAL)

ELECTRICITY_STANDARD = ElectricityTariff(30, 30, 1, 1)
ELECTRICITY_7HR = ElectricityTariff(32, 31, .9, .71)
ELECTRICITY_10HR = ElectricityTariff(34, 33, .8, .58)
ELECTRICITY_24HR = ElectricityTariff(35, 35, 1, 1)

ELECTRICITY_OFFSET = ElectricityTariff(37, 37, 1, 1)
ELECTRICITY_SOLD = ElectricityTariff(36, 36, 1, 1)

HEAT_FROM_CHP = Fuel(48)

TABLE_12_ELEC = {
    30: ELECTRICITY_STANDARD,
    32: ELECTRICITY_7HR,
    31: ELECTRICITY_7HR,
    34: ELECTRICITY_10HR,
    33: ELECTRICITY_10HR,
    35: ELECTRICITY_24HR,
}


def fuel_from_code(code):
    if code in TABLE_12_ELEC:
        return copy.deepcopy(TABLE_12_ELEC[code])
    else:
        return Fuel(code)


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


class PVOvershading(object):
    HEAVY = 1
    SIGNIFICANT = 2
    MODEST = 3
    NONE_OR_VERY_LITTLE = 4


class TerrainTypes(object):
    DENSE_URBAN = 1
    SUBURBAN = 2
    RURAL = 3


FLOOR_INFILTRATION = {
    FloorTypes.SUSPENDED_TIMBER_UNSEALED: 0.2,
    FloorTypes.SUSPENDED_TIMBER_SEALED: 0.1,
    FloorTypes.NOT_SUSPENDED_TIMBER: 0,
    FloorTypes.OTHER: 0,
}


def true_and_not_missing(d, attr):
    return hasattr(d, attr) and getattr(d, attr)

# Table 1a
DAYS_PER_MONTH = numpy.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])

# Table 1b part 1
def occupancy(dwelling):
    return 1 + 1.76 * (1 - math.exp(-0.000349 * (dwelling.GFA - 13.9) ** 2)) + 0.0013 * (
    dwelling.GFA - 13.9) if dwelling.GFA > 13.9 else 1


# Table 1b part 2
def daily_hw_use(dwelling):
    if dwelling.low_water_use:
        return (25. * dwelling.Nocc + 36.) * .95
    else:
        return 25. * dwelling.Nocc + 36.

# Table 1c
MONTHLY_HOT_WATER_FACTORS = numpy.array([1.1, 1.06, 1.02, 0.98, 0.94, 0.9, 0.9, 0.94, 0.98, 1.02, 1.06, 1.1])

# Table 1d
MONTHLY_HOT_WATER_TEMPERATURE_RISE = numpy.array(
    [41.2, 41.4, 40.1, 37.6, 36.4, 33.9, 30.4, 33.4, 33.5, 36.3, 39.4, 39.9])

# Table 2
def hw_storage_loss_factor(dwelling):
    if dwelling.hw_cylinder_insulation_type == sap_worksheet.CylinderInsulationTypes.FOAM:
        return 0.005 + 0.55 / (dwelling.hw_cylinder_insulation + 4)
    else:
        return 0.005 + 1.76 / (dwelling.hw_cylinder_insulation + 12.8)


# Table 2a
def hw_volume_factor(cylinder_volume):
    return (120. / cylinder_volume) ** (1. / 3.)


# Table 2b
def constant(k):
    return lambda d: k


def cylinder_indirect(d):
    temperature_factor = 0.6
    if true_and_not_missing(d, 'has_hw_time_control'):
        temperature_factor = temperature_factor * 0.9
    if not d.has_cylinderstat:
        temperature_factor = temperature_factor * 1.3

    return temperature_factor


def cpsu_store(d):
    if hasattr(d, 'measured_cylinder_loss'):
        temperature_factor = .89
    else:
        temperature_factor = 1.08

    if true_and_not_missing(d, 'has_hw_time_control'):
        temperature_factor = temperature_factor * 0.81

    # Check airing cupboard
    if true_and_not_missing(d.water_sys, 'cpsu_not_in_airing_cupboard'):
        #!!! Actually this is if cpsu or thermal store not in airing cupboard
        temperature_factor = temperature_factor * 1.1

    return temperature_factor


def elec_cpsu_store(d):
    if hasattr(d, 'measured_cylinder_loss'):
        return 1.09 + 0.012 * (d.water_sys.cpsu_Tw - 85)
    else:
        return 1


def storage_combi_primary(d):
    return (.82
            if d.hw_cylinder_volume >= 115
            else .82 + 0.0022 * (115 - d.hw_cylinder_volume))


def storage_combi_secondary_store(d):
    return (.6
            if d.hw_cylinder_volume >= 115
            else .6 + 0.0016 * (115 - d.hw_cylinder_volume))


class ThermalStoreTypes(object):
    HW_ONLY = 1
    INTEGRATED = 2


TABLE_2b_manuf = {
    1: constant(0.6),
    2: cylinder_indirect,
    3: 0,
    4: storage_combi_secondary_store,
    5: cylinder_indirect,  # same equations as indirect cylinder
    6: cpsu_store,
    7: cpsu_store,
    8: elec_cpsu_store,
    9: constant(1),
}
TABLE_2b_table2 = {
    1: constant(0.6),
    2: cylinder_indirect,
    3: storage_combi_primary,
    4: storage_combi_secondary_store,
    5: cylinder_indirect,  # same equations as indirect cylinder,
    6: cpsu_store,
    7: cpsu_store,
    8: elec_cpsu_store,
    9: constant(1),
}


def hw_temperature_factor(dwelling, measured_loss):
    table2b = TABLE_2b_manuf if measured_loss else TABLE_2b_table2
    return table2b[dwelling.water_sys.table2brow](dwelling)

# Table 3
TABLE_3 = {
    1: constant(0),
    2: constant(1220),
    3: constant(610),
    4: 0,
    5: constant(360),
    6: constant(0),
    7: constant(0),
    8: constant(0),
    9: 0,
    10: constant(280),  # !!! Different for insulated/not insulated pipework
    11: 0,
    12: constant(360),
}


def getTable3Row(dwelling):
    if dwelling.water_heating_type_code == 901:
        # !!! Also need to do this for second main system?

        # Water heating with main
        if dwelling.main_sys_1.system_type == HeatingSystem.TYPES.cpsu:
            return 7
        if (hasattr(dwelling, 'main_heating_type_code') and
                    dwelling.main_heating_type_code == 191):
            return 1

    if dwelling.water_sys.system_type in [HeatingSystem.TYPES.combi,
                                          HeatingSystem.TYPES.storage_combi]:
        return 6
    elif dwelling.water_heating_type_code == 903:
        # Immersion
        return 1
    elif dwelling.community_heating_dhw:
        # Community heating
        return 12
    elif true_and_not_missing(dwelling, 'cylinder_is_thermal_store'):
        # !!! Need to check length of pipework here and insulation
        return 10
    elif (dwelling.water_sys.system_type in [HeatingSystem.TYPES.pcdf_heat_pump,
                                             HeatingSystem.TYPES.microchp]
          and dwelling.water_sys.has_integral_store):
        return 8
    elif dwelling.has_hw_cylinder:
        # Cylinder !!! Cylinderstat should be assumed to be present
        # for CPSU, electric immersion, etc - see 9.3.7
        if dwelling.has_cylinderstat and dwelling.primary_pipework_insulated:
            return 5
        elif dwelling.has_cylinderstat or dwelling.primary_pipework_insulated:
            return 3  # row 4 is the same
        else:
            return 2
    else:
        # Must be combi? 
        raise Exception("WTF?")  # !!!
        #return 6


def hw_primary_circuit_loss(dwelling):
    table3row = getTable3Row(dwelling)
    return TABLE_3[table3row](dwelling)


# Table 3a
# !!! Need to add the other options in here
def combi_loss_instant_without_keep_hot(daily_hot_water_use):
    fn = numpy.where(daily_hot_water_use > 100,
                     1.0,
                     daily_hot_water_use / 100)
    return 600. * fn


def combi_loss_instant_with_timed_heat_hot(_daily_hot_water_use):
    return 600.


def combi_loss_instant_with_untimed_heat_hot(_daily_hot_water_use):
    return 900.


def combi_loss_storage_combi_more_than_55l(_daily_hot_water_use):
    return 0


def combi_loss_storage_combi_less_than_55l(Vc, daily_hot_water_use):
    fn = numpy.where(daily_hot_water_use > 100,
                     1.0,
                     daily_hot_water_use / 100)
    return (600 - (Vc - 15) * 15) * fn


def combi_loss_table_3a(dwelling, system):
    storage_volume = (dwelling.hw_cylinder_volume
                      if hasattr(dwelling, 'hw_cylinder_volume') else 0)
    if storage_volume == 0:
        if hasattr(system, "table3arow"):
            return system.table3arow
        else:
            # !!! Need other keep hot types
            return combi_loss_instant_without_keep_hot
    elif storage_volume < 55:
        return lambda hw_use: combi_loss_storage_combi_less_than_55l(dwelling.hw_cylinder_volume, hw_use)
    else:
        return combi_loss_storage_combi_more_than_55l


# !!! Need to complete this table
def combi_loss_table_3b(pcdf_data):
    # !!! Need to set storage loss here
    #dwelling.measured_cylinder_loss=0#pcdf_data['storage_loss_factor_f1']
    #dwelling.has_hw_cylinder=True
    #system.table2brow=5
    #dwelling.has_cylinderstat=True
    return lambda x: 365 * pcdf_data['storage_loss_factor_f1']


# !!! Need to complete this table
def combi_loss_table_3c():
    return None

# Table 4a
# !!! Electric storage systems - offpeak and 24 hour tariff systems
# have same type codes!

USE_TABLE_4D_FOR_RESPONSIVENESS = -99


def translate_4a_row(systems, row):
    if row[6] != 'n/a':
        sys = dict(
            code=int(row[0]),
            #type=row[1],
            effy=float_or_zero(row[2]),
            effy_hetas=float_or_zero(row[3]),
            effy_gas=float_or_zero(row[4]),
            effy_lpg=float_or_zero(row[5]),
            responsiveness=(float(row[6])
                            if row[6] != 'emitter'
                            else USE_TABLE_4D_FOR_RESPONSIVENESS),
            table2brow=int(row[7]) if row[7] != '' else -1,
            fraction_of_heat_from_secondary=float(row[8]),
            flue_fan=row[9],
            warm_air_fan=row[10],
            water_effy=row[11])
    else:
        # HW system
        sys = dict(
            code=int(row[0]),
            type=row[1],
            effy=float(row[2]),
            table2brow=int(row[7]) if row[7] != '' else -1)

    if sys['code'] in systems:
        systems[sys['code']].append(sys)
    else:
        systems[sys['code']] = [sys, ]


TABLE_4A = csv_to_dict(DATA_FILE_LOCATION + 'table_4a.csv', translate_4a_row)


def get_4a_system(dwelling, code):
    matches = TABLE_4A[code]
    if len(matches) > 1:
        assert len(matches) == 2
        # Electric storage heaters appear twice with the same code -
        # once for off peak, once for 24 hour tariffs.
        if dwelling.electricity_tariff == ELECTRICITY_24HR:
            return matches[1]
        else:
            assert (dwelling.electricity_tariff == ELECTRICITY_10HR or
                    dwelling.electricity_tariff == ELECTRICITY_7HR)
            return matches[0]
    else:
        return matches[0]


def get_effy(system_data, fuel):
    if system_data['effy'] > 0:
        return system_data['effy']
    elif system_data['effy_gas'] > 0:
        if fuel.is_mains_gas:
            return system_data['effy_gas']
        else:  #if fuel in [BULK_LPG, BOTTLED_LPG, LPG_COND18]:
            # Should be LPG fuel if we get here, but do this assertion
            # check anyway which will catch everything apart from LNG
            assert fuel.type == FuelTypes.GAS
            return system_data['effy_lpg']

    raise ValueError("Input error if we get here?")


def has_ch_pump(dwelling):
    return (hasattr(dwelling, 'heating_emitter_type') or
            (hasattr(dwelling, 'heating_emitter_type2') and
             not dwelling.heating_emitter_type2 is None))


def system_type_from_sap_code(system_code, system_data):
    if ('boiler_type' in system_data and
                system_data['boiler_type'] == BOILER_TYPES['COMBI']):
        return HeatingSystem.TYPES.combi
    elif is_cpsu(system_code):
        return HeatingSystem.TYPES.cpsu
    elif is_off_peak_only_system(system_code):
        return HeatingSystem.TYPES.off_peak_only
    elif is_integrated_system(system_code):
        return HeatingSystem.TYPES.integrated_system
    elif is_storage_heater(system_code):
        return HeatingSystem.TYPES.storage_heater
    elif is_electric_boiler(system_code):
        return HeatingSystem.TYPES.electric_boiler
    elif is_boiler(system_code):
        return HeatingSystem.TYPES.regular_boiler
    elif is_heat_pump(system_code):
        return HeatingSystem.TYPES.heat_pump
    elif is_room_heater(system_code):
        return HeatingSystem.TYPES.room_heater
    elif is_warm_air_system(system_code):
        return HeatingSystem.TYPES.warm_air
    return HeatingSystem.TYPES.misc


def get_4a_main_system(dwelling,
                       system_code,
                       fuel,
                       use_immersion_in_summer,
                       hetas_approved):
    system_data = get_4a_system(dwelling, system_code)

    if hetas_approved and system_data['effy_hetas'] > 0:
        effy = system_data["effy_hetas"]
    else:
        effy = get_effy(system_data, fuel)

    system = HeatingSystem(system_type_from_sap_code(system_code, system_data),
                           effy,
                           effy,
                           use_immersion_in_summer,
                           system_data['flue_fan'] == 'TRUE',
                           has_ch_pump(dwelling),
                           system_data['table2brow'],
                           system_data['fraction_of_heat_from_secondary'],
                           fuel)

    system.has_warm_air_fan = system_data['warm_air_fan'] == "TRUE"
    system.responsiveness = system_data['responsiveness']
    if system_data['water_effy'] != "same":
        system.water_effy = float(system_data['water_effy'])

    if system.system_type in [HeatingSystem.TYPES.combi,
                              HeatingSystem.TYPES.storage_combi]:
        system.combi_loss = combi_loss_table_3a(dwelling, system)
    elif system.system_type == HeatingSystem.TYPES.cpsu:
        system.cpsu_Tw = dwelling.cpsu_Tw
        system.cpsu_not_in_airing_cupboard = true_and_not_missing(dwelling, 'cpsu_not_in_airing_cupboard')
    return system


def get_4a_secondary_system(dwelling):
    system_data = get_4a_system(dwelling, dwelling.secondary_heating_type_code)

    if (true_and_not_missing(dwelling, 'secondary_hetas_approved') and
                system_data['effy_hetas'] > 0):
        effy = system_data["effy_hetas"]
    else:
        effy = get_effy(system_data, dwelling.secondary_sys_fuel)

    sys = SecondarySystem(
        system_type_from_sap_code(dwelling.secondary_heating_type_code,
                                  system_data),
        effy,
        (dwelling.use_immersion_heater_summer
         if hasattr(dwelling, 'use_immersion_heater_summer')
         else False))
    sys.table2brow = system_data['table2brow']
    sys.fuel = dwelling.secondary_sys_fuel

    if system_data['water_effy'] != "same" and system_data['water_effy'] != "":
        sys.water_effy = float(system_data['water_effy'])

    return sys


def get_manuf_data_secondary_system(dwelling):
    effy = dwelling.secondary_sys_manuf_effy
    sys = SecondarySystem(
        HeatingSystem.TYPES.misc,
        effy,
        (dwelling.use_immersion_heater_summer
         if hasattr(dwelling, 'use_immersion_heater_summer')
         else False))
    #sys.table2brow=system_data['table2brow']
    sys.fuel = dwelling.secondary_sys_fuel
    return sys

# Table 4b
BOILER_TYPES = dict(
    REGULAR=1,
    COMBI=2,
    CPSU=3,
    OTHER=4
)


def translate_4b_row(systems, row):
    sys = dict(
        code=int(row[0]),
        type=row[1],
        effy_winter=float(row[1]),
        effy_summer=float(row[2]),
        table2brow=int(row[3]),
        fraction_of_heat_from_secondary=.1,
        responsiveness=USE_TABLE_4D_FOR_RESPONSIVENESS,
        flue_fan=row[4],
        boiler_type=int(row[5]),
        condensing=row[6] == "TRUE",
        warm_air_fan="FALSE")
    systems[sys['code']] = sys


TABLE_4B = csv_to_dict(DATA_FILE_LOCATION + 'table_4b.csv', translate_4b_row)


def get_4b_main_system(dwelling, system_code, fuel, use_immersion_in_summer):
    system_data = TABLE_4B[system_code]
    system = HeatingSystem(system_type_from_sap_code(system_code, system_data),
                           system_data['effy_winter'],
                           system_data['effy_summer'],
                           use_immersion_in_summer,
                           system_data['flue_fan'] == 'TRUE',
                           has_ch_pump(dwelling),
                           system_data['table2brow'],
                           system_data['fraction_of_heat_from_secondary'],
                           fuel)
    system.responsiveness = system_data['responsiveness']
    system.is_condensing = system_data['condensing']
    if system.system_type in [HeatingSystem.TYPES.combi,
                              HeatingSystem.TYPES.storage_combi]:
        system.combi_loss = combi_loss_table_3a(dwelling, system)
    elif system.system_type == HeatingSystem.TYPES.cpsu:
        system.cpsu_not_in_airing_cupboard = true_and_not_missing(dwelling, 'cpsu_not_in_airing_cupboard')

    return system


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


def apply_load_compensator(sys, ctype):
    if ctype in [LoadCompensators.ENHANCED_LOAD_COMPENSATOR,
                 LoadCompensators.WEATHER_COMPENSATOR]:
        if sys.fuel.is_mains_gas:
            sys.space_adj += 3
        else:
            sys.space_adj += 1.5


def apply_4c1(dwelling, sys, load_compensator):
    if not true_and_not_missing(sys, "is_condensing"):
        return  # no corrections apply

    if (sys is dwelling.water_sys and
            hasattr(dwelling, 'fghrs') and
                dwelling.fghrs != None):
        # Can't have the effy adjustment if the system has an fghrs
        return

        # !!! Can have different emitter types for different systems
    if (dwelling.heating_emitter_type in [HeatEmitters.UNDERFLOOR_TIMBER,
                                          HeatEmitters.UNDERFLOOR_SCREED,
                                          HeatEmitters.UNDERFLOOR_CONCRETE] and
            not sys is dwelling.water_sys):
        if sys.fuel.is_mains_gas:
            sys.space_adj += 3
        else:
            sys.space_adj += 2
    elif load_compensator != None:
        apply_load_compensator(sys, load_compensator)


def apply_4c2(dwelling, sys):
    # !!! Actually not sure if these adjustments apply to solid fuel
    # !!! boilers? Case 15 suggests even solid fuel boilers without
    # !!! thermostatic control have an effy penalty.  But the
    # !!! interlock penalty is definitely just for gas and oil
    # !!! boilers.
    # - Probably answer to above question: see end of section 9.3.9

    # !!! This entire function needs to be independent of sys1/sys2!

    # !!! Need to check  main_sys_2 here as well?
    if (dwelling.main_sys_1.system_type == HeatingSystem.TYPES.cpsu or
            (hasattr(dwelling, 'thermal_store_type') and
                     dwelling.thermal_store_type == ThermalStoreTypes.INTEGRATED)):
        dwelling.temperature_adjustment -= 0.1

    # !!! Also check sys2!
    if true_and_not_missing(dwelling, "sys1_delayed_start_thermostat"):
        dwelling.temperature_adjustment -= .15

    if not sys.fuel.type in [FuelTypes.GAS,
                             FuelTypes.OIL,
                             FuelTypes.SOLID]:
        return

    apply_adjustment = False
    if not (dwelling.has_room_thermostat or dwelling.has_trvs):
        # Applies for all boilers
        apply_adjustment = True
    elif (sys.fuel.type in [FuelTypes.GAS, FuelTypes.OIL] and
              (not dwelling.sys1_has_boiler_interlock or
                   not dwelling.has_room_thermostat)):
        apply_adjustment = True
    elif (dwelling.water_sys is sys and
              hasattr(dwelling, "hwsys_has_boiler_interlock") and
              not dwelling.hwsys_has_boiler_interlock):
        apply_adjustment = True

    if apply_adjustment:
        space_heat_effy_adjustment = -5
        if not dwelling.water_sys.system_type in [HeatingSystem.TYPES.combi,
                                                  HeatingSystem.TYPES.cpsu,
                                                  HeatingSystem.TYPES.storage_combi]:
            dhw_heat_effy_adjustment = -5
        else:
            dhw_heat_effy_adjustment = 0

        # !!! These adjustments need to be applied to the correct system
        # !!! (main 1 or main 2) - also confusion with water_sys
        dwelling.main_sys_1.space_adj = space_heat_effy_adjustment
        dwelling.main_sys_1.water_adj = dhw_heat_effy_adjustment


TABLE_4C3 = {
    2301: (1.1, 1.05),
    2302: (1.1, 1.05),
    2303: (1.05, 1.05),
    2304: (1.05, 1.05),
    2307: (1.05, 1.05),
    2305: (1.05, 1.05),
    2308: (1.05, 1),
    2309: (1.05, 1),
    2310: (1.0, 1.0),
    2306: (1.0, 1.0),
    # !!! Also need DHW only systems
}


def apply_4c3(dwelling, sys):
    # !!! Assumes community heating is system 1
    # !!! Also need DHW factor
    sys.space_heat_charging_factor = TABLE_4C3[dwelling.control_type_code][0]
    sys.dhw_charging_factor = TABLE_4C3[dwelling.control_type_code][1]


T4C4_SPACE_EFFY_MULTIPLIERS = {
    HeatEmitters.RADIATORS: .7,
    # !!!Need to check for presence of load compensator! (also for the rads+underfloor cases)
    HeatEmitters.UNDERFLOOR_TIMBER: 1,
    HeatEmitters.UNDERFLOOR_SCREED: 1,
    HeatEmitters.UNDERFLOOR_CONCRETE: 1,
    HeatEmitters.RADIATORS_UNDERFLOOR_TIMBER: .7,
    HeatEmitters.RADIATORS_UNDERFLOOR_SCREED: .7,
    HeatEmitters.RADIATORS_UNDERFLOOR_CONCRETE: .7,
    HeatEmitters.FAN_COILS: .85,
}


def apply_4c4(dwelling, sys):
    # !!! Also need to check main sys 2?
    e = dwelling.heating_emitter_type
    dwelling.main_sys_1.space_mult = T4C4_SPACE_EFFY_MULTIPLIERS[e]

    if (dwelling.main_sys_1.space_mult == .7 and
            hasattr(dwelling, "sys1_load_compensator") and
                dwelling.sys1_load_compensator in [
                LoadCompensators.ENHANCED_LOAD_COMPENSATOR,
                LoadCompensators.WEATHER_COMPENSATOR]):
        dwelling.main_sys_1.space_mult = .75

    if dwelling.water_sys is sys:
        #!!! This assumes it supplies all of the DHW - also need the 50% case
        dwelling.water_sys.water_mult = .7

# Table 4d
TABLE_4d = {
    HeatEmitters.RADIATORS: 1,
    HeatEmitters.UNDERFLOOR_TIMBER: 1,
    HeatEmitters.UNDERFLOOR_SCREED: .75,
    HeatEmitters.UNDERFLOOR_CONCRETE: .25,
    HeatEmitters.RADIATORS_UNDERFLOOR_TIMBER: 1,
    HeatEmitters.RADIATORS_UNDERFLOOR_SCREED: .75,
    HeatEmitters.RADIATORS_UNDERFLOOR_CONCRETE: .25,
    HeatEmitters.FAN_COILS: 1,
}

# Table 4e
def translate_4e_row(controls, row):
    other_adjustments_str = row[5]
    if other_adjustments_str != "n/a":
        table_no = re.match(r'Table 4c\((\d)\)', other_adjustments_str)
        other_adj_table = globals()['apply_4c%s' % (table_no.group(1),)]
    else:
        other_adj_table = None

    control = dict(
        code=int(row[0]),
        control_type=int(row[1]),
        Tadjustment=float(row[2]),
        thermostat=row[3],
        trv=row[4],
        other_adj_table=other_adj_table,
        description=row[6])

    controls[control['code']] = control


TABLE_4E = csv_to_dict(DATA_FILE_LOCATION + 'table_4e.csv', translate_4e_row)

# Table 4f
def has_oil_pump(dwelling):
    return (dwelling.main_sys_1.has_oil_pump or
            (hasattr(dwelling, 'main_sys_2') and
             dwelling.main_heating_2_fraction > 0 and
             dwelling.main_sys_2.has_oil_pump))


def heating_fans_and_pumps_electricity(dwelling):
    Qfansandpumps = 0
    if (dwelling.main_sys_1.has_ch_pump or
            (hasattr(dwelling, 'main_sys_2') and
                 dwelling.main_sys_2.has_ch_pump)):
        if dwelling.has_room_thermostat:
            Qfansandpumps += 130
        else:
            Qfansandpumps += 130 * 1.3

    if has_oil_pump(dwelling):
        if dwelling.has_room_thermostat:
            Qfansandpumps += 100
        else:
            #raise RuntimeError("!!! DO WE EVER GET HERE?")
            Qfansandpumps += 100 * 1.3

    if dwelling.main_sys_1.has_flue_fan:
        Qfansandpumps += 45

    if (hasattr(dwelling, 'main_sys_2') and
            dwelling.main_sys_2.has_flue_fan and
                dwelling.main_heating_2_fraction > 0):
        Qfansandpumps += 45

    if dwelling.main_sys_1.has_warm_air_fan or (
                    hasattr(dwelling, 'main_sys_2') and
                    dwelling.main_sys_2.has_warm_air_fan and
                    dwelling.main_heating_2_fraction > 0):
        if not dwelling.ventilation_type in [VentilationTypes.MVHR,
                                             VentilationTypes.MV]:
            Qfansandpumps += 0.6 * dwelling.volume
        else:
            # Warm air fan elec not included for MVHR/MV
            pass

    # Keep hot only applies for water sys?  What if you have a combi
    # boiler but it's not providing hw? No need for keep hot?  Or
    # maybe it's just not a combi boiler in that case?
    if hasattr(dwelling.water_sys, "keep_hot_elec_consumption"):
        Qfansandpumps += dwelling.water_sys.keep_hot_elec_consumption

    if true_and_not_missing(dwelling,
                            'has_electric_shw_pump'):
        Qfansandpumps += 75

    return Qfansandpumps


def mech_vent_fans_electricity(dwelling):
    Qfansandpumps = 0
    if dwelling.ventilation_type in [VentilationTypes.MEV_CENTRALISED,
                                     VentilationTypes.MEV_DECENTRALISED,
                                     VentilationTypes.MV,
                                     VentilationTypes.PIV_FROM_OUTSIDE]:
        Qfansandpumps += 1.22 * dwelling.volume * dwelling.adjusted_fan_sfp
    elif dwelling.ventilation_type == VentilationTypes.MVHR:
        nmech = 0.5
        Qfansandpumps += 2.44 * dwelling.volume * nmech * dwelling.adjusted_fan_sfp
    return Qfansandpumps


def fans_and_pumps_electricity(dwelling):
    dwelling.Q_fans_and_pumps = heating_fans_and_pumps_electricity(dwelling)
    dwelling.Q_mech_vent_fans = mech_vent_fans_electricity(dwelling)

# Table 4h
from .pcdf import DuctTypes
from .pcdf import VentilationTypes

# Lazy load these, to give a chance to swap the pcdf database file if necessary
TABLE_4h_in_use = None
TABLE_4h_in_use_approved_scheme = None
TABLE_4h_hr_effy_approved_scheme = None


def load_4h_tables():
    global TABLE_4h_in_use, TABLE_4h_in_use_approved_scheme, TABLE_4h_hr_effy, TABLE_4h_hr_effy_approved_scheme

    (TABLE_4h_in_use,
     TABLE_4h_in_use_approved_scheme,
     TABLE_4h_hr_effy,
     TABLE_4h_hr_effy_approved_scheme
     ) = pcdf.get_in_use_factors()


def get_in_use_factor(vent_type, duct_type, approved_scheme):
    if TABLE_4h_in_use is None:
        load_4h_tables()
    if approved_scheme:
        return TABLE_4h_in_use_approved_scheme[vent_type][duct_type]
    else:
        return TABLE_4h_in_use[vent_type][duct_type]


def get_in_use_factor_hr(vent_type, duct_type, approved_scheme):
    if TABLE_4h_in_use is None:
        load_4h_tables()
    if approved_scheme:
        return TABLE_4h_hr_effy_approved_scheme[vent_type][duct_type]
    else:
        return TABLE_4h_hr_effy[vent_type][duct_type]


def default_in_use_factor():
    return 2.5


def default_hr_effy_factor():
    return 0.7


# Table 5a
# !!! NEED TO FINISH THIS!
def has_oil_pump_inside(dwelling):
    return (
        true_and_not_missing(dwelling, 'main_heating_oil_pump_inside_dwelling')
        or
        true_and_not_missing(dwelling, 'main_heating_2_oil_pump_inside_dwelling'))


def fans_and_pumps_gain(dwelling):
    fansandpumps_gain = 0
    gain_due_to_heating_system = 0

    # !!! Nope, this is for balanced without heat recovery
    #if dwelling.ventilation_type==VentilationTypes.MVHR:
    #    fansandpumps_gain+=dwelling.adjusted_fan_sfp*0.06*dwelling.volume

    ch_pump_gain = (0
                    if (hasattr(dwelling, 'central_heating_pump_in_heated_space')
                        and not dwelling.central_heating_pump_in_heated_space)
                    else 10)
    if (dwelling.main_sys_1.has_ch_pump or
            (hasattr(dwelling, 'main_sys_2') and dwelling.main_sys_2.has_ch_pump)):
        fansandpumps_gain += ch_pump_gain
        gain_due_to_heating_system += ch_pump_gain

    if has_oil_pump_inside(dwelling):
        fansandpumps_gain += 10
        gain_due_to_heating_system += 10
    if true_and_not_missing(dwelling,
                            'has_fans_for_positive_input_vent_from_outside'):
        assert (False)
    if true_and_not_missing(dwelling,
                            'has_fans_for_balanced_mech_vent_without_hr'):
        assert (False)

    if not dwelling.ventilation_type in [VentilationTypes.MVHR,
                                         VentilationTypes.MV]:
        if dwelling.main_sys_1.has_warm_air_fan or (
                        hasattr(dwelling, 'main_sys_2') and
                        dwelling.main_sys_2.has_warm_air_fan and
                        dwelling.main_heating_2_fraction > 0):
            fansandpumps_gain += 0.06 * dwelling.volume

    if dwelling.ventilation_type == VentilationTypes.MV:
        fansandpumps_gain += dwelling.adjusted_fan_sfp * .06 * dwelling.volume
    elif dwelling.ventilation_type == VentilationTypes.PIV_FROM_OUTSIDE:
        fansandpumps_gain += dwelling.adjusted_fan_sfp * .12 * dwelling.volume

    dwelling.pump_gain = fansandpumps_gain
    dwelling.heating_system_pump_gain = gain_due_to_heating_system


# Table 6d
class OvershadingTypes(object):
    HEAVY = 0
    MORE_THAN_AVERAGE = 1
    AVERAGE = 2
    VERY_LITTLE = 3


TABLE_6D = {
    OvershadingTypes.HEAVY: dict(
        solar_access_factor_winter=.3,
        solar_access_factor_summer=.5,
        light_access_factor=.5),
    OvershadingTypes.MORE_THAN_AVERAGE: dict(
        solar_access_factor_winter=.54,
        solar_access_factor_summer=.7,
        light_access_factor=.67),
    OvershadingTypes.AVERAGE: dict(
        solar_access_factor_winter=.77,
        solar_access_factor_summer=.9,
        light_access_factor=.83),
    OvershadingTypes.VERY_LITTLE: dict(
        solar_access_factor_winter=1,
        solar_access_factor_summer=1,
        light_access_factor=1),
}

# Table 10
def translate_10_row(regions, row):
    climate_data = dict(
        code=int(row[0]),
        name=row[1],
        latitude=float(row[2]),
        solar_radiation=summer_to_annual(row[3:6]),
        external_temperature=summer_to_annual(row[6:9]))

    regions[climate_data['code']] = climate_data


def summer_to_annual(summer_vals):
    return numpy.array([0, ] * 5 + [float(s) for s in summer_vals] + [0, ] * 4)


TABLE_10 = csv_to_dict(DATA_FILE_LOCATION + 'table_10.csv', translate_10_row)

# Table 10c
def translate_10c_row(systems, row):
    system = dict(
        energy_label=row[0],
        split_sys_eer=float(row[1]),
        packaged_sys_eer=float(row[2]))
    systems[system['energy_label']] = system


TABLE_10C = csv_to_dict(DATA_FILE_LOCATION + 'table_10c.csv', translate_10c_row)


def appendix_f_cpsu_on_peak(sys, dwelling):
    """
    39m=dwelling.h
    45m=hw_energy_content
    93m=Tmean
    95m=useful gains
    98m=Q_required"""

    Vcs = dwelling.hw_cylinder_volume
    Tw = dwelling.water_sys.cpsu_Tw
    Cmax = .1456 * Vcs * (Tw - 48)
    nm = sap_worksheet.DAYS_PER_MONTH
    Tmin = (
           (dwelling.h * dwelling.heat_calc_results['Tmean']) - Cmax + (1000 * dwelling.hw_energy_content / (24 * nm)) -
           dwelling.heat_calc_results['useful_gain']) / dwelling.h

    Text = dwelling.Texternal_heating
    Eonpeak = numpy.where(
        Tmin - Text == 0,
        0.024 * dwelling.h * nm,
        (0.024 * dwelling.h * nm * (Tmin - Text)) / (1 - numpy.exp(-(Tmin - Text))))

    F = Eonpeak / (dwelling.hw_energy_content + dwelling.Q_required)
    for i in range(5, 9):
        F[i] = 0
    return F


# Table 12a
def dhw_on_peak_fraction(water_sys, dwelling):
    # !!! Need to complete this table
    if water_sys.system_type == HeatingSystem.TYPES.cpsu:
        return appendix_f_cpsu_on_peak(water_sys, dwelling)
    elif water_sys.system_type == HeatingSystem.TYPES.heat_pump:
        # !!! Need off-peak immersion option
        return .7
    elif water_sys.system_type in [HeatingSystem.TYPES.pcdf_heat_pump,
                                   HeatingSystem.TYPES.microchp]:
        return .7
    else:
        return water_sys.fuel.general_elec_on_peak_fraction


def space_heat_on_peak_fraction(sys, dwelling):
    if sys.system_type == HeatingSystem.TYPES.off_peak_only:
        return 0
    elif sys.system_type == HeatingSystem.TYPES.integrated_system:
        assert sys.fuel == ELECTRICITY_7HR
        return .2
    elif sys.system_type == HeatingSystem.TYPES.storage_heater:
        return 0
    elif sys.system_type == HeatingSystem.TYPES.cpsu:
        return appendix_f_cpsu_on_peak(sys, dwelling)
    elif sys.system_type == HeatingSystem.TYPES.electric_boiler:
        if sys.fuel == ELECTRICITY_7HR:
            return 0.9
        elif sys.fuel == ELECTRICITY_10HR:
            return .5
        else:
            return 1
    elif sys.system_type in [HeatingSystem.TYPES.pcdf_heat_pump,
                             HeatingSystem.TYPES.microchp]:
        return .8
    elif sys.system_type == HeatingSystem.TYPES.heat_pump:
        return 0.6
    # !!! underfloor heating
    # !!! ground source heat pump
    # !!! air source heat pump
    # !!! other direct acting heating (incl secondary)
    else:
        if sys.fuel == ELECTRICITY_10HR:
            return .5
        else:
            return 1


# Table 13
def immersion_on_peak_fraction(N_occ,
                               elec_tariff,
                               cylinder_volume,
                               immersion_type):
    if elec_tariff == ELECTRICITY_7HR:
        if immersion_type == ImmersionTypes.SINGLE:
            return max(0, ((14530 - 762 * N_occ) / (cylinder_volume) - 80 + 10 * N_occ) / 100)
        else:
            assert immersion_type == ImmersionTypes.DUAL
            return max(0, ((6.8 - 0.024 * cylinder_volume) * N_occ + 14 - 0.07 * cylinder_volume) / 100)
    elif elec_tariff == ELECTRICITY_10HR:
        if immersion_type == ImmersionTypes.SINGLE:
            return max(0, ((14530 - 762 * N_occ) / (1.5 * cylinder_volume) - 80 + 10 * N_occ) / 100)
        else:
            assert immersion_type == ImmersionTypes.DUAL
            return max(0, ((6.8 - 0.036 * cylinder_volume) * N_occ + 14 - 0.105 * cylinder_volume) / 100)
    else:
        return 1


# Table H1
class SHWCollectorTypes(object):
    EVACUATED_TUBE = 1
    FLAT_PLATE_GLAZED = 2
    UNGLAZED = 3


TABLE_H1 = {
    SHWCollectorTypes.EVACUATED_TUBE: [0.6, 3, .72],
    SHWCollectorTypes.FLAT_PLATE_GLAZED: [0.75, 6, .9],
    SHWCollectorTypes.UNGLAZED: [0.9, 20, 1],
}

# Table H2
TABLE_H2 = {
    # !!! Needs finishing
    "Horizontal": 961,
    30: {
        0: 730,
        45: 785,
        90: 913,
        135: 1027,
        180: 1073,
        225: 1027,
        270: 913,
        315: 785,
    },
    45: {
        0: 640,
        45: 686,
        90: 854,
        135: 997,
        180: 1054,
        225: 997,
        270: 854,
        315: 686,
    },
    60: {
        0: 500,
        45: 597,
        90: 776,
        135: 927,
        180: 989,
        225: 927,
        270: 776,
        315: 597,
    },
    "Vertical": {
        0: 371,
        45: 440,
        90: 582,
        135: 705,
        180: 746,
        225: 705,
        270: 582,
        315: 440,
    },
}

TABLE_H3 = {
    "Horizontal": numpy.array([0.24, 0.50, 0.86, 1.37, 1.74, 1.84, 1.78, 1.50, 1.06, 0.63, 0.31, 0.19]),
    30: numpy.array([0.35, 0.63, 0.92, 1.30, 1.58, 1.68, 1.62, 1.39, 1.08, 0.74, 0.43, 0.29]),
    45: numpy.array([0.39, 0.69, 0.95, 1.27, 1.52, 1.61, 1.55, 1.34, 1.08, 0.79, 0.48, 0.33]),
    60: numpy.array([0.44, 0.74, 0.97, 1.24, 1.45, 1.54, 1.48, 1.30, 1.09, 0.84, 0.53, 0.37]),
    "Vertical": numpy.array([0.58, 0.92, 1.05, 1.15, 1.25, 1.33, 1.28, 1.15, 1.10, 0.99, 0.69, 0.50]),
}

# Table H4
TABLE_H4 = {
    PVOvershading.HEAVY: .5,
    PVOvershading.SIGNIFICANT: .65,
    PVOvershading.MODEST: .8,
    PVOvershading.NONE_OR_VERY_LITTLE: 1,
}

TABLE_H5 = [1.0, 1.0, 0.94, 0.70, 0.45, 0.44, 0.44, 0.48, 0.76, 0.94, 1.0, 1.0]

TABLE_M1 = {
    TerrainTypes.DENSE_URBAN: {
        10: .56,
        5: .51,
        2: .4,
        0: .28,
    },
    TerrainTypes.SUBURBAN: {
        6: .67,
        4: .61,
        2: .53,
        0: .39,
    },
    TerrainTypes.RURAL: {
        12: 1,
        7: .94,
        2: .86,
        0: .82,
    },
}


def get_M1_correction_factor(terrain_type, wind_speed):
    interpolation_vals = TABLE_M1[terrain_type]

    closest_above = 999
    closest_below = 0

    for k in list(interpolation_vals.keys()):
        if k >= wind_speed and k < closest_above:
            closest_above = k
        if k <= wind_speed and k > closest_below:
            closest_below = k

    if closest_above == 999:
        # Outside of range, return largest
        return interpolation_vals[closest_below]
    elif closest_above == closest_below:
        return interpolation_vals[closest_below]
    else:
        v1 = interpolation_vals[closest_below]
        v2 = interpolation_vals[closest_above]
        return v1 + (v2 - v1) * (wind_speed - closest_below) / (closest_above - closest_below)


def configure_ventilation(dwelling):
    if dwelling.ventilation_type == VentilationTypes.MEV_CENTRALISED:
        if hasattr(dwelling, 'mev_sfp'):
            sfp = dwelling.mev_sfp
            in_use_factor = get_in_use_factor(dwelling.ventilation_type, dwelling.mv_ducttype,
                                              true_and_not_missing(dwelling, 'mv_approved'))
        else:
            sfp = 0.8  # Table 4g
            in_use_factor = default_in_use_factor()
        dwelling.adjusted_fan_sfp = sfp * in_use_factor
        if true_and_not_missing(dwelling, 'mv_approved'):
            assert False
    elif dwelling.ventilation_type == VentilationTypes.MEV_DECENTRALISED:
        if hasattr(dwelling, 'mev_sys_pcdf_id'):
            sys = pcdf.get_mev_system(dwelling.mev_sys_pcdf_id)
            get_sfp = lambda configuration: sys['configs'][configuration]['sfp']
        else:
            get_sfp = lambda configuration: getattr(dwelling, "mev_fan_" + configuration + "_sfp")

        total_flow = 0
        sfp_sum = 0

        for location in ['room', 'duct', 'wall']:
            this_duct_type = (DuctTypes.NONE
                              if location == 'wall'
                              else dwelling.mv_ducttype)
            for fantype in ['kitchen', 'other']:
                configuration = location + '_' + fantype
                countattr = 'mev_fan_' + configuration + '_count'
                if hasattr(dwelling, countattr):
                    count = getattr(dwelling, countattr)
                    sfp = get_sfp(configuration)
                    in_use_factor = get_in_use_factor(dwelling.ventilation_type,
                                                      this_duct_type,
                                                      true_and_not_missing(dwelling, 'mv_approved'))
                    flowrate = 13 if fantype == 'kitchen' else 8
                    sfp_sum += sfp * count * flowrate * in_use_factor
                    total_flow += flowrate * count

        if total_flow > 0:
            dwelling.adjusted_fan_sfp = sfp_sum / total_flow
        else:
            in_use_factor = default_in_use_factor()
            sfp = 0.8  # Table 4g
            dwelling.adjusted_fan_sfp = sfp * in_use_factor

    elif dwelling.ventilation_type == VentilationTypes.MVHR:
        if hasattr(dwelling, 'mvhr_sfp'):
            in_use_factor = get_in_use_factor(dwelling.ventilation_type,
                                              dwelling.mv_ducttype,
                                              true_and_not_missing(dwelling, 'mv_approved'))
            in_use_factor_hr = get_in_use_factor_hr(dwelling.
                                                    ventilation_type,
                                                    dwelling.mv_ducttype,
                                                    true_and_not_missing(dwelling, 'mv_approved'))
        else:
            dwelling.mvhr_sfp = 2  # Table 4g
            dwelling.mvhr_effy = 66  # Table 4g

            in_use_factor = default_in_use_factor()
            in_use_factor_hr = default_hr_effy_factor()

            if true_and_not_missing(dwelling, 'mv_approved'):
                assert False

        dwelling.adjusted_fan_sfp = dwelling.mvhr_sfp * in_use_factor
        dwelling.mvhr_effy = dwelling.mvhr_effy * in_use_factor_hr
    elif dwelling.ventilation_type == VentilationTypes.MV:
        if hasattr(dwelling, 'mv_sfp'):
            mv_sfp = dwelling.mv_sfp
            in_use_factor = get_in_use_factor(dwelling.ventilation_type, dwelling.mv_ducttype,
                                              true_and_not_missing(dwelling, 'mv_approved'))
        else:
            mv_sfp = 2  # Table 4g
            in_use_factor = default_in_use_factor()
        dwelling.adjusted_fan_sfp = mv_sfp * in_use_factor
    elif dwelling.ventilation_type == VentilationTypes.PIV_FROM_OUTSIDE:
        if hasattr(dwelling, 'piv_sfp'):
            piv_sfp = dwelling.piv_sfp
            in_use_factor = get_in_use_factor(dwelling.ventilation_type, dwelling.mv_ducttype,
                                              true_and_not_missing(dwelling, 'mv_approved'))
        else:
            piv_sfp = 0.8  # Table 4g
            in_use_factor = default_in_use_factor()
        dwelling.adjusted_fan_sfp = piv_sfp * in_use_factor


def enum(**enums):
    return type('Enum', (), enums)


def is_cpsu(type_code):
    return (type_code >= 120 and type_code <= 123) or type_code == 192


def is_storage_heater(type_code):
    return type_code >= 401 and type_code <= 407  #(408 is an integrated system)


def is_off_peak_only_system(type_code):
    return type_code == 421 or type_code == 515


def is_integrated_system(type_code):
    return type_code in [408, 422, 423]


def is_electric_boiler(type_code):
    return type_code >= 191 and type_code <= 196


def is_boiler(type_code):
    return type_code < 200


def is_heat_pump(type_code):
    return ((type_code >= 201 and type_code <= 207) or
            (type_code >= 521 and type_code <= 527))


def is_room_heater(type_code):
    return type_code >= 601 and type_code <= 694


def is_warm_air_system(type_code):
    # Note overlap with heat pumps 
    return type_code >= 501 and type_code <= 527


def heating_fuel_cost(sys, dwelling):
    if sys.fuel.is_electric:
        on_peak = space_heat_on_peak_fraction(sys, dwelling)
        return sys.fuel.unit_price(on_peak)
    else:
        return sys.fuel.unit_price()


def dhw_fuel_cost(dwelling):
    if dwelling.water_sys.fuel.is_electric and hasattr(dwelling,
                                                       'immersion_type') and not dwelling.immersion_type is None:
        # !!! Are there other places that should use non-solar cylinder volume?
        non_solar_cylinder_volume = dwelling.hw_cylinder_volume - (
            dwelling.solar_dedicated_storage_volume
            if hasattr(dwelling, 'solar_dedicated_storage_volume')
            else 0)
        on_peak = immersion_on_peak_fraction(dwelling.Nocc,
                                             dwelling.electricity_tariff,
                                             non_solar_cylinder_volume,
                                             dwelling.immersion_type)
        return dwelling.water_sys.fuel.unit_price(on_peak)
    elif dwelling.water_sys.fuel.is_electric:
        on_peak = dhw_on_peak_fraction(dwelling.water_sys, dwelling)
        return dwelling.water_sys.fuel.unit_price(on_peak)
    else:
        return dwelling.water_sys.fuel.unit_price()


def weighted_effy(Q_space, Q_water, wintereff, summereff):
    # If there is no space or water demand then divisor will be
    # zero
    water_effy = numpy.zeros(12)
    divisor = Q_space / wintereff + Q_water / summereff
    for i in range(12):
        if divisor[i] != 0:
            water_effy[i] = (Q_space[i] + Q_water[i]) / divisor[i]
        else:
            water_effy[i] = 100
    return water_effy


class HeatingSystem(object):
    TYPES = enum(misc=0,
                 regular_boiler=6,
                 combi=1,
                 storage_combi=13,
                 cpsu=2,
                 electric_boiler=5,
                 storage_heater=3,
                 integrated_system=4,
                 heat_pump=7,
                 room_heater=8,
                 warm_air=9,
                 off_peak_only=10,
                 pcdf_heat_pump=11,
                 microchp=14,
                 community=12)

    def __init__(self, system_type,
                 winter_effy,
                 summer_effy,
                 summer_immersion,
                 has_flue_fan,
                 has_ch_pump,
                 table2brow,
                 default_secondary_fraction,
                 fuel):
        self.system_type = system_type

        self.heating_effy_winter = winter_effy
        self.heating_effy_summer = summer_effy
        self.summer_immersion = summer_immersion
        self.table2brow = table2brow
        self.default_secondary_fraction = default_secondary_fraction

        self.has_flue_fan = has_flue_fan
        self.has_ch_pump = has_ch_pump
        self.has_warm_air_fan = False

        self.has_oil_pump = (fuel.type == FuelTypes.OIL and
                             system_type in [self.TYPES.regular_boiler,
                                             self.TYPES.combi,
                                             self.TYPES.storage_combi])

        self.fuel = fuel

        # These may be changed after init
        self.space_mult = 1
        self.space_adj = 0
        self.water_mult = 1
        self.water_adj = 0

        self.is_community_heating = False

    def space_heat_effy(self, Q_space):
        self.Q_space = Q_space
        return (self.heating_effy_winter + self.space_adj) * self.space_mult

    def water_heat_effy(self, Q_water):
        if hasattr(self, 'water_effy'):
            # Override for systems like gas warm air system with circulator
            return self.water_effy

        """
        base_water_effy=(self.Q_space+Q_water)/(self.Q_space/self.heating_effy_winter+Q_water/self.heating_effy_summer)
        water_effy=(base_water_effy+self.water_adj)*self.water_mult
        """
        # Looks like you apply effy adjustments before calculating the
        # seasonal weight efficiency, but which adjustments do you use
        # for winter?  Space or water heating?
        wintereff = (self.heating_effy_winter + self.water_adj) * self.water_mult
        summereff = (self.heating_effy_summer + self.water_adj) * self.water_mult

        water_effy = weighted_effy(self.Q_space, Q_water, wintereff, summereff)
        if self.summer_immersion:
            for i in range(5, 9):
                water_effy[i] = 100

        return water_effy

    def fuel_price(self, dwelling):
        return heating_fuel_cost(self, dwelling)

    def co2_factor(self):
        return self.fuel.co2_factor

    def primary_energy_factor(self):
        return self.fuel.primary_energy_factor

    def water_fuel_price(self, dwelling):
        return dhw_fuel_cost(dwelling)


class SecondarySystem(object):
    def __init__(self, system_type, effy, summer_immersion):
        self.effy = effy
        self.summer_immersion = summer_immersion
        self.system_type = system_type
        self.is_community_heating = False

    def space_heat_effy(self, _Q_space):
        return self.effy

    def water_heat_effy(self, _Q_water):
        if hasattr(self, 'water_effy'):
            # Override for systems like gas warm air system with circulator
            return self.water_effy
        water_effy = [self.effy, ] * 12
        if self.summer_immersion:
            for i in range(5, 9):
                water_effy[i] = 100

        return water_effy

    def fuel_price(self, dwelling):
        return heating_fuel_cost(self, dwelling)

    def co2_factor(self):
        return self.fuel.co2_factor

    def primary_energy_factor(self):
        return self.fuel.primary_energy_factor

    def water_fuel_price(self, dwelling):
        return dhw_fuel_cost(dwelling)


class DedicatedWaterSystem(object):
    def __init__(self, effy, summer_immersion):
        self.base_effy = numpy.array([effy, ] * 12)
        self.summer_immersion = summer_immersion
        self.water_mult = 1  # Might be changed after init
        self.system_type = HeatingSystem.TYPES.misc
        self.is_community_heating = False

    def water_heat_effy(self, _Q_water):
        water_effy = self.base_effy * self.water_mult

        if self.summer_immersion:
            for i in range(5, 9):
                water_effy[i] = 100

        return water_effy

    def co2_factor(self):
        return self.fuel.co2_factor

    def primary_energy_factor(self):
        return self.fuel.primary_energy_factor

    def water_fuel_price(self, dwelling):
        return dhw_fuel_cost(dwelling)


def gas_boiler_from_pcdf(dwelling, pcdf_data, fuel, use_immersion_in_summer):
    if pcdf_data['main_type'] == "Combi":
        system_type = HeatingSystem.TYPES.combi
    elif pcdf_data['main_type'] == "CPSU":
        system_type = HeatingSystem.TYPES.cpsu
    else:
        system_type = HeatingSystem.TYPES.regular_boiler

    sys = HeatingSystem(system_type,
                        pcdf_data['winter_effy'],
                        pcdf_data['summer_effy'],
                        False,  # summer immersion 
                        pcdf_data['fan_assisted_flue'] == 'True',
                        True,  # ch pump
                        -1,
                        0.1,
                        fuel)  # !!! Assumes 10% secondary fraction

    # !!!
    sys.has_warm_air_fan = False
    sys.sap_appendixD_eqn = pcdf_data['sap_appendixD_eqn']
    sys.is_condensing = pcdf_data['condensing']

    if pcdf_data['subsidiary_type'] == "with integral PFGHRD":
        if (pcdf_data['subsidiary_type_table'] == "" and
                    pcdf_data['subsidiary_type_index'] == ""):
            # integral PFGHRD, performance data included in boilerl data
            assert not hasattr(dwelling, 'fghrs')
        else:
            if (hasattr(dwelling, 'fghrs') and
                        dwelling.fghrs is None):
                # inputs expliticly say there is no fghrs, so don't
                # add one even if boiler specifies one
                pass
            else:
                if hasattr(dwelling, 'fghrs'):
                    assert dwelling.fghrs['pcdf_id'] == pcdf_data['subsidiary_type_index']
                else:
                    dwelling.fghrs = dict(pcdf_id=pcdf_data['subsidiary_type_index'])

    if pcdf_data['storage_type'] != "Unknown":
        # Shouldn't have cylinder data specified if we are going to
        # use pcdf cylinder info
        assert not hasattr(dwelling, "hw_cylinder_volume")

    if pcdf_data['main_type'] == 'Regular':
        # !!! Also need to allow this for table 4a systems?
        if true_and_not_missing(dwelling, 'cylinder_is_thermal_store'):
            if dwelling.thermal_store_type == ThermalStoreTypes.HW_ONLY:
                sys.table2brow = 6
            else:
                sys.table2brow = 7
            dwelling.has_cylinderstat = True
        else:
            sys.table2brow = 2  # !!! Assumes not electric
    elif pcdf_data['main_type'] == 'Combi':
        # !!! introduce a type for storage types
        if pcdf_data['storage_type'] in ['storage combi with primary store', 'storage combi with secondary store']:
            # !!! Should only do this if combi is the hw system - this
            # !!! check for having a defined ins type works for now,
            # !!! but will need improving
            if not hasattr(dwelling, 'hw_cylinder_insulation_type'):
                dwelling.hw_cylinder_volume = pcdf_data["store_boiler_volume"]
                dwelling.hw_cylinder_insulation = pcdf_data["store_insulation_mms"]
                dwelling.hw_cylinder_insulation_type = sap_worksheet.CylinderInsulationTypes.FOAM
                # Force calc to use the data from pcdf, don't use a user entered cylinder loss
                dwelling.measured_cylinder_loss = None

        if pcdf_data['storage_type'] == 'storage combi with primary store':
            sys.table2brow = 3
            dwelling.has_cylinderstat = True
        elif pcdf_data['storage_type'] == 'storage combi with secondary store':
            sys.table2brow = 4
            dwelling.has_cylinderstat = True

        if not 'keep_hot_facility' in pcdf_data or pcdf_data['keep_hot_facility'] == 'None':
            sys.has_no_keep_hot = True
            sys.table3arow = combi_loss_instant_without_keep_hot
        elif pcdf_data['keep_hot_timer']:
            sys.table3arow = combi_loss_instant_with_timed_heat_hot
            if pcdf_data['keep_hot_facility'] == "elec" or pcdf_data[
                'keep_hot_facility'] == "gas/oil and elec":  # !!! or mixed?
                sys.keep_hot_elec_consumption = 600
        else:
            sys.table3arow = combi_loss_instant_with_untimed_heat_hot
            if pcdf_data['keep_hot_facility'] == "elec" or pcdf_data[
                'keep_hot_facility'] == "gas/oil and elec":  # !!! or mixed?
                sys.keep_hot_elec_consumption = 900
    elif pcdf_data['main_type'] == 'CPSU':
        sys.table2brow = 7  # !!! Assumes gas-fired
        dwelling.has_cylinderstat = True
        sys.cpsu_Tw = dwelling.cpsu_Tw
        sys.cpsu_not_in_airing_cupboard = true_and_not_missing(d, 'cpsu_not_in_airing_cupboard')
    else:
        # !!! What about other table rows?
        raise ValueError("Unknown system type")

    if sys.system_type == HeatingSystem.TYPES.combi:
        configure_combi_loss(dwelling, sys, pcdf_data)
    # !!! Assumes gas/oil boiler
    sys.responsiveness = USE_TABLE_4D_FOR_RESPONSIVENESS
    return sys


def configure_combi_loss(dwelling, sys, pcdf_data):
    if 'storage_loss_factor_f2' in pcdf_data and pcdf_data['storage_loss_factor_f2'] != None:
        sys.combi_loss = combi_loss_table_3c(dwelling, sys, pcdf_data)
    elif 'storage_loss_factor_f1' in pcdf_data and pcdf_data['storage_loss_factor_f1'] != None:
        sys.combi_loss = combi_loss_table_3b(pcdf_data)
    else:
        sys.combi_loss = combi_loss_table_3a(dwelling, sys)

    sys.pcdf_data = pcdf_data  # !!! Needed if we later add a store to this boiler


def solid_fuel_boiler_from_pcdf(pcdf_data, fuel, use_immersion_in_summer):
    # Appendix J
    if pcdf_data['seasonal_effy'] != '':
        effy = float(pcdf_data['seasonal_effy'])
    elif pcdf_data['part_load_fuel_use'] != '':
        untested()  # !!!
        # !!! Need to tests for inside/outside of heated space
        nominal_effy = 100 * (pcdf_data['nominal_heat_to_water'] + pcdf_data['nominal_heat_to_room']) / pcdf_data[
            'nominal_fuel_use']
        part_load_effy = 100 * (pcdf_data['part_load_heat_to_water'] + pcdf_data['part_load_heat_to_room']) / pcdf_data[
            'part_load_fuel_use']
        effy = 0.5 * (nominal_effy + part_load_effy)
    else:
        nominal_effy = 100 * (
            float(pcdf_data['nominal_heat_to_water']) + float(pcdf_data['nominal_heat_to_room'])) / float(
            pcdf_data['nominal_fuel_use'])
        effy = .975 * nominal_effy
    sys = HeatingSystem(HeatingSystem.TYPES.regular_boiler,  # !!!
                        effy,
                        effy,
                        summer_immersion=use_immersion_in_summer,
                        has_flue_fan=False,  #!!!
                        has_ch_pump=True,
                        table2brow=2,  # !!! Solid fuel boilers can only have indirect boiler?
                        default_secondary_fraction=0.1,  # !!! Assumes 10% secondary fraction
                        fuel=fuel)

    sys.responsiveness = .5  # !!! Needs to depend on "main type" input

    # !!!
    sys.has_warm_air_fan = False
    return sys


def twin_burner_cooker_boiler_from_pcdf(pcdf_data,
                                        fuel,
                                        use_immersion_in_summer):
    winter_effy = pcdf_data['winter_effy']
    summer_effy = pcdf_data['summer_effy']

    sys = HeatingSystem(HeatingSystem.TYPES.regular_boiler,  # !!!
                        winter_effy,
                        summer_effy,
                        summer_immersion=use_immersion_in_summer,
                        has_flue_fan=False,  #!!!
                        has_ch_pump=True,
                        table2brow=2,  # !!! Solid fuel boilers can only have indirect boiler?
                        default_secondary_fraction=0.1,  # !!! Assumes 10% secondary fraction
                        fuel=fuel)

    sys.range_cooker_heat_required_scale_factor = 1 - (
        pcdf_data['case_loss_at_full_output'] / pcdf_data['full_output_power'])

    # !!! Assumes we have a heat emitter - is that always the case?
    sys.responsiveness = USE_TABLE_4D_FOR_RESPONSIVENESS

    # !!!
    sys.has_warm_air_fan = False
    return sys

# Table N4
TABLE_N4 = [
    (0.2, 57, 143, 8),  # PSR;N24.16;N24,9;N16,9;
    (0.25, 54, 135, 2),
    (0.3, 51, 127, 10),
    (0.35, 40, 99, 20),
    (0.4, 35, 88, 29),
    (0.45, 31, 77, 40),
    (0.5, 26, 65, 31),
    (0.55, 21, 54, 41),
    (0.6, 17, 43, 30),
    (0.65, 8, 20, 51),
    (0.7, 6, 15, 36),
    (0.75, 4, 10, 40),
    (0.8, 3, 6, 24),
    (0.85, 2, 4, 27),
    (0.9, 0, 1, 15),
    (0.95, 0, 0, 15),
    (1, 0, 0, 14),
    (1.05, 0, 0, 7),
    (1.1, 0, 0, 6),
    (1.15, 0, 0, 3),
    (1.2, 0, 0, 2),
    (1.25, 0, 0, 1),
    (1.3, 0, 0, 0),
]


def interpolate_psr_table(psr, table,
                          key=lambda x: x[0],
                          data=numpy.array):
    if psr >= key(table[-1]):
        return data(table[-1])
    if psr < key(table[0]):
        return data(table[0])

    # !!! Interpolation will fail if psr is off bottom of range
    psr_data_below = max((p for p in table if key(p) < psr),
                         key=key)
    psr_data_above = min((p for p in table if key(p) > psr),
                         key=key)
    frac = (psr - key(psr_data_below)) / (key(psr_data_above) - key(psr_data_below))
    return (1 - frac) * data(psr_data_below) + frac * data(psr_data_above)


def table_n4_heating_days(psr):
    data = interpolate_psr_table(psr, TABLE_N4)
    N24_16 = int(0.5 + data[1])
    N24_9 = int(0.5 + data[2])
    N16_9 = int(0.5 + data[3])
    return N24_16, N24_9, N16_9

# Table N8
TABLE_N8 = [
    # psr;24 hr heating secondary fraction; 16 hr; 11hr; variable
    (0.2, 0.4, 0.53, 0.64, 0.41),
    (0.25, 0.28, 0.43, 0.57, 0.3),
    (0.3, 0.19, 0.34, 0.49, 0.2),
    (0.35, 0.12, 0.27, 0.42, 0.13),
    (0.4, 0.06, 0.2, 0.35, 0.07),
    (0.45, 0.03, 0.14, 0.29, 0.03),
    (0.5, 0.01, 0.09, 0.24, 0.01),
    (0.55, 0, 0.06, 0.19, 0),
    (0.6, 0, 0.03, 0.15, 0),
    (0.65, 0, 0.02, 0.11, 0),
    (0.7, 0, 0.01, 0.09, 0),
    (0.75, 0, 0, 0.05, 0),
    (0.8, 0, 0, 0.05, 0),
    (0.85, 0, 0, 0.03, 0),
    (0.9, 0, 0, 0.02, 0),
    (0.95, 0, 0, 0.01, 0),
    (1, 0, 0, 0.01, 0),
    (1.05, 0, 0, 0, 0),
]


def table_n8_secondary_fraction(psr, heating_duration):
    data = interpolate_psr_table(psr, TABLE_N8)
    if heating_duration == "24":
        table_col = 1
    elif heating_duration == "16":
        table_col = 2
    elif heating_duration == "11":
        table_col = 3
    else:
        assert heating_duration == "V"
        table_col = 4

    interpolated = data[table_col]
    return int(interpolated * 1000 + .5) / 1000.


def micro_chp_from_pcdf(dwelling, pcdf_data, fuel, use_immersion_in_summer):
    # !!! Probably should check provision type in here for consistency
    # !!! with water sys inputs (e.g. summer immersion, etc)
    sys = HeatingSystem(HeatingSystem.TYPES.microchp,
                        -1,
                        -1,
                        summer_immersion=use_immersion_in_summer,
                        has_flue_fan=False,  #!!!
                        has_ch_pump=pcdf_data['separate_circulator'],
                        table2brow=2,
                        default_secondary_fraction=0,  # overwritten below
                        fuel=fuel)

    sys.responsiveness = USE_TABLE_4D_FOR_RESPONSIVENESS

    # It seems that oil based micro chp needs to include a 10W gain
    # inside the dwelling, but doesn't include the electricity
    # consumption of the pump
    if fuel.type == FuelTypes.OIL:
        dwelling.main_heating_oil_pump_inside_dwelling = True
    # !!! Effy adjustments for condensing underfloor heating can be applied?

    if pcdf_data['hw_vessel'] == 1:
        # integral vessel
        dwelling.measured_cylinder_loss = 0
        dwelling.hw_cylinder_volume = 0
        dwelling.has_cylinderstat = True
        dwelling.has_hw_time_control = True
        dwelling.cylinder_in_heated_space = False
        sys.has_integral_store = True
    else:
        sys.has_integral_store = False

    if not hasattr(dwelling, 'secondary_heating_type_code'):
        dwelling.secondary_heating_type_code = 693
        dwelling.secondary_sys_fuel = dwelling.electricity_tariff

    if not pcdf_data['net_specific_elec_consumed_sch3'] is None:
        dwelling.chp_water_elec = sch3_calc(dwelling,
                                            pcdf_data['net_specific_elec_consumed_sch2'],
                                            pcdf_data['net_specific_elec_consumed_sch3'])
    else:
        dwelling.chp_water_elec = pcdf_data['net_specific_elec_consumed_sch2']

    add_appendix_n_equations_microchp(dwelling, sys, pcdf_data)
    return sys


def interpolate_efficiency(psr, psr_dataset):
    if psr > psr_dataset[-1]['psr']:
        raise SAPCalculationError("PSR too large for this system")
    if psr < psr_dataset[0]['psr']:
        raise SAPCalculationError("PSR too small for this system")

    return 1 / interpolate_psr_table(psr, psr_dataset,
                                     key=lambda x: x['psr'],
                                     data=lambda x: 1 / x['space_effy'])


def sch3_calc(dwelling, sch2val, sch3val):
    Vd = dwelling.daily_hot_water_use
    return sch2val + (sch3val - sch2val) * (Vd - 100.2) / 99.6


def add_appendix_n_equations_microchp(dwelling, sys, pcdf_data):
    add_appendix_n_equations_shared(dwelling, sys, pcdf_data)

    def micro_chp_space_effy(self, Q_space):
        h_mean = sum(dwelling.h) / 12
        psr = 1000 * pcdf_data['maximum_output'] / (h_mean * 24.2)
        effy = interpolate_efficiency(psr, pcdf_data['psr_datasets'][0])
        sys.effy_space = effy
        space_heat_in_use_factor = 1
        self.Q_space = Q_space

        dwelling.chp_space_elec = interpolate_psr_table(
            psr, pcdf_data['psr_datasets'][0],
            key=lambda x: x['psr'],
            data=lambda x: x['specific_elec_consumed'])

        return effy * space_heat_in_use_factor

    def micro_chp_water_effy(self, Q_water):
        # !!! Can this all be replaced with regular water function?
        # !!! Winter effy might be the problem as it needs psr

        # !!! adjustments can apply??
        if not pcdf_data['water_heating_effy_sch3'] is None:
            Vd = dwelling.daily_hot_water_use
            summereff = sch3_calc(dwelling,
                                  pcdf_data['water_heating_effy_sch2'],
                                  pcdf_data['water_heating_effy_sch3'])
        else:
            summereff = pcdf_data['water_heating_effy_sch2']
        wintereff = sys.effy_space

        water_effy = weighted_effy(self.Q_space, Q_water, wintereff, summereff)

        if self.summer_immersion:
            for i in range(5, 9):
                water_effy[i] = 100

        return water_effy

    sys.water_heat_effy = types.MethodType(micro_chp_water_effy, sys)
    sys.space_heat_effy = types.MethodType(micro_chp_space_effy, sys)


def heat_pump_from_pcdf(dwelling, pcdf_data, fuel, use_immersion_in_summer):
    # !!! Probably should check provision type in here for consistency
    # !!! with water sys inputs (e.g. summer immersion, etc)
    sys = HeatingSystem(HeatingSystem.TYPES.pcdf_heat_pump,
                        -1,
                        -1,
                        summer_immersion=use_immersion_in_summer,
                        has_flue_fan=False,  #!!!
                        has_ch_pump=pcdf_data['separate_circulator'],
                        table2brow=2,
                        default_secondary_fraction=0,  # overwritten below
                        fuel=fuel)

    if pcdf_data['emitter_type'] == "4":
        sys.responsiveness = 1
        sys.has_warm_air_fan = True
        sys.has_ch_pump = False
    else:
        # !!! Assumes we have a heat emitter - is that always the case?
        sys.responsiveness = USE_TABLE_4D_FOR_RESPONSIVENESS

    if pcdf_data['hw_vessel'] == 1:
        # integral vessel
        dwelling.measured_cylinder_loss = pcdf_data['vessel_heat_loss']
        dwelling.hw_cylinder_volume = pcdf_data['vessel_volume']
        dwelling.has_cylinderstat = True
        dwelling.has_hw_time_control = True
        dwelling.cylinder_in_heated_space = False  # !!! Not sure why this applies?
        sys.has_integral_store = True
    else:
        sys.has_integral_store = False

    if not hasattr(dwelling, 'secondary_heating_type_code'):
        dwelling.secondary_heating_type_code = 693
        dwelling.secondary_sys_fuel = dwelling.electricity_tariff

    add_appendix_n_equations_heat_pumps(dwelling, sys, pcdf_data)
    return sys


def add_appendix_n_equations_heat_pumps(dwelling, sys, pcdf_data):
    add_appendix_n_equations_shared(dwelling, sys, pcdf_data)

    def heat_pump_space_effy(self, Q_space):
        h_mean = sum(dwelling.h) / 12
        psr = 1000 * pcdf_data['maximum_output'] / (h_mean * 24.2)

        if not pcdf_data['number_of_air_flow_rates'] is None:
            throughput = 0.5  # !!!
            flow_rate = dwelling.volume * throughput / 3.6

            if flow_rate < pcdf_data['air_flow_2']:
                assert flow_rate >= pcdf_data['air_flow_1']  # !!!
                flowrateset1 = 0
                flowrateset2 = 1
            else:
                # doesn't matter if flow rate > flowrate_3 because
                # when we do the interpolation we limit frac to 1
                flowrateset1 = 1
                flowrateset2 = 2

            flowrate1 = pcdf_data['air_flow_%d' % (flowrateset1 + 1)]
            flowrate2 = pcdf_data['air_flow_%d' % (flowrateset2 + 1)]
            frac = min(1, (flow_rate - flowrate1) / (flowrate2 - flowrate1))

            effy1 = interpolate_efficiency(psr, pcdf_data['psr_datasets'][flowrateset1])
            effy2 = interpolate_efficiency(psr, pcdf_data['psr_datasets'][flowrateset2])
            effy = (1 - frac) * effy1 + frac * effy2
            run_hrs1 = interpolate_psr_table(psr,
                                             pcdf_data['psr_datasets'][flowrateset1],
                                             key=lambda x: x['psr'],
                                             data=lambda x: x['running_hours'])
            run_hrs2 = interpolate_psr_table(psr, pcdf_data['psr_datasets'][flowrateset2],
                                             key=lambda x: x['psr'],
                                             data=lambda x: x['running_hours'])
            running_hours = (int)((1 - frac) * run_hrs1 + frac * run_hrs2 + .5)
            Rhp = 1  # !!!
            Qfans = dwelling.volume * dwelling.adjusted_fan_sfp * throughput * Rhp * (
                8760 - running_hours) / 3600
            dwelling.Q_mech_vent_fans = Qfans
        else:
            effy = interpolate_efficiency(psr, pcdf_data['psr_datasets'][0])

        space_heat_in_use_factor = .95
        return effy * space_heat_in_use_factor

    def heat_pump_water_effy(self, Q_water):
        if pcdf_data['hw_vessel'] == 1:  # integral
            in_use_factor = .95
        elif pcdf_data['hw_vessel'] == 2:  # separate, specified
            dwelling.hw_cylinder_area = 9e9  # !!! Should be input
            # !!! Need to check performance criteria of cylinder (table N7)
            if (dwelling.hw_cylinder_volume >= pcdf_data['vessel_volume'] and
                # !!! Might not always have measured loss - can also come from insulation type, etc
                        dwelling.measured_cylinder_loss <= pcdf_data['vessel_heat_loss'] and
                        dwelling.hw_cylinder_area >= pcdf_data['vessel_heat_exchanger']):
                in_use_factor = .95
            else:
                in_use_factor = .6
        elif pcdf_data['hw_vessel'] == 3:  # separate, unspecified
            in_use_factor = .6
        else:
            assert False
            in_use_factor = 1

        # !!! also need sch3 option
        water_effy = [max(100, pcdf_data['water_heating_effy_sch2'] * in_use_factor), ] * 12
        if self.summer_immersion:
            for i in range(5, 9):
                water_effy[i] = 100
        return water_effy

    sys.water_heat_effy = types.MethodType(heat_pump_water_effy, sys)
    sys.space_heat_effy = types.MethodType(heat_pump_space_effy, sys)


def add_appendix_n_equations_shared(dwelling, sys, pcdf_data):
    def longer_heating_days(self):
        h_mean = sum(dwelling.h) / 12
        psr = 1000 * pcdf_data['maximum_output'] / (h_mean * 24.2)

        # !!! Not the best place to set this
        dwelling.fraction_of_heat_from_main = 1 - table_n8_secondary_fraction(psr, pcdf_data['heating_duration'])

        # TABLE N3
        if pcdf_data['heating_duration'] == "V":
            N24_16, N24_9, N16_9 = table_n4_heating_days(psr)
        elif pcdf_data['heating_duration'] == "24":
            N24_16, N24_9, N16_9 = (104, 261, 0)
        elif pcdf_data['heating_duration'] == "16":
            N24_16, N24_9, N16_9 = (0, 0, 261)
        else:
            assert pcdf_data['heating_duration'] == "11"
            N24_16, N24_9, N16_9 = (0, 0, 0)

        # TABLE N5
        MONTH_ORDER = [0, 11, 1, 2, 10, 3, 9, 4, 5, 6, 7, 8]
        N_WE = [9, 9, 8, 9, 8, 8, 9, 9, 9, 9, 9, 8]
        N_WD = [22, 22, 20, 22, 22, 22, 22, 22, 21, 22, 22, 22]

        N24_9_m = [0, ] * 12
        N16_9_m = [0, ] * 12
        N24_16_m = [0, ] * 12
        for i in range(12):
            month = MONTH_ORDER[i]

            # Allocate weekdays
            N24_9_m[month] = min(N_WD[i], N24_9)
            N24_9 -= N24_9_m[month]
            N_WD[i] -= N24_9_m[month]

            N16_9_m[month] = min(N_WD[i], N16_9)
            N16_9 -= N16_9_m[month]

            # Allocate weekends
            N24_16_m[month] = min(N_WE[i], N24_16)
            N24_16 -= N24_16_m[month]

        return numpy.array(N24_16_m), numpy.array(N24_9_m), numpy.array(N16_9_m),

    dwelling.longer_heating_days = types.MethodType(longer_heating_days, dwelling)


def pcdf_heating_system(dwelling,
                        pcdf_id,
                        fuel,
                        use_immersion_in_summer):
    pcdf_data = pcdf.get_boiler(pcdf_id)
    if not pcdf_data is None:
        return gas_boiler_from_pcdf(dwelling, pcdf_data, fuel, use_immersion_in_summer)

    pcdf_data = pcdf.get_solid_fuel_boiler(pcdf_id)
    if not pcdf_data is None:
        return solid_fuel_boiler_from_pcdf(pcdf_data, fuel, use_immersion_in_summer)

    pcdf_data = pcdf.get_twin_burner_cooker_boiler(pcdf_id)
    if not pcdf_data is None:
        return twin_burner_cooker_boiler_from_pcdf(pcdf_data, fuel, use_immersion_in_summer)

    pcdf_data = pcdf.get_heat_pump(pcdf_id)
    if not pcdf_data is None:
        return heat_pump_from_pcdf(dwelling, pcdf_data, fuel, use_immersion_in_summer)

    pcdf_data = pcdf.get_microchp(pcdf_id)
    if not pcdf_data is None:
        return micro_chp_from_pcdf(dwelling, pcdf_data, fuel, use_immersion_in_summer)


def sap_table_heating_system(dwelling,
                             system_code,
                             fuel,
                             use_immersion_in_summer,
                             hetas_approved):
    if system_code in TABLE_4A:
        system = get_4a_main_system(dwelling,
                                    system_code,
                                    fuel,
                                    use_immersion_in_summer,
                                    hetas_approved)
    else:
        system = get_4b_main_system(dwelling,
                                    system_code,
                                    fuel,
                                    use_immersion_in_summer)
    return system


TABLE_D7 = {
    FuelTypes.GAS: {
        # Modulating, condensing, type
        (False, False, HeatingSystem.TYPES.regular_boiler): (-6.5, 3.8, -6.5),
        (False, True, HeatingSystem.TYPES.regular_boiler): (-2.5, 1.45, -2.5),
        (True, False, HeatingSystem.TYPES.regular_boiler): (-2.0, 3.15, -2.0),
        (True, True, HeatingSystem.TYPES.regular_boiler): (-2.0, -0.95, -2.0),
        (False, False, HeatingSystem.TYPES.combi): (-6.8, -3.7, -6.8),
        (False, True, HeatingSystem.TYPES.combi): (-2.8, -5.0, -2.8),
        (True, False, HeatingSystem.TYPES.combi): (-6.1, 4.15, -6.1),
        (True, True, HeatingSystem.TYPES.combi): (-2.1, -0.7, -2.1),
        (False, False, HeatingSystem.TYPES.storage_combi): (-6.59, -0.5, -6.59),
        (False, True, HeatingSystem.TYPES.storage_combi): (-6.59, -0.5, -6.59),
        (True, False, HeatingSystem.TYPES.storage_combi): (-1.7, 3.0, -1.7),
        (True, True, HeatingSystem.TYPES.storage_combi): (-1.7, -1.0, -1.7),
        (False, False, HeatingSystem.TYPES.cpsu): (-0.64, -1.25, -0.64),
        (True, False, HeatingSystem.TYPES.cpsu): (-0.64, -1.25, -0.64),
        (False, True, HeatingSystem.TYPES.cpsu): (-0.28, -3.15, -0.28),
        (True, True, HeatingSystem.TYPES.cpsu): (-0.28, -3.15, -0.28),
    },
    FuelTypes.OIL: {
        # Condensing, type
        (False, HeatingSystem.TYPES.regular_boiler): (0, -5.2, -1.1),
        (True, HeatingSystem.TYPES.regular_boiler): (0, 1.1, -1.1),
        (False, HeatingSystem.TYPES.combi): (-2.8, 1.45, -2.8),
        (True, HeatingSystem.TYPES.combi): (-2.8, -0.25, -2.8),
        (False, HeatingSystem.TYPES.storage_combi): (-2.8, -2.8, -2.8),
        (True, HeatingSystem.TYPES.storage_combi): (-2.8, -0.95, -2.8),
    }
}


def sedbuk_2005_heating_system(dwelling,
                               fuel,
                               sedbuk_2005_effy,
                               range_case_loss,
                               range_full_output,
                               boiler_type,
                               fan_assisted_flue,
                               use_immersion_heater_summer):
    modulating = True  # !!!
    is_condensing = True  # !!!

    if fuel.type == FuelTypes.GAS:
        d7_data = TABLE_D7[FuelTypes.GAS][(modulating, is_condensing, boiler_type)]
    else:
        d7_data = TABLE_D7[fuel.type][(is_condensing, boiler_type)]

    k1 = d7_data[0]
    k2 = d7_data[1]
    k3 = d7_data[2]
    f = .901  # !!! Assumes natural gas !!!

    nflnet = (sedbuk_2005_effy - k1) / f + k2
    nplnet = (sedbuk_2005_effy - k1) / f - k2

    if nflnet > 95.5:
        nflnet -= 0.673 * (nflnet - 95.5)
    if nplnet > 96.6:
        nplnet -= .213 * (nplnet - 96.6)

    # !!! Assumes gas
    if is_condensing:
        nflnet = min(98, nflnet)
        nplnet = min(108, nplnet)
    else:
        assert False  # !!!
        nflnet = min(92, nflnet)
        nplnet = min(91, nplnet)

    annual_effy = 0.5 * (nflnet + nplnet) * f + k3
    annual_effy = int(annual_effy * 10 + .5) / 10.
    return sedbuk_2009_heating_system(
        dwelling,
        fuel,
        annual_effy,
        range_case_loss,
        range_full_output,
        boiler_type,
        is_condensing,
        fan_assisted_flue,
        use_immersion_heater_summer)


"""
class AppendixD:
    class BurnerTypes:
        ON_OFF
        MODULATING

    class BoilerTypes:
        REGULAR
        INSTANTANEOUS_COMBI
        STORAGE_COMBI
        CPSU
"""

TABLE_D2_7 = {
    FuelTypes.GAS: {
        # !!! Assumes modulating burner !!!
        HeatingSystem.TYPES.regular_boiler: (1., -9.7),
        HeatingSystem.TYPES.combi: (.9, -9.2),
        HeatingSystem.TYPES.storage_combi: (.8, -8.3),
        HeatingSystem.TYPES.cpsu: (.22, -1.64),
    },
    FuelTypes.OIL: {
        HeatingSystem.TYPES.regular_boiler: (1.1, -10.6),
        HeatingSystem.TYPES.combi: (1., -8.5),
        HeatingSystem.TYPES.storage_combi: (.9, -7.2),
    }
}


# !!! Needs completing
def get_seasonal_effy_offset(is_modulating_burner,
                             fuel,
                             boiler_type):
    assert is_modulating_burner  # !!!
    return TABLE_D2_7[fuel.type][boiler_type]


def sedbuk_2009_heating_system(dwelling,
                               fuel,
                               sedbuk_2009_effy,
                               range_case_loss,
                               range_full_output,
                               boiler_type,
                               is_condensing,
                               fan_assisted_flue,
                               use_immersion_heater_summer):
    # !!! Assumes this boiler is also the HW sytstem!
    winter_offset, summer_offset = get_seasonal_effy_offset(
        True,  # !!!
        fuel,
        boiler_type)

    effy_winter = sedbuk_2009_effy + winter_offset
    effy_summer = sedbuk_2009_effy + summer_offset

    # !!! Don't include a flue fan for oil boilers (move to table 5 stuff?)
    has_flue_fan = fan_assisted_flue and fuel.type != FuelTypes.OIL

    # !!! Assumes either a regular boiler or storage combi
    if boiler_type == HeatingSystem.TYPES.regular_boiler:
        table2brow = 2
    elif boiler_type == HeatingSystem.TYPES.storage_combi:
        table2brow = 3
    elif boiler_type == HeatingSystem.TYPES.cpsu:
        table2brow = 7
    else:
        table2brow = -1

    system = HeatingSystem(boiler_type,
                           effy_winter,
                           effy_summer,
                           use_immersion_heater_summer,
                           has_flue_fan,
                           True,  # CH pump
                           table2brow,
                           .1,  # !!! 2ndary fraction
                           fuel)

    system.responsiveness = 1
    system.is_condensing = is_condensing
    if system.system_type in [HeatingSystem.TYPES.combi,
                              HeatingSystem.TYPES.storage_combi]:
        system.combi_loss = combi_loss_table_3a(dwelling, system)

        if hasattr(dwelling, 'hw_cylinder_volume') and dwelling.hw_cylinder_volume > 0:
            dwelling.has_cylinderstat = True  # !!! Does this go here?
    elif system.system_type == HeatingSystem.TYPES.cpsu:
        # !!! Might also need to set cpsu_Tw here?
        system.cpsu_not_in_airing_cupboard = true_and_not_missing(dwelling, 'cpsu_not_in_airing_cupboard')

    if range_case_loss != None:
        system.range_cooker_heat_required_scale_factor = 1 - (
            range_case_loss / range_full_output)

    return system


class CommunityDistributionTypes:
    PRE_1990_UNINSULATED = 1
    PRE_1990_INSULATED = 2
    MODERN_HIGH_TEMP = 3
    MODERN_LOW_TEMP = 4


TABLE_12c = {
    CommunityDistributionTypes.PRE_1990_UNINSULATED: 1.2,
    CommunityDistributionTypes.PRE_1990_INSULATED: 1.1,
    CommunityDistributionTypes.MODERN_HIGH_TEMP: 1.1,
    CommunityDistributionTypes.MODERN_LOW_TEMP: 1.05,
}


class CommunityHeating:
    class CommunityFuel:
        def __init__(self):
            self.standing_charge = 106

        @property
        def is_mains_gas(self):
            return False

    def __init__(self, heat_sources, sap_distribution_type):
        self.is_community_heating = True
        self.table2brow = 2  # !!! Assume indirect cylinder inside dwelling
        self.system_type = HeatingSystem.TYPES.community
        self.has_ch_pump = False
        self.has_oil_pump = False

        self.has_flue_fan = False
        self.has_warm_air_fan = False
        self.responsiveness = 1
        self.summer_immersion = False
        self.default_secondary_fraction = 0.1

        self.fuel = self.CommunityFuel()
        if not sap_distribution_type is None:
            self.distribution_loss_factor = TABLE_12c[sap_distribution_type]
        else:
            self.distribution_loss_factor = 1.5

        self.chp_fraction = 0
        self.chp_heat_to_power = 0
        self.chp_effy = 0
        boiler_effy_sum = 0
        boiler_co2_factor_sum = 0
        boiler_pe_factor_sum = 0
        boiler_price_sum = 0
        boiler_fraction_sum = 0
        chp_system = None
        biggest_contributor = heat_sources[0]
        for hs in heat_sources:
            if 'heat_to_power' in hs:
                # chp
                assert chp_system is None  # should only find one?
                chp_system = hs
            else:
                boiler_effy_sum += hs['fraction'] / hs['efficiency']
                boiler_fraction_sum += hs['fraction']
                boiler_co2_factor_sum += hs['fuel'].co2_factor * hs['fraction'] / hs['efficiency']
                boiler_pe_factor_sum += hs['fuel'].primary_energy_factor * hs['fraction'] / hs['efficiency']
                boiler_price_sum += hs['fuel'].unit_price() * hs['fraction']

            if hs['fraction'] > biggest_contributor['fraction']:
                biggest_contributor = hs

        self.boiler_effy = boiler_fraction_sum / boiler_effy_sum
        boiler_co2_factor = boiler_co2_factor_sum / boiler_fraction_sum
        boiler_pe_factor = boiler_pe_factor_sum / boiler_fraction_sum
        boiler_price = boiler_price_sum / boiler_fraction_sum
        if not chp_system is None:
            self.chp_fraction += chp_system['fraction']
            self.chp_heat_to_power = chp_system['heat_to_power']
            total_effy = chp_system['efficiency']
            heat_effy = total_effy * self.chp_heat_to_power / (1 + self.chp_heat_to_power)
            chp_effy = heat_effy

            self.heat_to_power_ratio = self.chp_heat_to_power / self.chp_fraction
            self.co2_factor_ = (
                self.chp_fraction * chp_system['fuel'].co2_factor / chp_effy +
                (1 - self.chp_fraction) * boiler_co2_factor)

            self.pe_factor = (
                self.chp_fraction * chp_system['fuel'].primary_energy_factor / chp_effy +
                (1 - self.chp_fraction) * boiler_pe_factor)

            chp_price = HEAT_FROM_CHP.unit_price()
            self.fuel_price_ = (self.chp_fraction * chp_price +
                                (1 - self.chp_fraction) * boiler_price)

        else:
            self.heat_to_power_ratio = 0
            self.co2_factor_ = boiler_co2_factor
            self.pe_factor = boiler_pe_factor
            self.fuel_price_ = boiler_price

        # this is for TER, not completely this is right - how do you
        # pick the TER fuel if you also have a second main system?
        for hs in heat_sources:
            if hs['fuel'].is_mains_gas:
                self.fuel.fuel_factor = hs['fuel'].fuel_factor
                self.fuel.emission_factor_adjustment = hs['fuel'].emission_factor_adjustment
                return

        self.fuel.fuel_factor = biggest_contributor['fuel'].fuel_factor
        self.fuel.emission_factor_adjustment = biggest_contributor['fuel'].emission_factor_adjustment

    def space_heat_effy(self, _Q_space):
        # Efficiencies work a bit differently for community systems -
        # system efficiency is not accounted to in calculating energy
        # consumption and cost (so we return 100% here, scaled for
        # additional loss factors.  System effy is included in CO2 and
        # primary energy factors. 
        space_mult = 1 / (self.space_heat_charging_factor * self.distribution_loss_factor)
        return 100 * space_mult

    def water_heat_effy(self, _Q_water):
        space_mult = 1 / (self.dhw_charging_factor * self.distribution_loss_factor)
        return 100 * space_mult

    def fuel_price(self, dwelling):
        return self.fuel_price_

    def co2_factor(self):
        return self.co2_factor_

    def primary_energy_factor(self):
        return self.pe_factor

    def water_fuel_price(self, dwelling):
        return self.fuel_price_


def configure_fuel_costs(dwelling):
    dwelling.general_elec_co2_factor = dwelling.electricity_tariff.co2_factor
    dwelling.general_elec_price = dwelling.electricity_tariff.unit_price(
        dwelling.electricity_tariff.general_elec_on_peak_fraction)
    dwelling.mech_vent_elec_price = dwelling.electricity_tariff.unit_price(
        dwelling.electricity_tariff.mech_vent_elec_on_peak_fraction)

    dwelling.general_elec_PE = dwelling.electricity_tariff.primary_energy_factor

    if dwelling.water_sys.summer_immersion:
        # Should this be here or in sap_worksheet.py?
        on_peak = immersion_on_peak_fraction(dwelling.Nocc,
                                             dwelling.electricity_tariff,
                                             dwelling.hw_cylinder_volume,
                                             dwelling.immersion_type)
        dwelling.water_fuel_price_immersion = dwelling.electricity_tariff.unit_price(on_peak)

    fuels = set()
    fuels.add(dwelling.main_sys_1.fuel)
    fuels.add(dwelling.water_sys.fuel)
    if hasattr(dwelling, "main_sys_2"):
        fuels.add(dwelling.main_sys_2.fuel)

    # Standing charge for electricity is only included if main heating or
    # hw uses electricity
    if (hasattr(dwelling, "secondary_sys") and
            not dwelling.secondary_sys.fuel.is_electric):
        fuels.add(dwelling.secondary_sys.fuel)
    if true_and_not_missing(dwelling, 'use_immersion_heater_summer'):
        fuels.add(dwelling.electricity_tariff)

    standing_charge = 0
    for f in fuels:
        standing_charge += f.standing_charge
    dwelling.cost_standing = standing_charge


def configure_responsiveness(dwelling):
    if dwelling.main_sys_1.responsiveness == USE_TABLE_4D_FOR_RESPONSIVENESS:
        sys1_responsiveness = dwelling.heating_responsiveness = TABLE_4d[dwelling.heating_emitter_type]
    else:
        sys1_responsiveness = dwelling.main_sys_1.responsiveness

    if hasattr(dwelling, 'main_sys_2') and dwelling.main_heating_2_fraction > 0:
        if dwelling.main_sys_2.responsiveness == USE_TABLE_4D_FOR_RESPONSIVENESS:
            sys2_responsiveness = dwelling.heating_responsiveness = TABLE_4d[dwelling.heating_emitter_type2]
        else:
            sys2_responsiveness = dwelling.main_sys_2.responsiveness
    else:
        sys2_responsiveness = 0
    assert sys1_responsiveness >= 0
    assert sys2_responsiveness >= 0

    dwelling.heating_responsiveness = (
        sys1_responsiveness * dwelling.main_heating_fraction +
        sys2_responsiveness * dwelling.main_heating_2_fraction)
    dwelling.heating_responsiveness_sys1 = sys1_responsiveness  # used for TER


def configure_control_system1(dwelling, system):
    # !!! Need to check main sys 2 here
    control = TABLE_4E[dwelling.control_type_code]
    dwelling.temperature_adjustment = control['Tadjustment']
    dwelling.has_room_thermostat = (control['thermostat'] == "TRUE")
    dwelling.has_trvs = control['trv'] == "TRUE"

    dwelling.heating_control_type_sys1 = control['control_type']

    system.heating_control_type = control['control_type']
    if control['other_adj_table'] != None:
        control['other_adj_table'](dwelling, dwelling.main_sys_1)
        if control['other_adj_table'] == apply_4c2:
            apply_4c1(dwelling, dwelling.main_sys_1,
                      dwelling.sys1_load_compensator if hasattr(dwelling, "sys1_load_compensator") else None)

    # !!! Special case table 4c4 for warm air heat pumps - needs
    # !!! to apply to sys2 too
    # !!! Should only apply if water is from this system!!
    if hasattr(dwelling,
               'main_heating_type_code') and dwelling.main_heating_type_code >= 521 and dwelling.main_heating_type_code <= 527:
        system.water_mult = .7


def configure_control_system2(dwelling, system):
    # !!! Duplication with function above !!!
    control = TABLE_4E[dwelling.control_2_type_code]

    dwelling.heating_control_type_sys2 = control['control_type']

    system.heating_control_type = control['control_type']
    if control['other_adj_table'] != None:
        control['other_adj_table'](dwelling, dwelling.main_sys_2)
        if control['other_adj_table'] == apply_4c2:
            apply_4c1(dwelling, system,
                      dwelling.sys2_load_compensator if hasattr(dwelling, "sys2_load_compensator") else None)

    # !!! Should only apply if water is from this system!!
    if hasattr(dwelling,
               'main_heating_2_type_code') and dwelling.main_heating_2_type_code >= 521 and dwelling.main_heating_type_code <= 527:
        system.water_mult = .7


def configure_main_system(dwelling):
    if hasattr(dwelling, 'main_heating_pcdf_id') and not dwelling.main_heating_pcdf_id is None:
        dwelling.main_sys_1 = pcdf_heating_system(dwelling,
                                                  dwelling.main_heating_pcdf_id,
                                                  dwelling.main_sys_fuel,
                                                  dwelling.use_immersion_heater_summer if hasattr(dwelling,
                                                                                                  'use_immersion_heater_summer') else False)
        # !!! Might need to enforce a secondary system?
    elif (hasattr(dwelling, 'sys1_sedbuk_2005_effy') and
              not dwelling.sys1_sedbuk_2005_effy is None):
        dwelling.main_sys_1 = sedbuk_2005_heating_system(
            dwelling,
            dwelling.main_sys_fuel,
            dwelling.sys1_sedbuk_2005_effy,
            dwelling.sys1_sedbuk_range_case_loss_at_full_output if hasattr(dwelling,
                                                                           'sys1_sedbuk_range_case_loss_at_full_output') else None,
            dwelling.sys1_sedbuk_range_full_output if hasattr(dwelling, 'sys1_sedbuk_range_full_output') else None,
            dwelling.sys1_sedbuk_type,
            dwelling.sys1_sedbuk_fan_assisted,
            dwelling.use_immersion_heater_summer if hasattr(dwelling, 'use_immersion_heater_summer') else False)
    elif (hasattr(dwelling, 'sys1_sedbuk_2009_effy')
          and not dwelling.sys1_sedbuk_2009_effy is None):
        dwelling.main_sys_1 = sedbuk_2009_heating_system(
            dwelling,
            dwelling.main_sys_fuel,
            dwelling.sys1_sedbuk_2009_effy,
            dwelling.sys1_sedbuk_range_case_loss_at_full_output if hasattr(dwelling,
                                                                           'sys1_sedbuk_range_case_loss_at_full_output') else None,
            dwelling.sys1_sedbuk_range_full_output if hasattr(dwelling, 'sys1_sedbuk_range_full_output') else None,
            dwelling.sys1_sedbuk_type,
            True,  # !!! Assumes condensing
            dwelling.sys1_sedbuk_fan_assisted,
            dwelling.use_immersion_heater_summer if hasattr(dwelling, 'use_immersion_heater_summer') else False)
    elif dwelling.main_heating_type_code == "community":
        # !!! Can Community can be second main system too?
        dwelling.main_sys_1 = CommunityHeating(
            dwelling.community_heat_sources,
            (dwelling.sap_community_distribution_type
             if hasattr(dwelling, 'sap_community_distribution_type')
             else None))
        dwelling.main_sys_fuel = dwelling.main_sys_1.fuel
    else:
        dwelling.main_sys_1 = sap_table_heating_system(
            dwelling,
            dwelling.main_heating_type_code,
            dwelling.main_sys_fuel,
            dwelling.use_immersion_heater_summer if hasattr(dwelling, 'use_immersion_heater_summer') else False,
            dwelling.sys1_hetas_approved if hasattr(dwelling, 'sys1_hetas_approved') else False)
        # !!! Should really check here for no main system specified, and
        # !!! use a default if that's the case


def configure_main_system_2(dwelling):
    # !!! Sedbuk systems

    if hasattr(dwelling, 'main_heating_2_pcdf_id') and not dwelling.main_heating_2_pcdf_id is None:
        dwelling.main_sys_2 = pcdf_heating_system(dwelling,
                                                  dwelling.main_heating_2_pcdf_id,
                                                  dwelling.main_sys_2_fuel,
                                                  dwelling.use_immersion_heater_summer if hasattr(dwelling,
                                                                                                  'use_immersion_heater_summer') else False)
        # !!! Might need to enforce a secondary system?
    elif hasattr(dwelling, 'main_heating_2_type_code') and not dwelling.main_heating_2_type_code is None:
        dwelling.main_sys_2 = sap_table_heating_system(
            dwelling,
            dwelling.main_heating_2_type_code,
            dwelling.main_sys_2_fuel,
            dwelling.use_immersion_heater_summer if hasattr(dwelling, 'use_immersion_heater_summer') else False,
            dwelling.sys2_hetas_approved if hasattr(dwelling, 'sys2_hetas_approved') else False)


def configure_secondary_system(dwelling):
    # !!! Need to apply the rules from A4 here - need to do this
    # before fraction_of_heat_from_main is set.  Also back boiler
    # should have secondary system - see section 9.2.8

    if hasattr(dwelling, 'secondary_heating_type_code'):
        dwelling.secondary_sys = get_4a_secondary_system(dwelling)
    elif hasattr(dwelling, 'secondary_sys_manuf_effy'):
        dwelling.secondary_sys = get_manuf_data_secondary_system(dwelling)

    # There must be a secondary system if electric storage heaters
    # or off peak underfloor electric
    if hasattr(dwelling, 'main_heating_type_code'):
        if not hasattr(dwelling, 'secondary_sys') and (
                    (dwelling.main_heating_type_code >= 401 and dwelling.main_heating_type_code <= 408)
                or (
                            dwelling.main_heating_type_code >= 421 and dwelling.main_heating_type_code <= 425 and dwelling.main_sys_fuel != ELECTRICITY_STANDARD)):
            # !!! Does 24 hour tariff count as being offpeak?
            dwelling.secondary_heating_type_code = 693
            dwelling.secondary_sys_fuel = dwelling.electricity_tariff
            dwelling.secondary_sys = get_4a_secondary_system(dwelling)

    if not hasattr(dwelling, 'secondary_sys') and true_and_not_missing(dwelling, 'force_secondary_heating'):
        dwelling.secondary_heating_type_code = 693
        dwelling.secondary_sys_fuel = dwelling.electricity_tariff
        dwelling.secondary_sys = get_4a_secondary_system(dwelling)


def configure_water_system(dwelling):
    if hasattr(dwelling, 'water_heating_type_code'):  # !!! Why this tests?
        code = dwelling.water_heating_type_code

        if code in TABLE_4A:
            water_system = get_4a_system(dwelling, code)
            dwelling.water_sys = DedicatedWaterSystem(water_system['effy'],
                                                      dwelling.use_immersion_heater_summer if hasattr(dwelling,
                                                                                                      'use_immersion_heater_summer') else False)
            dwelling.water_sys.table2brow = water_system['table2brow']
            dwelling.water_sys.fuel = dwelling.water_sys_fuel
        elif code == 999:  # no h/w system present - assume electric immersion
            pass
        elif code == 901:  # from main
            dwelling.water_sys = dwelling.main_sys_1
        elif code == 902:  # from secondary
            dwelling.water_sys = dwelling.secondary_sys
        elif code == 914:  # from second main
            dwelling.water_sys = dwelling.main_sys_2
        elif code == 950:  # community dhw only
            # !!! Community hot water based on sap defaults not handled
            dwelling.water_sys = CommunityHeating(
                dwelling.community_heat_sources_dhw,
                (dwelling.sap_community_distribution_type_dhw
                 if hasattr(dwelling, 'sap_community_distribution_type_dhw')
                 else None))
            if true_and_not_missing(dwelling,
                                    'community_dhw_flat_rate_charging'):
                dwelling.water_sys.dhw_charging_factor = 1.05
            else:
                dwelling.water_sys.dhw_charging_factor = 1.0
            if dwelling.main_sys_1.system_type == HeatingSystem.TYPES.community:
                # Standing charge already covered by main system
                dwelling.water_sys.fuel.standing_charge = 0
            else:
                # Only half of standing charge applies for DHW only
                dwelling.water_sys.fuel.standing_charge /= 2
        else:
            assert False


def configure_water_storage(dwelling):
    if dwelling.water_sys.is_community_heating:
        dwelling.has_cylinderstat = True
        dwelling.community_heating_dhw = True  # use for table 3
        # Community heating
        if not hasattr(dwelling, 'hw_cylinder_volume'):
            dwelling.hw_cylinder_volume = 110
            dwelling.storage_loss_factor = .0152

    if dwelling.water_heating_type_code in [907, 908, 909]:
        dwelling.instantaneous_pou_water_heating = True
        dwelling.has_hw_cylinder = False
        dwelling.primary_circuit_loss_annual = 0
    elif dwelling.has_hw_cylinder:
        if hasattr(dwelling, "measured_cylinder_loss") and dwelling.measured_cylinder_loss != None:
            dwelling.temperature_factor = hw_temperature_factor(dwelling, True)
        else:
            # !!! Is this electric CPSU tests in the right place?
            if (dwelling.water_sys.system_type == HeatingSystem.TYPES.cpsu and
                    dwelling.water_sys.fuel.is_electric):
                dwelling.storage_loss_factor = 0.022
            elif not hasattr(dwelling, 'storage_loss_factor'):
                # This is already set for community heating dhw
                dwelling.storage_loss_factor = hw_storage_loss_factor(dwelling)
            dwelling.volume_factor = hw_volume_factor(dwelling.hw_cylinder_volume)
            dwelling.temperature_factor = hw_temperature_factor(dwelling, False)
        dwelling.primary_circuit_loss_annual = hw_primary_circuit_loss(dwelling)
    else:
        dwelling.storage_loss_factor = 0
        dwelling.volume_factor = 0
        dwelling.temperature_factor = 0
        dwelling.primary_circuit_loss_annual = 0


def configure_systems(dwelling):
    dwelling.community_heating_dhw = False
    dwelling.Nfluelessgasfires = 0
    if hasattr(dwelling, 'main_heating_type_code') and dwelling.main_heating_type_code == 613:
        dwelling.Nfluelessgasfires += 1
    if hasattr(dwelling, 'secondary_heating_type_code') and dwelling.secondary_heating_type_code == 613:
        dwelling.Nfluelessgasfires += 1

    configure_main_system(dwelling)
    configure_main_system_2(dwelling)
    # !!! fraction of heat from main 2 not specified, assume 0%
    if not hasattr(dwelling, 'main_heating_fraction'):
        dwelling.main_heating_fraction = 1
        dwelling.main_heating_2_fraction = 0

    configure_secondary_system(dwelling)

    if hasattr(dwelling, 'secondary_sys'):
        dwelling.fraction_of_heat_from_main = 1 - dwelling.main_sys_1.default_secondary_fraction
    else:
        dwelling.fraction_of_heat_from_main = 1

    configure_water_system(dwelling)
    configure_wwhr(dwelling)
    configure_fghr(dwelling)
    configure_water_storage(dwelling)

    configure_controls(dwelling)


def configure_controls(dwelling):
    if not hasattr(dwelling, 'sys1_has_boiler_interlock'):
        # !!! Should really only be added for boilers, but I don't
        # !!! think it will do anything for other systems, so ok? (If
        # !!! it doesn't have a boiler then it doesn't have a boiler
        # !!! interlock?)

        # !!! Potentially different for main_1 & main_2?
        dwelling.sys1_has_boiler_interlock = False
    dwelling.main_sys_1.has_interlock = dwelling.sys1_has_boiler_interlock
    dwelling.water_sys.has_interlock = dwelling.hwsys_has_boiler_interlock if hasattr(dwelling,
                                                                                      'hwsys_has_boiler_interlock') else False

    if dwelling.water_sys.system_type in [HeatingSystem.TYPES.combi,
                                          HeatingSystem.TYPES.storage_combi]:
        dwelling.combi_loss = dwelling.water_sys.combi_loss

    if not hasattr(dwelling, 'heating_control_type_sys1'):
        configure_control_system1(dwelling, dwelling.main_sys_1)

    if hasattr(dwelling, 'main_sys_2') and not hasattr(dwelling, 'heating_control_type_sys2') and hasattr(dwelling,
                                                                                                          "control_2_type_code") and dwelling.control_2_type_code != 2100:
        configure_control_system2(dwelling, dwelling.main_sys_2)


def configure_fans_and_pumps(dwelling):
    fans_and_pumps_gain(dwelling)
    fans_and_pumps_electricity(dwelling)

    configure_responsiveness(dwelling)
    configure_fuel_costs(dwelling)


def configure_cooling_system(dwelling):
    if hasattr(dwelling, 'cooled_area') and dwelling.cooled_area > 0:
        dwelling.fraction_cooled = dwelling.cooled_area / dwelling.GFA

        if hasattr(dwelling, "cooling_tested_eer"):
            cooling_eer = dwelling.cooling_tested_eer
        elif dwelling.cooling_packaged_system == True:
            cooling_eer = TABLE_10C[dwelling.cooling_energy_label]['packaged_sys_eer']
        else:
            cooling_eer = TABLE_10C[dwelling.cooling_energy_label]['split_sys_eer']

        if dwelling.cooling_compressor_control == 'on/off':
            dwelling.cooling_seer = 1.25 * cooling_eer
        else:
            dwelling.cooling_seer = 1.35 * cooling_eer
    else:
        dwelling.fraction_cooled = 0
        dwelling.cooling_seer = 1  # Need a number, but doesn't matter what


def configure_wwhr(dwelling):
    if hasattr(dwelling, 'wwhr_systems') and not dwelling.wwhr_systems is None:
        for sys in dwelling.wwhr_systems:
            sys['pcdf_sys'] = pcdf.get_wwhr_system(sys['pcdf_id'])


def configure_fghr(dwelling):
    # !!! Should check that fghr is allowed for this system

    if hasattr(dwelling, 'fghrs') and not dwelling.fghrs is None:
        # !!! Need to add electrical power G1.4
        # !!! Entire fghrs calc is unfinished really
        dwelling.fghrs.update(
            dict(pcdf.get_fghr_system(dwelling.fghrs['pcdf_id'])))

        if dwelling.fghrs["heat_store"] == "3":
            assert dwelling.water_sys.system_type == HeatingSystem.TYPES.combi
            assert not hasattr(dwelling, 'hw_cylinder_volume')
            assert not dwelling.has_hw_cylinder

            dwelling.has_hw_cylinder = True
            dwelling.has_cylinderstat = True
            dwelling.has_hw_time_control = True
            dwelling.hw_cylinder_volume = dwelling.fghrs['heat_store_total_volume']
            dwelling.measured_cylinder_loss = dwelling.fghrs['heat_store_loss_rate']
            dwelling.water_sys.table2brow = 5

            # !!! This ideally wouldn't be here!  Basically combi loss
            # !!! has already been calculated, but now we are adding a
            # !!! thermal store, so need to recalculate it
            if hasattr(dwelling.water_sys, 'pcdf_data'):
                configure_combi_loss(dwelling,
                                     dwelling.water_sys,
                                     dwelling.water_sys.pcdf_data)
            else:
                dwelling.water_sys.combi_loss = combi_loss_table_3a(
                    dwelling, dwelling.water_sys)

            if dwelling.fghrs["has_pv_module"]:
                assert "PV_kWp" in dwelling.fghrs
                configure_pv_system(dwelling.fghrs)
                dwelling.fghrs['monthly_solar_hw_factors'] = TABLE_H3[dwelling.fghrs['pitch']]
        else:
            assert not "PV_kWp" in dwelling.fghrs

        if (dwelling.water_sys.system_type in [HeatingSystem.TYPES.combi,
                                               HeatingSystem.TYPES.storage_combi]
            and true_and_not_missing(dwelling.water_sys, 'has_no_keep_hot')
            and not dwelling.has_hw_cylinder):
            dwelling.fghrs['equations'] = dwelling.fghrs['equations_combi_without_keephot_without_ext_store']
        else:
            dwelling.fghrs['equations'] = dwelling.fghrs['equations_other']


def configure_pv_system(pv_system):
    pv_system['overshading_factor'] = TABLE_H4[pv_system['overshading_category']]
    if str(pv_system['pitch']).lower() != "Horizontal".lower():
        pv_system['Igh'] = TABLE_H2[pv_system['pitch']][pv_system['orientation']]
    else:
        pv_system['Igh'] = TABLE_H2[pv_system['pitch']]


def configure_pv(dwelling):
    if hasattr(dwelling, 'photovoltaic_systems'):
        for pv_system in dwelling.photovoltaic_systems:
            configure_pv_system(pv_system)


def configure_solar_hw(dwelling):
    if hasattr(dwelling, 'solar_collector_aperture') and dwelling.solar_collector_aperture != None:
        dwelling.collector_overshading_factor = TABLE_H4[dwelling.collector_overshading]
        if str(dwelling.collector_pitch).lower() != "Horizontal".lower():
            dwelling.collector_Igh = TABLE_H2[dwelling.collector_pitch][dwelling.collector_orientation]
        else:
            dwelling.collector_Igh = TABLE_H2[dwelling.collector_pitch]

        dwelling.monthly_solar_hw_factors = TABLE_H3[dwelling.collector_pitch]
        if dwelling.solar_storage_combined_cylinder:
            dwelling.solar_effective_storage_volume = dwelling.solar_dedicated_storage_volume + 0.3 * (
            dwelling.hw_cylinder_volume - dwelling.solar_dedicated_storage_volume)
        else:
            dwelling.solar_effective_storage_volume = dwelling.solar_dedicated_storage_volume

        if not hasattr(dwelling, 'collector_zero_loss_effy'):
            default_params = TABLE_H1[dwelling.collector_type]
            dwelling.collector_zero_loss_effy = default_params[0]
            dwelling.collector_heat_loss_coeff = default_params[1]


def configure_wind_turbines(dwelling):
    if hasattr(dwelling, 'N_wind_turbines'):
        dwelling.wind_turbine_speed_correction_factor = get_M1_correction_factor(
            dwelling.terrain_type,
            dwelling.wind_turbine_hub_height)


def do_sap_table_lookups(dwelling):
    global get_fuel_data
    if true_and_not_missing(dwelling, 'use_pcdf_fuel_prices'):
        get_fuel_data = get_fuel_data_pcdf
    else:
        get_fuel_data = get_fuel_data_table_12

    # Fix up fuel types
    if hasattr(dwelling, 'water_sys_fuel') and dwelling.water_sys_fuel == ELECTRICITY_STANDARD:
        dwelling.water_sys_fuel = dwelling.electricity_tariff
    if hasattr(dwelling, 'secondary_sys_fuel') and dwelling.secondary_sys_fuel == ELECTRICITY_STANDARD:
        dwelling.secondary_sys_fuel = dwelling.electricity_tariff

    dwelling.Nocc = occupancy(dwelling)
    dwelling.daily_hot_water_use = daily_hw_use(dwelling)

    region = dwelling.sap_region
    dwelling.external_temperature_summer = TABLE_10[region]['external_temperature']
    dwelling.Igh_summer = TABLE_10[region]['solar_radiation']
    dwelling.latitude = TABLE_10[region]['latitude']

    if not hasattr(dwelling, 'living_area_fraction'):
        dwelling.living_area_fraction = dwelling.living_area / dwelling.GFA

    if hasattr(dwelling, "wall_type"):
        dwelling.structural_infiltration = 0.35 if dwelling.wall_type == WallTypes.MASONRY else 0.25

    if hasattr(dwelling, 'floor_type'):
        dwelling.floor_infiltration = FLOOR_INFILTRATION[dwelling.floor_type]

    overshading_factors = TABLE_6D[dwelling.overshading]
    dwelling.light_access_factor = overshading_factors["light_access_factor"]
    dwelling.solar_access_factor_winter = overshading_factors["solar_access_factor_winter"]
    dwelling.solar_access_factor_summer = overshading_factors["solar_access_factor_summer"]

    configure_ventilation(dwelling)
    configure_systems(dwelling)
    configure_cooling_system(dwelling)
    configure_pv(dwelling)
    configure_solar_hw(dwelling)
    configure_wind_turbines(dwelling)
    configure_fans_and_pumps(dwelling)

    # Bit of a special case here!
    if true_and_not_missing(dwelling, 'reassign_systems_for_test_case_30'):
        # Basically, I have no idea what happens here
        assert False

    if hasattr(dwelling, 'nextStage'):
        dwelling.nextStage()
