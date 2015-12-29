import math
import os.path

import numpy

from .appendix_f import cpsu_store, elec_cpsu_store
from .fuels import ElectricityTariff, ELECTRICITY_7HR, ELECTRICITY_10HR, ELECTRICITY_24HR
from .sap_types import (TerrainTypes, FuelTypes, CylinderInsulationTypes, OvershadingTypes, SHWCollectorTypes,
                        HeatingTypes, PVOvershading, HeatEmitters,
                        VentilationTypes, BoilerTypes)
from .utils import SAPCalculationError, csv_to_dict, exists_and_true, float_or_zero

_DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')

USE_TABLE_4D_FOR_RESPONSIVENESS = -99

ELECTRICITY_OFFSET = ElectricityTariff(37, 37, 1, 1)
ELECTRICITY_SOLD = ElectricityTariff(36, 36, 1, 1)


# ----------------------------
# SAP STANDARD NUMBERED TABLES
# ----------------------------
# Table 1b part 1
def occupancy(GFA):
    return 1 + 1.76 * (1 - math.exp(-0.000349 * (GFA - 13.9) ** 2)) + 0.0013 * (
        GFA - 13.9) if GFA > 13.9 else 1


# Table 1b part 2
def daily_hw_use(low_water_use, Nocc):
    if low_water_use:
        return (25. * Nocc + 36.) * .95
    else:
        return 25. * Nocc + 36.


# Table 1c
MONTHLY_HOT_WATER_FACTORS = numpy.array([1.1, 1.06, 1.02, 0.98, 0.94, 0.9, 0.9, 0.94, 0.98, 1.02, 1.06, 1.1])

# Table 1d
MONTHLY_HOT_WATER_TEMPERATURE_RISE = numpy.array(
        [41.2, 41.4, 40.1, 37.6, 36.4, 33.9, 30.4, 33.4, 33.5, 36.3, 39.4, 39.9])


# Table 2
def hw_storage_loss_factor(hw_cylinder_insulation_type, hw_cylinder_insulation):
    """
    Calculate Hot water storage loss factor according to equation in Note 1.
    of Table 2 (rather than usring the tabulated values)

    :param hw_cylinder_insulation_type: a CylinderInsulationTypes
    :param hw_cylinder_insulation: thickness of cylinder insulation
    :return: hot water storage loss factor
    """
    if hw_cylinder_insulation_type == CylinderInsulationTypes.FOAM:
        return 0.005 + 0.55 / (hw_cylinder_insulation + 4)
    else:
        return 0.005 + 1.76 / (hw_cylinder_insulation + 12.8)


# Table 2a
def hw_volume_factor(cylinder_volume):
    """
    Calculate the volume factor according to equation in Note 2. of Table 2a

    :param cylinder_volume: volume of hot water cylinder
    :return: hot water volume factor
    """
    return (120. / cylinder_volume) ** (1.0 / 3.0)


# Table 2b
# Table 2b is actually a table of functions. Define the functions first and add them
# to a dict lookup to give the table

def constant(k):
    return lambda d: k


def cylinder_indirect(dwelling):
    temperature_factor = 0.6
    if exists_and_true(dwelling, 'has_hw_time_control'):
        temperature_factor *= 0.9
    if not dwelling.has_cylinderstat:
        temperature_factor *= 1.3

    return temperature_factor


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
    """
    Calculate the hot water temperature factor

    :param dwelling: dwelling object
    :param measured_loss: boolean, whether the losses are measured by manufacturer or must be assumed
    :return:
    """
    table2b = TABLE_2b_manuf if measured_loss else TABLE_2b_table2
    return table2b[dwelling.water_sys.table2b_row](dwelling)


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
    # system.table2b_row=5
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
                table2b_row=int(row[7]) if row[7] != '' else -1,
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
                table2b_row=int(row[7]) if row[7] != '' else -1)

    if sys['code'] in systems:
        systems[sys['code']].append(sys)
    else:
        systems[sys['code']] = [sys, ]


TABLE_4A = csv_to_dict(os.path.join(_DATA_FOLDER, 'table_4a.csv'), translate_4a_row)


# Table 4b
def translate_4b_row(systems, row):
    sys = dict(
            code=int(row[0]),
            type=row[1],
            effy_winter=float(row[1]),
            effy_summer=float(row[2]),
            table2b_row=int(row[3]),
            fraction_of_heat_from_secondary=.1,
            responsiveness=USE_TABLE_4D_FOR_RESPONSIVENESS,
            flue_fan=row[4],
            boiler_type=int(row[5]),
            condensing=row[6] == "TRUE",
            warm_air_fan="FALSE")
    systems[sys['code']] = sys


TABLE_4B = csv_to_dict(os.path.join(_DATA_FOLDER, 'table_4b.csv'), translate_4b_row)

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

# Table 4d
TABLE_4D = {
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
        # table_no = re.match(r'Table 4c\((\d)\)', other_adjustments_str)
        # other_adj_table = globals()['apply_4c%s' % (table_no.group(1),)]
        other_adj_table = other_adjustments_str.lower()
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


def get_4a_system(electricity_tariff, code):
    matches = TABLE_4A[code]
    if len(matches) > 1:
        assert len(matches) == 2
        # Electric storage heaters appear twice with the same code -
        # once for off peak, once for 24 hour tariffs.
        if electricity_tariff == ELECTRICITY_24HR:
            return matches[1]
        else:
            assert (electricity_tariff == ELECTRICITY_10HR or
                    electricity_tariff == ELECTRICITY_7HR)
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


T4C4_SPACE_EFFY_MULTIPLIERS = {
    HeatEmitters.RADIATORS: 0.7,
    # !!!Need to check for presence of load compensator! (also for the rads+underfloor cases)
    HeatEmitters.UNDERFLOOR_TIMBER: 1.0,
    HeatEmitters.UNDERFLOOR_SCREED: 1.0,
    HeatEmitters.UNDERFLOOR_CONCRETE: 1.0,
    HeatEmitters.RADIATORS_UNDERFLOOR_TIMBER: 0.7,
    HeatEmitters.RADIATORS_UNDERFLOOR_SCREED: 0.7,
    HeatEmitters.RADIATORS_UNDERFLOOR_CONCRETE: 0.7,
    HeatEmitters.FAN_COILS: 0.85,
}


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

    if exists_and_true(dwelling,
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

# FIXME: if it's possible to swap the PCDF file, make this explicit!
# Lazy load these, to give a chance to swap the pcdf database file if necessary


def default_in_use_factor():
    return 2.5


def default_hr_effy_factor():
    return 0.7


# Table 5a
# !!! NEED TO FINISH THIS!
def has_oil_pump_inside(dwelling):
    return (
        exists_and_true(dwelling, 'main_heating_oil_pump_inside_dwelling')
        or
        exists_and_true(dwelling, 'main_heating_2_oil_pump_inside_dwelling'))


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
    if exists_and_true(dwelling,
                       'has_fans_for_positive_input_vent_from_outside'):
        assert (False)
    if exists_and_true(dwelling,
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


def summer_to_annual(summer_vals):
    return numpy.array([0, ] * 5 + [float(s) for s in summer_vals] + [0, ] * 4)


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


def table_n4_heating_days(psr):
    data = interpolate_psr_table(psr, TABLE_N4)
    N24_16 = int(0.5 + data[1])
    N24_9 = int(0.5 + data[2])
    N16_9 = int(0.5 + data[3])
    return N24_16, N24_9, N16_9


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


# !!! Needs completing
def get_seasonal_effy_offset(is_modulating_burner,
                             fuel,
                             boiler_type):
    assert is_modulating_burner  # !!!
    return TABLE_D2_7[fuel.type][boiler_type]


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


def interpolate_efficiency(psr, psr_dataset):
    if psr > psr_dataset[-1]['psr']:
        raise SAPCalculationError("PSR too large for this system")
    if psr < psr_dataset[0]['psr']:
        raise SAPCalculationError("PSR too small for this system")

    return 1 / interpolate_psr_table(psr, psr_dataset,
                                     key=lambda x: x['psr'],
                                     data=lambda x: 1 / x['space_effy'])


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
