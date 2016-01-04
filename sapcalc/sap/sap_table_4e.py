from sap.sap_tables import TABLE_4C3, T4C4_SPACE_EFFY_MULTIPLIERS
from sap.sap_types import LoadCompensators, HeatEmitters, HeatingTypes, ThermalStoreTypes, FuelTypes


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


def apply_table_4e(table_4c_subsection, dwelling, sys, sys_number):
    """
    Apply table 4e using the reference to the section of Table 4c (Table 4c(1), 4c(2)...)
    Runs the  apply function for the corresponding table using the given arguments

    .. todo:
      This requires the system number (1 or 2 = main system 1 or main system 2) to
      be explicitly specified. Should be possible to attach this metadata to the
      HeatingSystem object instead

    Args:
        table_4c_subsection:
        sys (HeatingSystem):
        dwelling:
        sys_number: The number of the main system (1 or 2)

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