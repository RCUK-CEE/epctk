from .cooling import configure_cooling_system
from .domestic_hot_water import hw_primary_circuit_loss
from .utils import SAPInputError
from . import fuels
from .fuels import ELECTRICITY_STANDARD
from .constants import USE_TABLE_4D_FOR_RESPONSIVENESS
from .domestic_hot_water import get_water_heater
from .elements import HeatingTypes
from .fuel_use import configure_fuel_costs
from .heating_loaders import sedbuk_2005_heating_system, sedbuk_2009_heating_system, pcdf_heating_system
from .solar import overshading_factors
from .tables import (table_1b_occupancy, table_1b_daily_hot_water, TABLE_10, table_2a_hot_water_vol_factor,
                     table_2_hot_water_store_loss_factor, table_2b_hot_water_temp_factor,
                     TABLE_4D, TABLE_4E, table_4f_fans_pumps_keep_hot, apply_table_4e,
                     table_5a_fans_and_pumps_gain)
from .ventilation import ventilation_properties, infiltration
from .appendix import appendix_a, appendix_c, appendix_g, appendix_h, appendix_m


def lookup_sap_tables(dwelling):
    """
    Lookup data from SAP tables for given dwelling

    .. note::
        This modifies the input dwelling! The dwelling is returned anyway
        In the future, shift to "immutable" style where the copies are always
        returned without modifying input data, enabling a "pipeling" style
        workflow and easier testing of partially configured dwellings

    Args:
        dwelling input dwelling data

    Returns:
        dwelling where input data has been converted to configured
        dwelling elements, values converted, sap table lookups performed, etc

        NOTE that this also MODIFIES the inputs.
    """

    # FIXME: use of global variable is a problem!
    if dwelling.get('use_pcdf_fuel_prices'):
        fuels.PREFER_PCDF_FUEL_PRICES = True
    else:
        fuels.PREFER_PCDF_FUEL_PRICES = False

    if dwelling.get('hw_cylinder_volume', 0) > 0:
        dwelling.has_cylinderstat = True

    # Fix up fuel types
    if dwelling.get('water_sys_fuel') == ELECTRICITY_STANDARD:
        dwelling.water_sys_fuel = dwelling.electricity_tariff

    if dwelling.get('secondary_sys_fuel') == ELECTRICITY_STANDARD:
        dwelling.secondary_sys_fuel = dwelling.electricity_tariff

    dwelling.Nocc = table_1b_occupancy(dwelling.GFA)
    dwelling.daily_hot_water_use = table_1b_daily_hot_water(dwelling.Nocc, dwelling.low_water_use)

    set_regional_properties(dwelling)

    if not dwelling.get('living_area_fraction'):
        dwelling.living_area_fraction = dwelling.living_area / dwelling.GFA

    # Add infiltration factors
    dwelling.update(infiltration(wall_type=dwelling.get("wall_type"),
                                 floor_type=dwelling.get("floor_type")))

    dwelling.update(ventilation_properties(dwelling))

    # Add overshading factors
    dwelling.update(overshading_factors(dwelling.overshading))

    # TODO: change the following to return dicts of properties to extend the dwelling definition
    configure_heat_systems(dwelling)
    configure_cooling_system(dwelling)

    appendix_m.configure_wind_turbines(dwelling)
    appendix_m.configure_pv(dwelling)
    appendix_h.configure_solar_hw(dwelling)

    configure_fans_and_pumps(dwelling)

    # Bit of a special case here!
    if dwelling.get('reassign_systems_for_test_case_30'):
        # FIXME @Andy: Basically, I have no idea what happens here
        raise SAPInputError("reassign_systems_for_test_case_30  was set but no idea why it should do!")

    dwelling.update(fix_misc_configuration(dwelling))

    return dwelling


def fix_misc_configuration(dwelling):
    # FIXME: dump for various special case fixes that are pulled from elsewhere. Cleanup!

    if not dwelling.get('thermal_mass_parameter'):
        ka = 0
        for t in dwelling.thermal_mass_elements:
            ka += t.area * t.kvalue
        thermal_mass_parameter = ka / dwelling.GFA
    else:
        thermal_mass_parameter = dwelling['thermal_mass_parameter']

    living_area_fraction = dwelling.get('living_area_fraction')
    if not living_area_fraction:
        living_area_fraction = dwelling.living_area / dwelling.GFA

    return dict(thermal_mass_parameter=thermal_mass_parameter, living_area_fraction=living_area_fraction)


def configure_responsiveness(dwelling):
    if dwelling.main_sys_1.responsiveness == USE_TABLE_4D_FOR_RESPONSIVENESS:
        sys1_responsiveness = dwelling.heating_responsiveness = TABLE_4D[dwelling.heating_emitter_type]
    else:
        sys1_responsiveness = dwelling.main_sys_1.responsiveness

    if dwelling.get('main_sys_2') and dwelling.main_heating_2_fraction > 0:
        if dwelling.main_sys_2.responsiveness == USE_TABLE_4D_FOR_RESPONSIVENESS:
            sys2_responsiveness = dwelling.heating_responsiveness = TABLE_4D[dwelling.heating_emitter_type2]
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


def configure_control_system(dwelling, system_num):
    """

    Args:
        dwelling:
        system_num: 1 for main system 1, 2 for main system 2

    Returns:

    """
    if system_num not in [1, 2]:
        raise ValueError('Main system number must be 1 or 2, not {}'.format(system_num))

    system = dwelling.get('main_sys_{}'.format(system_num))

    # Hack because name for control and heating type codes are:
    # "main_heating_type_code" instead of main_heating_1_type_code, similar for control
    sub = "_" + str(system_num) if system_num == 2 else ""

    control = TABLE_4E[dwelling.get('control' + sub + '_type_code')]
    system.heating_control_type = control['control_type']

    dwelling['heating_control_type_sys{}'.format(system_num)] = control['control_type']

    other_adj_table = control.get('other_adj_table')
    if other_adj_table is not None:
        apply_table_4e(other_adj_table, dwelling, system, system_num)

    # TODO Special case table 4c4 for warm air heat pumps - needs to apply to sys2 too
    # TODO Should only apply if water is from this system!!
    heat_type_code = dwelling.get('main_heating' + sub + '_type_code')
    if heat_type_code and heat_type_code != 'community' and 521 <= heat_type_code <= 527:
        system.water_mult = 0.7


def configure_main_system_1(dwelling):
    """
    Configure the main heating system.


    Args:
        dwelling:

    Returns:

    """

    use_immersion_heater_summer = dwelling.get('use_immersion_heater_summer', False)
    heating_type_code = dwelling.get('main_heating_type_code')

    fuel = dwelling.get('main_sys_fuel')

    pcdf_id = dwelling.get('main_heating_pcdf_id')

    sedbuk_range_case_loss = dwelling.get('sys1_sedbuk_range_case_loss_at_full_output')
    sedbuk_range = dwelling.get('sys1_sedbuk_range_full_output')
    sedbuk_type = dwelling.get('sys1_sedbuk_type')

    sedbuk_2005_effy = dwelling.get('sys1_sedbuk_2005_effy')
    sedbuk_2009_effy = dwelling.get('sys1_sedbuk_2009_effy')
    sedbuk_fan_assisted = dwelling.get('sys1_sedbuk_fan_assisted')

    hw_cylinder_volume = dwelling.get('hw_cylinder_volume', 0)
    cpsu_not_in_airing_cupboard = dwelling.get('cpsu_not_in_airing_cupboard', False)

    if pcdf_id is not None:
        main_sys = pcdf_heating_system(dwelling,
                                       pcdf_id,
                                       fuel,
                                       use_immersion_heater_summer)
    # !!! Might need to enforce a secondary system?
    elif sedbuk_2005_effy is not None:
        main_sys = sedbuk_2005_heating_system(fuel, sedbuk_2005_effy, sedbuk_range_case_loss, sedbuk_range, sedbuk_type,
                                              sedbuk_fan_assisted, use_immersion_heater_summer,
                                              hw_cylinder_volume,
                                              cpsu_not_in_airing_cupboard)

    elif sedbuk_2009_effy is not None:
        main_sys = sedbuk_2009_heating_system(fuel, sedbuk_2009_effy, sedbuk_range_case_loss, sedbuk_range, sedbuk_type,
                                              True, sedbuk_fan_assisted, use_immersion_heater_summer,
                                              hw_cylinder_volume,
                                              cpsu_not_in_airing_cupboard)

    elif heating_type_code == "community":
        # TODO: Can Community can be second main system too?
        main_sys = appendix_c.CommunityHeating(
            dwelling.community_heat_sources,
            dwelling.get('sap_community_distribution_type'))

        dwelling.main_sys_fuel = main_sys.fuel

    else:
        main_sys = appendix_a.sap_table_heating_system(
            dwelling,
            heating_type_code,
            fuel,
            use_immersion_heater_summer,
            dwelling.get('sys1_hetas_approved', False))

    # TODO Should check here for no main system specified, and use a default if that's the case
    if main_sys is None:
        raise RuntimeError('Main system 1 cannot be None')

    # TODO: convert assignment to return value...
    dwelling.main_sys_1 = main_sys


def configure_main_system_2(dwelling):
    """
    Load the 2nd main system from pcdf data if available, otherwise fallback to SAP table
    :param dwelling:
    :return:
    """
    # TODO: Sedbuk systems
    main_system = None

    if dwelling.get('main_heating_2_pcdf_id') is not None:
        main_system = pcdf_heating_system(dwelling,
                                          dwelling.main_heating_2_pcdf_id,
                                          dwelling.main_sys_2_fuel,
                                          dwelling.get('use_immersion_heater_summer', False))

    # TODO: Might need to enforce a secondary system?
    elif dwelling.get('main_heating_2_type_code') is not None:
        main_system = appendix_a.sap_table_heating_system(
            dwelling,
            dwelling.main_heating_2_type_code,
            dwelling.main_sys_2_fuel,
            dwelling.get('use_immersion_heater_summer', False),
            dwelling.get('sys2_hetas_approved', False))

    dwelling.main_sys_2 = main_system


def configure_water_storage(dwelling):
    """
    Configure the water storage for the dwelling

    Args:
        dwelling:

    """
    if dwelling.water_sys.is_community_heating:
        dwelling.has_cylinderstat = True
        dwelling.community_heating_dhw = True  # use for table 3
        # Community heating
        if not dwelling.get('hw_cylinder_volume'):
            dwelling.hw_cylinder_volume = 110
            dwelling.storage_loss_factor = 0.0152

    if dwelling.water_heating_type_code in [907, 908, 909]:
        dwelling.instantaneous_pou_water_heating = True
        dwelling.has_hw_cylinder = False
        dwelling.primary_circuit_loss_annual = 0

    elif dwelling.has_hw_cylinder:
        if dwelling.get("measured_cylinder_loss") is not None:
            dwelling.temperature_factor = table_2b_hot_water_temp_factor(dwelling, True)

        else:
            # TODO Is this electric CPSU test in the right place?
            if (dwelling.water_sys.system_type == HeatingTypes.cpsu and
                    dwelling.water_sys.fuel.is_electric):
                dwelling.storage_loss_factor = 0.022

            elif not dwelling.get('storage_loss_factor'):
                # This is already set for community heating dhw
                dwelling.storage_loss_factor = table_2_hot_water_store_loss_factor(dwelling.hw_cylinder_insulation_type,
                                                                                   dwelling.hw_cylinder_insulation)

            dwelling.volume_factor = table_2a_hot_water_vol_factor(dwelling.hw_cylinder_volume)
            dwelling.temperature_factor = table_2b_hot_water_temp_factor(dwelling, False)

        dwelling.primary_circuit_loss_annual = hw_primary_circuit_loss(dwelling)
    else:
        dwelling.storage_loss_factor = 0
        dwelling.volume_factor = 0
        dwelling.temperature_factor = 0
        dwelling.primary_circuit_loss_annual = 0


def configure_controls(dwelling):
    """
    Configure the heating system controls. Requires that the main heating systems
    (main_sys_1 and optionally main_sys_2) have been configured first.

    Args:
        dwelling:

    Returns:

    """
    if not dwelling.get('sys1_has_boiler_interlock'):
        #  Should really only be added for boilers, but I don't
        #  think it will do anything for other systems, so ok? (If
        #  it doesn't have a boiler then it doesn't have a boiler
        #  interlock?)

        # FIXME Potentially different for main_1 & main_2?
        dwelling.sys1_has_boiler_interlock = False

    dwelling.main_sys_1.has_interlock = dwelling.sys1_has_boiler_interlock
    dwelling.water_sys.has_interlock = dwelling.get('hwsys_has_boiler_interlock', False)

    if dwelling.water_sys.system_type in [HeatingTypes.combi,
                                          HeatingTypes.storage_combi]:
        dwelling.combi_loss = dwelling.water_sys.combi_loss

    if not dwelling.get('heating_control_type_sys1'):
        control = TABLE_4E[dwelling.control_type_code]
        dwelling.temperature_adjustment = control['Tadjustment']
        dwelling.has_room_thermostat = (control['thermostat'] == "TRUE")
        dwelling.has_trvs = control['trv'] == "TRUE"

        configure_control_system(dwelling, 1)

    if (dwelling.get('main_sys_2') and not dwelling.get('heating_control_type_sys2') and
                dwelling.get("control_2_type_code") != 2100):
        configure_control_system(dwelling, 2)


def configure_water(dwelling):
    dwelling.water_sys = get_water_heater(dwelling)

    appendix_g.configure_wwhr(dwelling)
    appendix_g.configure_fghr(dwelling)
    configure_water_storage(dwelling)


def configure_heat_systems(dwelling):
    """
    Configure space and water heating systems

    Args:
        dwelling:

    Returns:

    """
    dwelling['community_heating_dhw'] = False
    dwelling['Nfluelessgasfires'] = 0

    if dwelling.get('main_heating_type_code') and dwelling.main_heating_type_code == 613:
        dwelling.Nfluelessgasfires += 1

    if dwelling.get('secondary_heating_type_code') and dwelling.secondary_heating_type_code == 613:
        dwelling.Nfluelessgasfires += 1

    configure_main_system_1(dwelling)
    configure_main_system_2(dwelling)

    # !!! fraction of heat from main 2 not specified, assume 0%
    if not dwelling.get('main_heating_fraction'):
        dwelling.main_heating_fraction = 1
        dwelling.main_heating_2_fraction = 0

    # Apply Appendix A for the secondary heating system
    appendix_a.configure_secondary_system(dwelling, dwelling.get('force_secondary_heating', False))

    # Account for the heat provided by secondary system
    dwelling.fraction_of_heat_from_main = 1
    if dwelling.get('secondary_sys'):
        dwelling.fraction_of_heat_from_main -= dwelling.main_sys_1.default_secondary_fraction

    configure_water(dwelling)
    configure_controls(dwelling)


def configure_fans_and_pumps(dwelling):
    table_5a_fans_and_pumps_gain(dwelling)
    table_4f_fans_pumps_keep_hot(dwelling)

    configure_responsiveness(dwelling)
    configure_fuel_costs(dwelling)


def set_regional_properties(dwelling):
    region = dwelling['sap_region']
    dwelling['external_temperature_summer'] = TABLE_10[region]['external_temperature']
    dwelling['Igh_summer'] = TABLE_10[region]['solar_radiation']
    dwelling['latitude'] = TABLE_10[region]['latitude']
