"""
SAP Tables Part 4: 4, 4a-4h
===========================

Table 4e and 4c
~~~~~~~~~~~~~~~
Table 4e defines the efficiency adjustments to apply as a function
of the combination of heating system and heating system controls installed.

"""
import os.path

from ..elements import LoadCompensators, HeatEmitters, HeatingTypes, ThermalStoreTypes, FuelTypes, VentilationTypes
from ..io.pcdf import TABLE_4h_in_use_approved_scheme, TABLE_4h_in_use, TABLE_4h_hr_effy_approved_scheme, \
    TABLE_4h_hr_effy
from ..constants import USE_TABLE_4D_FOR_RESPONSIVENESS
from ..fuels import ELECTRICITY_24HR, ELECTRICITY_10HR, ELECTRICITY_7HR
from ..utils import float_or_zero, csv_to_dict


_DATA_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'data')

def apply_table_4e(table_4c_subsection, dwelling, sys, sys_number):
    """
    Apply table 4e using the reference to the section of Table 4c (Table 4c(1), 4c(2)...)
    Runs the  apply function for the corresponding table using the given arguments

    .. todo:
      This requires the system number (1 or 2 = main system 1 or main system 2) to
      be explicitly specified. Should be possible to attach this metadata to the
      HeatingSystem object instead

    Args:
        table_4c_subsection: name of table 4c subsection as found in column 4 of Table 4e
        sys (HeatingSystem):
        dwelling (Dwelling):
        sys_number: The number of the main system: 1 for main_sys_1 or 2 for main_sys_2

    """
    if table_4c_subsection == 'Table 4c(1)'.lower():
        apply_4c1(dwelling, sys)

    elif table_4c_subsection == 'Table 4c(2)'.lower():
        apply_4c2(dwelling, sys)
        load_comp_varname = "sys{}_load_compensator".format(sys_number)
        apply_4c1(dwelling, sys, load_compensator=dwelling.get(load_comp_varname))

    elif table_4c_subsection == 'Table 4c(3)'.lower():
        apply_4c3(dwelling, sys)

    elif table_4c_subsection == 'Table 4c(4)'.lower():
        apply_4c4(dwelling, sys)

def apply_load_compensator(sys, compensator_type):
    if compensator_type in [LoadCompensators.ENHANCED_LOAD_COMPENSATOR,
                            LoadCompensators.WEATHER_COMPENSATOR]:
        if sys.fuel.is_mains_gas:
            sys.space_adj += 3
        else:
            sys.space_adj += 1.5


def apply_4c1(dwelling, sys, load_compensator=None):
    """
    Gas or oil boiler systems with radiators or underfloor heating:
    Efficiency adjustment due to lower temperature of distribution system

    Args:
        dwelling:
        sys:
        load_compensator:

    Returns:

    """
    if sys.get("is_condensing"):
        return  # no corrections apply

    if sys is dwelling.water_sys and dwelling.get('fghrs') is not None:
        # Can't have the effy adjustment if the system has an fghrs
        return

    # FIXME Can have different emitter types for different systems
    if (dwelling.heating_emitter_type in [HeatEmitters.UNDERFLOOR_TIMBER,
                                          HeatEmitters.UNDERFLOOR_SCREED,
                                          HeatEmitters.UNDERFLOOR_CONCRETE] and
                sys is not dwelling.water_sys):
        if sys.fuel.is_mains_gas:
            sys.space_adj += 3
        else:
            sys.space_adj += 2
    elif load_compensator is not None:
        apply_load_compensator(sys, load_compensator)


def apply_4c2(dwelling, sys):
    """
    Gas or oil boiler systems with radiators or underfloor heating:
    Efficiency adjustment due to control system

    Apply Table 4c (2) adjustments to the dwelling and heating system by setting the appropriate
    attributes on the dwelling's heating system

    .. note:

      Actually not sure if these adjustments apply to solid fuel
      boilers? Case 15 suggests even solid fuel boilers without
      thermostatic control have an effy penalty.  But the
      interlock penalty is definitely just for gas and oil
      boilers.
      Probable answer to above question: see end of section 9.3.9

    Args:
        dwelling (Dwelling): dwelling object
        sys (HeatingSystem): heating system object
    """

    # TODO This entire function needs to be independent of sys1/sys2!

    # TODO Need to check  main_sys_2 here as well?
    if (dwelling.main_sys_1.system_type == HeatingTypes.cpsu or
            (dwelling.get('thermal_store_type') == ThermalStoreTypes.INTEGRATED)):
        dwelling.temperature_adjustment -= 0.1

    # !!! Also check sys2!
    if dwelling.get("sys1_delayed_start_thermostat"):
        dwelling.temperature_adjustment -= .15

    if sys.fuel.type not in [FuelTypes.GAS,
                             FuelTypes.OIL,
                             FuelTypes.SOLID]:
        return

    apply_adjustment = False
    if not (dwelling.has_room_thermostat or dwelling.has_trvs):
        # Applies for all boilers
        apply_adjustment = True

    elif (sys.fuel.type in [FuelTypes.GAS, FuelTypes.OIL] and
              (not dwelling.sys1_has_boiler_interlock or not
              dwelling.has_room_thermostat)):
        apply_adjustment = True

    # if boiler interlock variable is set and is false, apply adjustment
    elif dwelling.water_sys is sys and dwelling.get("hwsys_has_boiler_interlock", False) is False:
        apply_adjustment = True

    if apply_adjustment:
        space_heat_effy_adjustment = -5
        if dwelling.water_sys.system_type not in [HeatingTypes.combi,
                                                  HeatingTypes.cpsu,
                                                  HeatingTypes.storage_combi]:
            dhw_heat_effy_adjustment = -5
        else:
            dhw_heat_effy_adjustment = 0

        # !!! These adjustments need to be applied to the correct system
        # !!! (main 1 or main 2) - also confusion with water_sys
        dwelling.main_sys_1.space_adj = space_heat_effy_adjustment
        dwelling.main_sys_1.water_adj = dhw_heat_effy_adjustment


def apply_4c3(dwelling, sys):
    """
    Community heating systems, (control code as defined in Table 4e)

    Args:
        dwelling:
        sys:

    Returns:

    """
    # !!! Assumes community heating is system 1.  Also need DHW factor
    sys.space_heat_charging_factor = TABLE_4C3[dwelling.control_type_code][0]
    sys.dhw_charging_factor = TABLE_4C3[dwelling.control_type_code][1]


def apply_4c4(dwelling, sys):
    """
    Heat pumps

    Efficiency adjustment due to temperature of heat supplied where the
    efficiency is from Table 4a (not applied if from database)

    Args:
        dwelling:
        sys:

    Returns:

    """
    # TODO: Also need to check main sys 2?
    e = dwelling.heating_emitter_type
    dwelling.main_sys_1.space_mult = TABLE_4C4[e]

    if (dwelling.main_sys_1.space_mult == 0.7 and
            dwelling.get("sys1_load_compensator") in [LoadCompensators.ENHANCED_LOAD_COMPENSATOR,
                                                      LoadCompensators.WEATHER_COMPENSATOR]):
        dwelling.main_sys_1.space_mult = 0.75

    if dwelling.water_sys is sys:
        # !!! This assumes it supplies all of the DHW - also need the 50% case
        dwelling.water_sys.water_mult = 0.7



# Table 4a
# FIXME Electric storage systems - offpeak and 24 hour tariff systems have same type codes!

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
        # Hot Water system
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

# SPACE efficiency Multipliers
TABLE_4C4 = {
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


def has_oil_pump(dwelling):

    return (dwelling.main_sys_1.has_oil_pump or
            (dwelling.get('main_sys_2') and
             dwelling.main_heating_2_fraction > 0 and
             dwelling.main_sys_2.has_oil_pump))


def heating_fans_and_pumps_electricity(dwelling):
    """
    Table 4f

    Args:
        dwelling:

    Returns:

    """
    Qfansandpumps = 0
    if (dwelling.main_sys_1.has_ch_pump or
            (dwelling.get('main_sys_2') and dwelling.main_sys_2.has_ch_pump)):
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
    if dwelling.water_sys.get("keep_hot_elec_consumption"):
        Qfansandpumps += dwelling.water_sys.keep_hot_elec_consumption

    if dwelling.get('has_electric_shw_pump'):
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


def table_4f_fans_pumps_keep_hot(dwelling):
    """
    Table 4f: Electricity for fans and pumps and electric keep-hot facility

    Args:
        dwelling:

    Returns:

    """
    dwelling.Q_fans_and_pumps = heating_fans_and_pumps_electricity(dwelling)
    dwelling.Q_mech_vent_fans = mech_vent_fans_electricity(dwelling)

# ------------------------------------
# Following functions describe Table 4h
def mech_vent_default_in_use_factor():
    """
    Default In-use factor for Specific fan power

    """
    return 2.5


def mech_vent_default_hr_effy_factor():
    """
    Default efficiency for mechanical ventilation with heat recovery

    :return:
    """
    return 0.7


def mech_vent_in_use_factor(vent_type, duct_type, approved_scheme):
    """
    Table 4h: In-use factors for mechanical ventilation systems

    :param vent_type:
    :param duct_type:
    :param approved_scheme:
    :return:
    """

    if approved_scheme:
        return TABLE_4h_in_use_approved_scheme[vent_type][duct_type]
    else:
        return TABLE_4h_in_use[vent_type][duct_type]


def mech_vent_in_use_factor_hr(vent_type, duct_type, approved_scheme):
    """
    Table 4h: In-use factors for mechanical ventilation systems with heat recovery

    :param vent_type:
    :param duct_type:
    :param approved_scheme:
    :return:
    """

    if approved_scheme:
        return TABLE_4h_hr_effy_approved_scheme[vent_type][duct_type]
    else:
        return TABLE_4h_hr_effy[vent_type][duct_type]