from sap.sap_table_4e import apply_4c1, apply_table_4e
from . import fuels
from .fuels import ELECTRICITY_STANDARD
from .heating_systems import pcdf_heating_system

# FIXME: we calculate on peak already inside
from .heating_system_types import DedicatedWaterSystem
from .heating_systems import immersion_on_peak_fraction, sedbuk_2005_heating_system, sedbuk_2009_heating_system
from .sap_tables import (TABLE_3, TABLE_4A, TABLE_4D, TABLE_4E, TABLE_6D, TABLE_10, TABLE_10C, get_4a_system, hw_volume_factor, hw_storage_loss_factor, hw_temperature_factor,
                         fans_and_pumps_gain, fans_and_pumps_electricity,
                         occupancy, daily_hw_use,
                         USE_TABLE_4D_FOR_RESPONSIVENESS, FLOOR_INFILTRATION)
from .sap_types import HeatingTypes, WallTypes

from .appendix import appendix_a
from .appendix.appendix_g import configure_wwhr, configure_fghr
from .appendix.appendix_h import configure_solar_hw
from .appendix.appendix_m import configure_pv, configure_wind_turbines

from .appendix.appendix_c import CommunityHeating
from .configure_ventilation import configure_ventilation


def configure_fuel_costs(dwelling):
    dwelling.general_elec_co2_factor = dwelling.electricity_tariff.co2_factor
    dwelling.general_elec_price = dwelling.electricity_tariff.unit_price(
            dwelling.electricity_tariff.general_elec_on_peak_fraction)
    dwelling.mech_vent_elec_price = dwelling.electricity_tariff.unit_price(
            dwelling.electricity_tariff.mech_vent_elec_on_peak_fraction)

    dwelling.general_elec_PE = dwelling.electricity_tariff.primary_energy_factor

    if dwelling.water_sys.summer_immersion:
        # Should this be here or in worksheet.py?
        # FIXME: we calculate on-peak inside heatingSystem, do we need to do it again?
        on_peak = immersion_on_peak_fraction(dwelling.Nocc,
                                             dwelling.electricity_tariff,
                                             dwelling.hw_cylinder_volume,
                                             dwelling.immersion_type)
        dwelling.water_fuel_price_immersion = dwelling.electricity_tariff.unit_price(on_peak)

    fuels = set()
    fuels.add(dwelling.main_sys_1.fuel)
    fuels.add(dwelling.water_sys.fuel)
    if dwelling.get("main_sys_2"):
        fuels.add(dwelling.main_sys_2.fuel)

    # Standing charge for electricity is only included if main heating or
    # hw uses electricity
    if (dwelling.get("secondary_sys") and
            not dwelling.secondary_sys.fuel.is_electric):
        fuels.add(dwelling.secondary_sys.fuel)

    if dwelling.get('use_immersion_heater_summer'):
        fuels.add(dwelling.electricity_tariff)

    standing_charge = 0
    for f in fuels:
        standing_charge += f.standing_charge
    dwelling.cost_standing = standing_charge


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

    # Hack because name for control and heating type codes are
    # e.g. "main_heating_type_code" instead of main_heating_1_type_code...
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
    if heat_type_code and 521 <= heat_type_code <= 527:
        system.water_mult = 0.7


def configure_main_system(dwelling):
    if dwelling.get('main_heating_pcdf_id') and dwelling.main_heating_pcdf_id is not None:
        dwelling.main_sys_1 = pcdf_heating_system(dwelling,
                                                  dwelling.main_heating_pcdf_id,
                                                  dwelling.main_sys_fuel,
                                                  dwelling.get( 'use_immersion_heater_summer', False))
        # !!! Might need to enforce a secondary system?
    elif (dwelling.get('sys1_sedbuk_2005_effy') and
                  dwelling.sys1_sedbuk_2005_effy is not None):

        dwelling.main_sys_1 = sedbuk_2005_heating_system(
                dwelling,
                dwelling.main_sys_fuel,
                dwelling.sys1_sedbuk_2005_effy,
                dwelling.get('sys1_sedbuk_range_case_loss_at_full_output'),
                dwelling.get('sys1_sedbuk_range_full_output'),
                dwelling.sys1_sedbuk_type,
                dwelling.sys1_sedbuk_fan_assisted,
                dwelling.get('use_immersion_heater_summer', False))

    elif dwelling.get('sys1_sedbuk_2009_effy') is not None:
        dwelling.main_sys_1 = sedbuk_2009_heating_system(
                dwelling,
                dwelling.main_sys_fuel,
                dwelling.sys1_sedbuk_2009_effy,
                dwelling.get('sys1_sedbuk_range_case_loss_at_full_output'),
                dwelling.get('sys1_sedbuk_range_full_output'),
                dwelling.sys1_sedbuk_type,
                True,  # !!! Assumes condensing
                dwelling.sys1_sedbuk_fan_assisted,
                dwelling.get('use_immersion_heater_summer', False))

    elif dwelling.get('main_heating_type_code') == "community":
        #TODO: Can Community can be second main system too?
        dwelling.main_sys_1 = CommunityHeating(
                dwelling.community_heat_sources,
                dwelling.get('sap_community_distribution_type'))
        dwelling.main_sys_fuel = dwelling.main_sys_1.fuel

    else:
        dwelling.main_sys_1 = appendix_a.sap_table_heating_system(
                dwelling,
                dwelling.main_heating_type_code,
                dwelling.main_sys_fuel,
                dwelling.use_immersion_heater_summer if dwelling.get('use_immersion_heater_summer') else False,
                dwelling.sys1_hetas_approved if dwelling.get('sys1_hetas_approved') else False)
        # !!! Should really check here for no main system specified, and
        # !!! use a default if that's the case


def configure_main_system_2(dwelling):
    """
    Load the 2nd main system from pcdf data if available, otherwise fallback to SAP table
    :param dwelling:
    :return:
    """
    # Sedbuk systems
    if dwelling.get('main_heating_2_pcdf_id') is not None:
        dwelling.main_sys_2 = pcdf_heating_system(dwelling,
                                                  dwelling.main_heating_2_pcdf_id,
                                                  dwelling.main_sys_2_fuel,
                                                  dwelling.get('use_immersion_heater_summer', False))

    # TODO: Might need to enforce a secondary system?
    elif dwelling.get('main_heating_2_type_code') is not None:
        dwelling.main_sys_2 = appendix_a.sap_table_heating_system(
                dwelling,
                dwelling.main_heating_2_type_code,
                dwelling.main_sys_2_fuel,
                dwelling.get('use_immersion_heater_summer', False),
                dwelling.get('sys2_hetas_approved', False))


def configure_water_system(dwelling):
    if dwelling.get('water_heating_type_code'):  # !!! Why this test?
        code = dwelling.water_heating_type_code

        if code in TABLE_4A:
            water_system = get_4a_system(dwelling.electricity_tariff, code)
            dwelling.water_sys = DedicatedWaterSystem(water_system['effy'],
                                                      dwelling.use_immersion_heater_summer if dwelling.get(
                                                              'use_immersion_heater_summer') else False)
            dwelling.water_sys.table2b_row = water_system['table2b_row']
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
                    dwelling.get('sap_community_distribution_type_dhw'))

            if dwelling.get('community_dhw_flat_rate_charging'):
                dwelling.water_sys.dhw_charging_factor = 1.05

            else:
                dwelling.water_sys.dhw_charging_factor = 1.0

            if dwelling.main_sys_1.system_type == HeatingTypes.community:
                # Standing charge already covered by main system
                dwelling.water_sys.fuel.standing_charge = 0

            else:
                # Only half of standing charge applies for DHW only
                dwelling.water_sys.fuel.standing_charge /= 2
        else:
            assert False


def configure_water_storage(dwelling):
    """
    Configure the water storage for the dwelling

    :param dwelling:
    :return:
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
            dwelling.temperature_factor = hw_temperature_factor(dwelling, True)

        else:
            # TODO Is this electric CPSU test in the right place?
            if (dwelling.water_sys.system_type == HeatingTypes.cpsu and
                    dwelling.water_sys.fuel.is_electric):
                dwelling.storage_loss_factor = 0.022

            elif not dwelling.get('storage_loss_factor'):
                # This is already set for community heating dhw
                dwelling.storage_loss_factor = hw_storage_loss_factor(dwelling.hw_cylinder_insulation_type,
                                                                      dwelling.hw_cylinder_insulation)
            dwelling.volume_factor = hw_volume_factor(dwelling.hw_cylinder_volume)
            dwelling.temperature_factor = hw_temperature_factor(dwelling, False)
        dwelling.primary_circuit_loss_annual = hw_primary_circuit_loss(dwelling)
    else:
        dwelling.storage_loss_factor = 0
        dwelling.volume_factor = 0
        dwelling.temperature_factor = 0
        dwelling.primary_circuit_loss_annual = 0


def configure_systems(dwelling):
    dwelling['community_heating_dhw'] = False
    dwelling['Nfluelessgasfires'] = 0
    if dwelling.get('main_heating_type_code') and dwelling.main_heating_type_code == 613:
        dwelling.Nfluelessgasfires += 1
    if dwelling.get('secondary_heating_type_code') and dwelling.secondary_heating_type_code == 613:
        dwelling.Nfluelessgasfires += 1

    configure_main_system(dwelling)
    configure_main_system_2(dwelling)
    # !!! fraction of heat from main 2 not specified, assume 0%
    if not dwelling.get('main_heating_fraction'):
        dwelling.main_heating_fraction = 1
        dwelling.main_heating_2_fraction = 0

    appendix_a.configure_secondary_system(dwelling)

    if dwelling.get('secondary_sys'):
        dwelling.fraction_of_heat_from_main = 1 - dwelling.main_sys_1.default_secondary_fraction
    else:
        dwelling.fraction_of_heat_from_main = 1

    configure_water_system(dwelling)
    configure_wwhr(dwelling)
    configure_fghr(dwelling)
    configure_water_storage(dwelling)

    configure_controls(dwelling)


def configure_controls(dwelling):
    if not dwelling.get('sys1_has_boiler_interlock'):
        # !!! Should really only be added for boilers, but I don't
        # !!! think it will do anything for other systems, so ok? (If
        # !!! it doesn't have a boiler then it doesn't have a boiler
        # !!! interlock?)

        # !!! Potentially different for main_1 & main_2?
        dwelling.sys1_has_boiler_interlock = False

    dwelling.main_sys_1.has_interlock = dwelling.sys1_has_boiler_interlock
    dwelling.water_sys.has_interlock = dwelling.hwsys_has_boiler_interlock if dwelling.get(
            'hwsys_has_boiler_interlock') else False

    if dwelling.water_sys.system_type in [HeatingTypes.combi,
                                          HeatingTypes.storage_combi]:
        dwelling.combi_loss = dwelling.water_sys.combi_loss

    if not dwelling.get('heating_control_type_sys1'):
        configure_control_system(dwelling, 1)
        control = TABLE_4E[dwelling.control_type_code]
        dwelling.temperature_adjustment = control['Tadjustment']
        dwelling.has_room_thermostat = (control['thermostat'] == "TRUE")
        dwelling.has_trvs = control['trv'] == "TRUE"

    if (dwelling.get('main_sys_2') and not dwelling.get('heating_control_type_sys2') and
                dwelling.get("control_2_type_code") != 2100):
        configure_control_system(dwelling, 2)


def configure_fans_and_pumps(dwelling):
    fans_and_pumps_gain(dwelling)
    fans_and_pumps_electricity(dwelling)

    configure_responsiveness(dwelling)
    configure_fuel_costs(dwelling)


def configure_cooling_system(dwelling):
    if dwelling.get('cooled_area') and dwelling.cooled_area > 0:
        dwelling.fraction_cooled = dwelling.cooled_area / dwelling.GFA

        if dwelling.get("cooling_tested_eer"):
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


def get_table3_row(dwelling):
    """
    Get the row number from Table 3 for the given dwelling
    by finding the row corresponding to the dwellings' combination of heating
    type codes and thermal storage.

    This implements the logic of section 4.2 Storage loss, and is used through the
    hw_primary_circuit_loss function

    :param dwelling:
    :return:
    """
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

    elif dwelling.get('cylinder_is_thermal_store'):
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
    """
    Hot water primary circuit losses according to the logic described in
    Section 4.2.

    :param dwelling:
    :return:
    """
    table3row = get_table3_row(dwelling)
    return TABLE_3[table3row]


def set_regional_properties(dwelling):
    region = dwelling['sap_region']
    dwelling['external_temperature_summer'] = TABLE_10[region]['external_temperature']
    dwelling['Igh_summer'] = TABLE_10[region]['solar_radiation']
    dwelling['latitude'] = TABLE_10[region]['latitude']


def set_infiltration(dwelling):
    if dwelling.get("wall_type"):
        dwelling['structural_infiltration'] = 0.35 if dwelling.wall_type == WallTypes.MASONRY else 0.25

    if dwelling.get('floor_type'):
        dwelling['floor_infiltration'] = FLOOR_INFILTRATION[dwelling.floor_type]


def set_overshading_factors(dwelling):
    """
    Set dwelling overshading factors from Table 6D, based on the shading amount

    :param dwelling:
    :return:
    """
    overshading_factors = TABLE_6D[dwelling.overshading]
    dwelling['light_access_factor'] = overshading_factors["light_access_factor"]
    dwelling['solar_access_factor_winter'] = overshading_factors["solar_access_factor_winter"]
    dwelling['solar_access_factor_summer'] = overshading_factors["solar_access_factor_summer"]


def lookup_sap_tables(dwelling):
    """
    Lookup data from SAP tables for given dwelling

    :param dwelling:
    :return:
    """

    # FIXME: You'd think you'd always want PCDF prices, but apparently this was not set and as result was usually False
    if dwelling.get('use_pcdf_fuel_prices'):
        fuels.PREFER_PCDF_FUEL_PRICES = True
    else:
        fuels.PREFER_PCDF_FUEL_PRICES = False

    # Fix up fuel types
    if dwelling.get('water_sys_fuel') == ELECTRICITY_STANDARD:
        dwelling['water_sys_fuel'] = dwelling.electricity_tariff

    if dwelling.get('secondary_sys_fuel') == ELECTRICITY_STANDARD:
        dwelling['secondary_sys_fuel'] = dwelling.electricity_tariff

    dwelling['Nocc'] = occupancy(dwelling.GFA)
    dwelling['daily_hot_water_use'] = daily_hw_use(dwelling.low_water_use, dwelling.Nocc)

    set_regional_properties(dwelling)

    if not dwelling.get('living_area_fraction'):
        dwelling['living_area_fraction'] = dwelling.living_area / dwelling.GFA

    set_infiltration(dwelling)
    set_overshading_factors(dwelling)

    configure_ventilation(dwelling)
    configure_systems(dwelling)
    configure_cooling_system(dwelling)
    configure_pv(dwelling)
    configure_solar_hw(dwelling)
    configure_wind_turbines(dwelling)
    configure_fans_and_pumps(dwelling)

    # Bit of a special case here!
    if dwelling.get('reassign_systems_for_test_case_30'):
        # FIXME @Andy: Basically, I have no idea what happens here
        assert False

    if dwelling.get('next_stage'):
        print('warning, calc stage thing enabled no idea what it does')
        dwelling.next_stage()
