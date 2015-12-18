import math
import os
import re

import numpy

from sap.heating_systems import HeatingSystem, SecondarySystem, appendix_f_cpsu_on_peak
from .fuels import Fuel, ElectricityTariff, ELECTRICITY_7HR, ELECTRICITY_10HR, ELECTRICITY_24HR
from .pcdf import (VentilationTypes, get_in_use_factors)
from .sap_types import FloorTypes, ImmersionTypes, TerrainTypes, FuelTypes, CylinderInsulationTypes, \
    ThermalStoreTypes, OvershadingTypes, SHWCollectorTypes, HeatingTypes, PVOvershading
from .utils import SAPCalculationError, csv_to_dict, true_and_not_missing, float_or_zero

_DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')

IGH_HEATING = numpy.array([26, 54, 94, 150, 190, 201, 194, 164, 116, 68, 33, 21])

T_EXTERNAL_HEATING = numpy.array([4.5, 5, 6.8, 8.7, 11.7, 14.6, 16.9, 16.9, 14.3, 10.8, 7, 4.9])

WIND_SPEED = numpy.array([5.4, 5.1, 5.1, 4.5, 4.1, 3.9, 3.7, 3.7, 4.2, 4.5, 4.8, 5.1])

ELECTRICITY_OFFSET = ElectricityTariff(37, 37, 1, 1)
ELECTRICITY_SOLD = ElectricityTariff(36, 36, 1, 1)

FLOOR_INFILTRATION = {
    FloorTypes.SUSPENDED_TIMBER_UNSEALED: 0.2,
    FloorTypes.SUSPENDED_TIMBER_SEALED: 0.1,
    FloorTypes.NOT_SUSPENDED_TIMBER: 0,
    FloorTypes.OTHER: 0,
}

# ----------------------------
# SAP STANDARD NUMBERED TABLES
# ----------------------------

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
    if dwelling.hw_cylinder_insulation_type == CylinderInsulationTypes.FOAM:
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
        temperature_factor *= 0.9
    if not d.has_cylinderstat:
        temperature_factor *= 1.3

    return temperature_factor


def cpsu_store(dwelling):
    if dwelling.get('measured_cylinder_loss'):
        temperature_factor = .89
    else:
        temperature_factor = 1.08

    if true_and_not_missing(dwelling, 'has_hw_time_control'):
        temperature_factor *= 0.81

    # Check airing cupboard
    if true_and_not_missing(dwelling.water_sys, 'cpsu_not_in_airing_cupboard'):
        # !!! Actually this is if cpsu or thermal store not in airing cupboard
        temperature_factor *= 1.1

    return temperature_factor


def elec_cpsu_store(dwelling):
    if dwelling.get('measured_cylinder_loss'):
        return 1.09 + 0.012 * (dwelling.water_sys.cpsu_Tw - 85)
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
        if dwelling.main_sys_1.system_type == HeatingTypes.cpsu:
            return 7
        if (dwelling.get('main_heating_type_code') and
            dwelling.main_heating_type_code == 191):
            return 1

    if dwelling.water_sys.system_type in [HeatingTypes.combi,
                                          HeatingTypes.storage_combi]:
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
    elif (dwelling.water_sys.system_type in [HeatingTypes.pcdf_heat_pump,
                                             HeatingTypes.microchp]
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
        # return 6


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
    storage_volume = dwelling.get('hw_cylinder_volume', 0)

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
    # dwelling.measured_cylinder_loss=0#pcdf_data['storage_loss_factor_f1']
    # dwelling.has_hw_cylinder=True
    # system.table2brow=5
    # dwelling.has_cylinderstat=True
    return lambda x: 365 * pcdf_data['storage_loss_factor_f1']


# !!! Need to complete this table
def combi_loss_table_3c():
    return None


# Table 4a
# !!! Electric storage systems - offpeak and 24 hour tariff systems
# have same type codes!


def translate_4a_row(systems, row):
    if row[6] != 'n/a':
        sys = dict(
                code=int(row[0]),
                # type=row[1],
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


TABLE_4A = csv_to_dict(os.path.join(_DATA_FOLDER, 'table_4a.csv'), translate_4a_row)


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
        else:  # if fuel in [BULK_LPG, BOTTLED_LPG, LPG_COND18]:
            # Should be LPG fuel if we get here, but do this assertion
            # check anyway which will catch everything apart from LNG
            assert fuel.type == FuelTypes.GAS
            return system_data['effy_lpg']

    raise ValueError("Input error if we get here?")


def has_ch_pump(dwelling):
    return (dwelling.get('heating_emitter_type') or
            (dwelling.get('heating_emitter_type2') and
             not dwelling.heating_emitter_type2 is None))


def system_type_from_sap_code(system_code, system_data):
    if ('boiler_type' in system_data and
                system_data['boiler_type'] == BOILER_TYPES['COMBI']):
        return HeatingTypes.combi
    elif is_cpsu(system_code):
        return HeatingTypes.cpsu
    elif is_off_peak_only_system(system_code):
        return HeatingTypes.off_peak_only
    elif is_integrated_system(system_code):
        return HeatingTypes.integrated_system
    elif is_storage_heater(system_code):
        return HeatingTypes.storage_heater
    elif is_electric_boiler(system_code):
        return HeatingTypes.electric_boiler
    elif is_boiler(system_code):
        return HeatingTypes.regular_boiler
    elif is_heat_pump(system_code):
        return HeatingTypes.heat_pump
    elif is_room_heater(system_code):
        return HeatingTypes.room_heater
    elif is_warm_air_system(system_code):
        return HeatingTypes.warm_air
    return HeatingTypes.misc


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

    if system.system_type in [HeatingTypes.combi,
                              HeatingTypes.storage_combi]:
        system.combi_loss = combi_loss_table_3a(dwelling, system)
    elif system.system_type == HeatingTypes.cpsu:
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
             if dwelling.get('use_immersion_heater_summer')
             else False))
    sys.table2brow = system_data['table2brow']
    sys.fuel = dwelling.secondary_sys_fuel

    if system_data['water_effy'] != "same" and system_data['water_effy'] != "":
        sys.water_effy = float(system_data['water_effy'])

    return sys


def get_manuf_data_secondary_system(dwelling):
    effy = dwelling.secondary_sys_manuf_effy
    sys = SecondarySystem(
            HeatingTypes.misc,
            effy,
            (dwelling.use_immersion_heater_summer
             if dwelling.get('use_immersion_heater_summer')
             else False))
    # sys.table2brow=system_data['table2brow']
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


TABLE_4B = csv_to_dict(os.path.join(_DATA_FOLDER, 'table_4b.csv'), translate_4b_row)


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
    if system.system_type in [HeatingTypes.combi,
                              HeatingTypes.storage_combi]:
        system.combi_loss = combi_loss_table_3a(dwelling, system)
    elif system.system_type == HeatingTypes.cpsu:
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
            dwelling.get('fghrs') and
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
    if (dwelling.main_sys_1.system_type == HeatingTypes.cpsu or
            (dwelling.get('thermal_store_type') and
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
              dwelling.get("hwsys_has_boiler_interlock") and
              not dwelling.hwsys_has_boiler_interlock):
        apply_adjustment = True

    if apply_adjustment:
        space_heat_effy_adjustment = -5
        if not dwelling.water_sys.system_type in [HeatingTypes.combi,
                                                  HeatingTypes.cpsu,
                                                  HeatingTypes.storage_combi]:
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
            dwelling.get("sys1_load_compensator") and
                dwelling.sys1_load_compensator in [
                LoadCompensators.ENHANCED_LOAD_COMPENSATOR,
                LoadCompensators.WEATHER_COMPENSATOR]):
        dwelling.main_sys_1.space_mult = .75

    if dwelling.water_sys is sys:
        # !!! This assumes it supplies all of the DHW - also need the 50% case
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


TABLE_4E = csv_to_dict(os.path.join(_DATA_FOLDER, 'table_4e.csv'), translate_4e_row)


# Table 4f
def has_oil_pump(dwelling):
    return (dwelling.main_sys_1.has_oil_pump or
            (dwelling.get('main_sys_2') and
             dwelling.main_heating_2_fraction > 0 and
             dwelling.main_sys_2.has_oil_pump))


def heating_fans_and_pumps_electricity(dwelling):
    Qfansandpumps = 0
    if (dwelling.main_sys_1.has_ch_pump or
            (dwelling.get('main_sys_2') and
                 dwelling.main_sys_2.has_ch_pump)):
        if dwelling.has_room_thermostat:
            Qfansandpumps += 130
        else:
            Qfansandpumps += 130 * 1.3

    if has_oil_pump(dwelling):
        if dwelling.has_room_thermostat:
            Qfansandpumps += 100
        else:
            # raise RuntimeError("!!! DO WE EVER GET HERE?")
            Qfansandpumps += 100 * 1.3

    if dwelling.main_sys_1.has_flue_fan:
        Qfansandpumps += 45

    if (dwelling.get('main_sys_2') and
            dwelling.main_sys_2.has_flue_fan and
                dwelling.main_heating_2_fraction > 0):
        Qfansandpumps += 45

    if dwelling.main_sys_1.has_warm_air_fan or (
                    dwelling.get('main_sys_2') and
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
     ) = get_in_use_factors()


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
    # if dwelling.ventilation_type==VentilationTypes.MVHR:
    #    fansandpumps_gain+=dwelling.adjusted_fan_sfp*0.06*dwelling.volume

    ch_pump_gain = (0
                    if (dwelling.get('central_heating_pump_in_heated_space')
                        and not dwelling.central_heating_pump_in_heated_space)
                    else 10)
    if (dwelling.main_sys_1.has_ch_pump or
            (dwelling.get('main_sys_2') and dwelling.main_sys_2.has_ch_pump)):
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
                        dwelling.get('main_sys_2') and
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


TABLE_10 = csv_to_dict(os.path.join(_DATA_FOLDER, 'table_10.csv'), translate_10_row)


# Table 10c
def translate_10c_row(systems, row):
    system = dict(
            energy_label=row[0],
            split_sys_eer=float(row[1]),
            packaged_sys_eer=float(row[2]))
    systems[system['energy_label']] = system


TABLE_10C = csv_to_dict(os.path.join(_DATA_FOLDER, 'table_10c.csv'), translate_10c_row)


# Table 12a
def dhw_on_peak_fraction(water_sys, dwelling):
    # !!! Need to complete this table
    if water_sys.system_type == HeatingTypes.cpsu:
        return appendix_f_cpsu_on_peak(water_sys, dwelling)
    elif water_sys.system_type == HeatingTypes.heat_pump:
        # !!! Need off-peak immersion option
        return .7
    elif water_sys.system_type in [HeatingTypes.pcdf_heat_pump,
                                   HeatingTypes.microchp]:
        return .7
    else:
        return water_sys.fuel.general_elec_on_peak_fraction


# Table 13
def immersion_on_peak_fraction(N_occ,
                               elec_tariff,
                               cylinder_volume,
                               immersion_type):
    """

    :param N_occ: number of occupants
    :param elec_tariff:
    :param cylinder_volume:
    :param immersion_type:
    :return:
    """
    if elec_tariff == ELECTRICITY_7HR:
        if immersion_type == ImmersionTypes.SINGLE:
            return max(0, ((14530 - 762 * N_occ) / cylinder_volume - 80 + 10 * N_occ) / 100)
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


def enum(**enums):
    return type('Enum', (), enums)


def is_cpsu(type_code):
    return (type_code >= 120 and type_code <= 123) or type_code == 192


def is_storage_heater(type_code):
    return type_code >= 401 and type_code <= 407  # (408 is an integrated system)


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


def interpolate_efficiency(psr, psr_dataset):
    if psr > psr_dataset[-1]['psr']:
        raise SAPCalculationError("PSR too large for this system")
    if psr < psr_dataset[0]['psr']:
        raise SAPCalculationError("PSR too small for this system")

    return 1 / interpolate_psr_table(psr, psr_dataset,
                                     key=lambda x: x['psr'],
                                     data=lambda x: 1 / x['space_effy'])


TABLE_D7 = {
    FuelTypes.GAS: {
        # Modulating, condensing, type
        (False, False, HeatingTypes.regular_boiler): (-6.5, 3.8, -6.5),
        (False, True, HeatingTypes.regular_boiler): (-2.5, 1.45, -2.5),
        (True, False, HeatingTypes.regular_boiler): (-2.0, 3.15, -2.0),
        (True, True, HeatingTypes.regular_boiler): (-2.0, -0.95, -2.0),
        (False, False, HeatingTypes.combi): (-6.8, -3.7, -6.8),
        (False, True, HeatingTypes.combi): (-2.8, -5.0, -2.8),
        (True, False, HeatingTypes.combi): (-6.1, 4.15, -6.1),
        (True, True, HeatingTypes.combi): (-2.1, -0.7, -2.1),
        (False, False, HeatingTypes.storage_combi): (-6.59, -0.5, -6.59),
        (False, True, HeatingTypes.storage_combi): (-6.59, -0.5, -6.59),
        (True, False, HeatingTypes.storage_combi): (-1.7, 3.0, -1.7),
        (True, True, HeatingTypes.storage_combi): (-1.7, -1.0, -1.7),
        (False, False, HeatingTypes.cpsu): (-0.64, -1.25, -0.64),
        (True, False, HeatingTypes.cpsu): (-0.64, -1.25, -0.64),
        (False, True, HeatingTypes.cpsu): (-0.28, -3.15, -0.28),
        (True, True, HeatingTypes.cpsu): (-0.28, -3.15, -0.28),
    },
    FuelTypes.OIL: {
        # Condensing, type
        (False, HeatingTypes.regular_boiler): (0, -5.2, -1.1),
        (True, HeatingTypes.regular_boiler): (0, 1.1, -1.1),
        (False, HeatingTypes.combi): (-2.8, 1.45, -2.8),
        (True, HeatingTypes.combi): (-2.8, -0.25, -2.8),
        (False, HeatingTypes.storage_combi): (-2.8, -2.8, -2.8),
        (True, HeatingTypes.storage_combi): (-2.8, -0.95, -2.8),
    }
}

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
        HeatingTypes.regular_boiler: (1., -9.7),
        HeatingTypes.combi: (.9, -9.2),
        HeatingTypes.storage_combi: (.8, -8.3),
        HeatingTypes.cpsu: (.22, -1.64),
    },
    FuelTypes.OIL: {
        HeatingTypes.regular_boiler: (1.1, -10.6),
        HeatingTypes.combi: (1., -8.5),
        HeatingTypes.storage_combi: (.9, -7.2),
    }
}


# !!! Needs completing
def get_seasonal_effy_offset(is_modulating_burner,
                             fuel,
                             boiler_type):
    assert is_modulating_burner  # !!!
    return TABLE_D2_7[fuel.type][boiler_type]


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
        self.system_type = HeatingTypes.community
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

        if chp_system is not None:
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

            chp_price = Fuel(48).unit_price()
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


USE_TABLE_4D_FOR_RESPONSIVENESS = -99