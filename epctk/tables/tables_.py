import math
import os.path

import numpy

from ..appendix.appendix_f import cpsu_store, elec_cpsu_store
from ..elements.sap_types import (TerrainTypes, FuelTypes, CylinderInsulationTypes, OvershadingTypes, HeatingTypes,
                                  VentilationTypes, BoilerTypes, FloorTypes)
from ..utils import csv_to_dict

_DATA_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')


def table_1b_occupancy(TFA):
    """
    Table 1b Part 1: Occupancy

    if TFA > 13.9: N = 1 + 1.76 × [1-exp (-0.000349 × (TFA-13.9)2 )] + 0.0013 × (TFA-13.9)

    if TFA ≤ 13.9: N=1

    Args:
        TFA: Total Floor Area

    Returns:
        int: Assumed number of occupants
    """
    if TFA > 13.9:
        return 1 + 1.76 * (1 - math.exp(-0.000349 * (TFA - 13.9) ** 2)) + 0.0013 * (TFA - 13.9)
    else:
        return 1


def table_1b_daily_hot_water(Nocc, low_water_use):
    """
    Table 1b part 2: Domestic hot water usage


    (a) Annual average hot water usage in litres per day Vd,average = (25 × N) + 36
    (b) Reduce the annual average hot water usage by 5% if the dwelling is designed
        to achieve a water use target of not more that 125 litres per person per day
        (all water use, hot and cold)
    (c) For each month, multiply Vd,average by the factor from Table 1c to obtain
        the daily volume in the month Vd,m
    (d) The energy content of water used is
            4.190 × Vd,m × nm × ∆Tm / 3600 kWh/month
        where ∆Tm is the temperature rise for month m from Table 1d.
    (e) Distribution loss is 0.15 times energy content calculated in (d).

    This function calculates parts a) and b)

    Args:
        Nocc: Number of Occupants (from Table 1b part 1)
        low_water_use (bool): Whether the dwelling is designed to save water (see point b)

    Returns:
        Average daily hot water use
    """
    if low_water_use:
        return (25. * Nocc + 36.) * .95
    else:
        return 25. * Nocc + 36.


# Table 1c
MONTHLY_HOT_WATER_FACTORS = numpy.array([1.1, 1.06, 1.02, 0.98, 0.94, 0.9, 0.9, 0.94, 0.98, 1.02, 1.06, 1.1])

# Table 1d
MONTHLY_HOT_WATER_TEMPERATURE_RISE = numpy.array(
    [41.2, 41.4, 40.1, 37.6, 36.4, 33.9, 30.4, 33.4, 33.5, 36.3, 39.4, 39.9])


def table_2_hot_water_store_loss_factor(hw_cylinder_insulation_type, hw_cylinder_insulation):
    """
    Table 2

    Calculate Hot water storage loss factor according to equation in Note 1.
    of Table 2 (rather than using the tabulated values)

    Args:
        hw_cylinder_insulation_type (CylinderInsulationTypes):
        hw_cylinder_insulation: thickness of cylinder insulation in mm

    Returns:
        hot water storage loss factor in kWh/litre/day

    """
    if hw_cylinder_insulation_type == CylinderInsulationTypes.FOAM:
        return 0.005 + 0.55 / (hw_cylinder_insulation + 4)
    else:
        return 0.005 + 1.76 / (hw_cylinder_insulation + 12.8)


def table_2a_hot_water_vol_factor(cylinder_volume):
    """
    Table 2a

    Calculate the volume factor according to equation in Note 2. of Table 2a
    When using Table 2, the loss is to be multiplied by the volume factor.

    Args:
        cylinder_volume: volume of hot water cylinder

    Returns:
        hot water volume factor
    """
    return (120. / cylinder_volume) ** (1.0 / 3.0)


# Table 2b
# Table 2b is actually a table of functions. Define the functions first and add them
# to a dict lookup to give the table

def constant(k):
    return lambda d: k


def cylinder_indirect(dwelling):
    temperature_factor = 0.6
    if dwelling.get('has_hw_time_control') is True:
        temperature_factor *= 0.9
    if not dwelling.has_cylinderstat:
        temperature_factor *= 1.3

    return temperature_factor


def storage_combi_primary(d):
    return (0.82
            if d.hw_cylinder_volume >= 115
            else .82 + 0.0022 * (115 - d.hw_cylinder_volume))


def storage_combi_secondary(d):
    return (0.6
            if d.hw_cylinder_volume >= 115
            else 0.6 + 0.0016 * (115 - d.hw_cylinder_volume))


# Table 2b format:
# Row number: (With Manufacturers data, Table 2 fallback)
_TABLE_2b = {
    1: (constant(0.6), constant(0.6)),
    2: (cylinder_indirect, cylinder_indirect),
    3: (0, storage_combi_primary),
    4: (storage_combi_secondary, storage_combi_secondary),
    5: (cylinder_indirect, cylinder_indirect),  # same equations as indirect cylinder
    6: (cpsu_store, cpsu_store),
    7: (cpsu_store, cpsu_store),
    8: (elec_cpsu_store, elec_cpsu_store),
    9: (constant(1), constant(1)),
}


def table_2b_hot_water_temp_factor(dwelling, measured_loss):
    """
    Calculate the hot water temperature factor according to Table 2b

    Args:
        dwelling (Dwelling):
        measured_loss: boolean, whether the losses are measured by manufacturer or must be assumed

    Returns:
    """

    if measured_loss:
        return _TABLE_2b[dwelling.water_sys.table2b_row][0](dwelling)
    else:
        return _TABLE_2b[dwelling.water_sys.table2b_row][1](dwelling)


# Table 3 Primary Circuit losses
TABLE_3 = {
    1: 0,
    2: 1220,
    3: 610,
    4: 0,
    5: 360,
    6: 0,
    7: 0,
    8: 0,
    9: 0,
    10: 280,  # !!! Different for insulated/not insulated pipework
    11: 0,
    12: 360,
}


# Table 3a
# !!! Need to add the other options in here
def combi_loss_instant_without_keep_hot(daily_hot_water_use):
    fn = numpy.where(daily_hot_water_use > 100,
                     1.0,
                     daily_hot_water_use / 100)
    return 600.0 * fn


def combi_loss_instant_with_timed_heat_hot(daily_hot_water_use):
    return 600.0


def combi_loss_instant_with_untimed_heat_hot(daily_hot_water_use):
    return 900.0


def combi_loss_storage_combi_more_than_55l(daily_hot_water_use):
    return 0


def combi_loss_storage_combi_less_than_55l(Vc, daily_hot_water_use):
    fn = numpy.where(daily_hot_water_use > 100,
                     1.0,
                     daily_hot_water_use / 100)
    return (600 - (Vc - 15) * 15) * fn


def combi_loss_table_3a(dwelling, system):
    storage_volume = dwelling.get('hw_cylinder_volume', 0)

    if storage_volume == 0:
        if system.get("table3a_fn"):
            return system.table3a_fn
        else:
            # !!! Need other keep hot types
            return combi_loss_instant_without_keep_hot
    elif storage_volume < 55:
        return lambda hw_use: combi_loss_storage_combi_less_than_55l(dwelling.hw_cylinder_volume, hw_use)
    else:
        return combi_loss_storage_combi_more_than_55l


# FIXME Need to complete this table
def combi_loss_table_3b(pcdf_data):
    # !!! Need to set storage loss here
    # dwelling.measured_cylinder_loss=0#pcdf_data['storage_loss_factor_f1']
    # dwelling.has_hw_cylinder=True
    # system.table2b_row=5
    # dwelling.has_cylinderstat=True
    return lambda x: 365 * pcdf_data['storage_loss_factor_f1']


# !!! Need to complete this table
def combi_loss_table_3c():
    raise NotImplementedError("Combi Loss Table 3c not implemented")


def system_efficiency(system_data, fuel):
    """
    Try to get the efficiency of the given heating sustem

    Args:
        system_data: HeatingSystem
        fuel: fuel of this heating system.
        .. todo:
         why can't we just get the fuel from the system?

    Returns:
    """
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


# Table 5a
# FIXME: NEED TO FINISH THIS!
def has_oil_pump_inside(dwelling):
    return (dwelling.get('main_heating_oil_pump_inside_dwelling') or
            dwelling.get('main_heating_2_oil_pump_inside_dwelling'))


def table_5a_fans_and_pumps_gain(dwelling):
    """
    Table 5a gains from pumps and fans
    Args:
        dwelling:

    Returns:

    """
    fans_pumps_gain = 0
    heating_system_gain = 0

    # !!! Nope, this is for balanced without heat recovery
    # if dwelling.ventilation_type==VentilationTypes.MVHR:
    #    fansandpumps_gain+=dwelling.adjusted_fan_sfp*0.06*dwelling.volume

    ch_pump_gain = 10 if dwelling.get('central_heating_pump_in_heated_space', False) else 0

    if (dwelling.main_sys_1.has_ch_pump or
            (dwelling.get('main_sys_2') and dwelling.main_sys_2.has_ch_pump)):
        fans_pumps_gain += ch_pump_gain
        heating_system_gain += ch_pump_gain

    if has_oil_pump_inside(dwelling):
        fans_pumps_gain += 10
        heating_system_gain += 10
    if dwelling.get('has_fans_for_positive_input_vent_from_outside'):
        assert False
    if dwelling.get('has_fans_for_balanced_mech_vent_without_hr'):
        assert False

    if dwelling.ventilation_type not in [VentilationTypes.MVHR,
                                         VentilationTypes.MV]:
        if dwelling.main_sys_1.has_warm_air_fan or (
                        dwelling.get('main_sys_2') and
                        dwelling.main_sys_2.has_warm_air_fan and
                        dwelling.main_heating_2_fraction > 0):
            fans_pumps_gain += 0.06 * dwelling.volume

    if dwelling.ventilation_type == VentilationTypes.MV:
        fans_pumps_gain += dwelling.adjusted_fan_sfp * .06 * dwelling.volume
    elif dwelling.ventilation_type == VentilationTypes.PIV_FROM_OUTSIDE:
        fans_pumps_gain += dwelling.adjusted_fan_sfp * .12 * dwelling.volume

    dwelling.pump_gain = fans_pumps_gain
    dwelling.heating_system_pump_gain = heating_system_gain


# Table 6d
TABLE_6D = {
    OvershadingTypes.HEAVY: dict(
        solar_access_factor_winter=0.3,
        solar_access_factor_summer=0.5,
        light_access_factor=0.5),
    OvershadingTypes.MORE_THAN_AVERAGE: dict(
        solar_access_factor_winter=0.54,
        solar_access_factor_summer=0.7,
        light_access_factor=0.67),
    OvershadingTypes.AVERAGE: dict(
        solar_access_factor_winter=0.77,
        solar_access_factor_summer=0.9,
        light_access_factor=0.83),
    OvershadingTypes.VERY_LITTLE: dict(
        solar_access_factor_winter=1,
        solar_access_factor_summer=1,
        light_access_factor=1),
}


# Table 10


def summer_to_annual(summer_vals):
    return numpy.array([0.0, ] * 5 + [float(s) for s in summer_vals] + [0.0, ] * 4)


def translate_10_row(regions, row):
    climate_data = dict(
        code=int(row[0]),
        name=row[1],
        latitude=float(row[2]),
        solar_radiation=summer_to_annual(row[3:6]),
        external_temperature=summer_to_annual(row[6:9]))

    regions[climate_data['code']] = climate_data


TABLE_10 = csv_to_dict(os.path.join(_DATA_FOLDER, 'table_10.csv'), translate_10_row)


# Table 10c
def translate_10c_row(systems, row):
    system = dict(
        energy_label=row[0],
        split_sys_eer=float(row[1]),
        packaged_sys_eer=float(row[2]))
    systems[system['energy_label']] = system


TABLE_10C = csv_to_dict(os.path.join(_DATA_FOLDER, 'table_10c.csv'), translate_10c_row)

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


# !!! Needs completing
def get_seasonal_effy_offset(is_modulating_burner,
                             fuel,
                             boiler_type):
    assert is_modulating_burner  # !!!
    return TABLE_D2_7[fuel.type][boiler_type]


def is_cpsu(type_code):
    return (120 <= type_code <= 123) or type_code == 192


def is_storage_heater(type_code):
    return 401 <= type_code <= 407  # (408 is an integrated system)


def is_off_peak_only_system(type_code):
    return type_code == 421 or type_code == 515


def is_integrated_system(type_code):
    return type_code in [408, 422, 423]


def is_electric_boiler(type_code):
    return 191 <= type_code <= 196


def is_boiler(type_code):
    return type_code < 200


def is_heat_pump(type_code):
    return ((201 <= type_code <= 207) or
            (521 <= type_code <= 527))


def is_room_heater(type_code):
    return 601 <= type_code <= 694


def is_warm_air_system(type_code):
    # Note overlap with heat pumps
    return 501 <= type_code <= 527


def system_type_from_sap_code(system_code, system_data):
    if ('boiler_type' in system_data and
                system_data['boiler_type'] == BoilerTypes.COMBI):
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


FLOOR_INFILTRATION = {
    FloorTypes.SUSPENDED_TIMBER_UNSEALED: 0.2,
    FloorTypes.SUSPENDED_TIMBER_SEALED: 0.1,
    FloorTypes.NOT_SUSPENDED_TIMBER: 0,
    FloorTypes.OTHER: 0,
}