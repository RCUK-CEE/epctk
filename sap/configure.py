
from . import fuels
from .fuels import ELECTRICITY_STANDARD
from .heating_systems import HeatingSystem, DedicatedWaterSystem, immersion_on_peak_fraction, \
    SecondarySystem, CommunityHeating
from .pcdf import (get_wwhr_system, get_fghr_system, get_mev_system, get_boiler, get_solid_fuel_boiler,
                   get_twin_burner_cooker_boiler, get_heat_pump, get_microchp)
from .sap_tables import (TABLE_3, TABLE_4A, TABLE_4B, TABLE_4D, TABLE_4E, TABLE_6D, TABLE_10, TABLE_10C, TABLE_D7,
                         TABLE_H1, TABLE_H2, TABLE_H3, TABLE_H4, TABLE_4C3, T4C4_SPACE_EFFY_MULTIPLIERS,
                         get_seasonal_effy_offset,
                         combi_loss_table_3a, get_4a_system, hw_volume_factor, hw_storage_loss_factor, hw_temperature_factor,
                         fans_and_pumps_gain, fans_and_pumps_electricity,
                         m1_correction_factor, occupancy, daily_hw_use,
                         get_in_use_factor, default_in_use_factor, get_in_use_factor_hr,
                         default_hr_effy_factor, combi_loss_instant_without_keep_hot,
                         combi_loss_instant_with_timed_heat_hot, combi_loss_instant_with_untimed_heat_hot,
                         combi_loss_table_3c, combi_loss_table_3b,
                         USE_TABLE_4D_FOR_RESPONSIVENESS, get_effy, system_type_from_sap_code, )
from .sap_types import FuelTypes, HeatingTypes, WallTypes, ThermalStoreTypes, CylinderInsulationTypes, \
    VentilationTypes, DuctTypes, LoadCompensators, HeatEmitters
from .appendix_n import micro_chp_from_pcdf, heat_pump_from_pcdf
from .sap_constants import FLOOR_INFILTRATION
from .utils import exists_and_true


def apply_4c1(dwelling, sys, load_compensator):
    if not exists_and_true(sys, "is_condensing"):
        return  # no corrections apply

    if sys is dwelling.water_sys and dwelling.get('fghrs') is not None:
        # Can't have the effy adjustment if the system has an fghrs
        return

        # !!! Can have different emitter types for different systems
    if (dwelling.heating_emitter_type in [HeatEmitters.UNDERFLOOR_TIMBER,
                                          HeatEmitters.UNDERFLOOR_SCREED,
                                          HeatEmitters.UNDERFLOOR_CONCRETE] and
             sys is not dwelling.water_sys):
        if sys.fuel.is_mains_gas:
            sys.space_adj += 3
        else:
            sys.space_adj += 2
    elif load_compensator != None:
        apply_load_compensator(sys, load_compensator)


def apply_4c2(dwelling, sys):
    """
    Apply Table 4c (2) adjustments to the dwelling and heating system by setting the appropriate
    attributes on the dwelling's heating system

    .. note:

      Actually not sure if these adjustments apply to solid fuel
      boilers? Case 15 suggests even solid fuel boilers without
      thermostatic control have an effy penalty.  But the
      interlock penalty is definitely just for gas and oil
      boilers.
      Probable answer to above question: see end of section 9.3.9

    :param dwelling: dwelling object
    :param sys: heating system object
    :return:
    """


    # TODO This entire function needs to be independent of sys1/sys2!

    # TODO Need to check  main_sys_2 here as well?
    if (dwelling.main_sys_1.system_type == HeatingTypes.cpsu or
            (dwelling.get('thermal_store_type') and
                     dwelling.thermal_store_type == ThermalStoreTypes.INTEGRATED)):
        dwelling.temperature_adjustment -= 0.1

    # !!! Also check sys2!
    if exists_and_true(dwelling, "sys1_delayed_start_thermostat"):
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
    # !!! Assumes community heating is system 1
    # !!! Also need DHW factor
    sys.space_heat_charging_factor = TABLE_4C3[dwelling.control_type_code][0]
    sys.dhw_charging_factor = TABLE_4C3[dwelling.control_type_code][1]


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


def apply_table_4e(table_4c_subsection, *args):
    """
    Apply table 4e using the reference to the section of Table 4c (Table 4c(1), 4c(2)...)
    Runs the  apply function for the corresponding table using the given arguments

    :param table_4c_subsection:
    :param args: arguments to the apply function (normally dwelling, system). See apply_4c{1-4}
    :return:
    """
    if table_4c_subsection == 'Table 4c(1)'.lower():
        return apply_4c1(*args)
    if table_4c_subsection == 'Table 4c(2)'.lower():
        return apply_4c2(*args)
    if table_4c_subsection == 'Table 4c(3)'.lower():
        return apply_4c3(*args)
    if table_4c_subsection == 'Table 4c(4)'.lower():
        return apply_4c4(*args)


def apply_load_compensator(sys, compensator_type):
    if compensator_type in [LoadCompensators.ENHANCED_LOAD_COMPENSATOR,
                            LoadCompensators.WEATHER_COMPENSATOR]:
        if sys.fuel.is_mains_gas:
            sys.space_adj += 3
        else:
            sys.space_adj += 1.5


def configure_fuel_costs(dwelling):
    dwelling.general_elec_co2_factor = dwelling.electricity_tariff.co2_factor
    dwelling.general_elec_price = dwelling.electricity_tariff.unit_price(
            dwelling.electricity_tariff.general_elec_on_peak_fraction)
    dwelling.mech_vent_elec_price = dwelling.electricity_tariff.unit_price(
            dwelling.electricity_tariff.mech_vent_elec_on_peak_fraction)

    dwelling.general_elec_PE = dwelling.electricity_tariff.primary_energy_factor

    if dwelling.water_sys.summer_immersion:
        # Should this be here or in worksheet.py?
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
    if exists_and_true(dwelling, 'use_immersion_heater_summer'):
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



def configure_control_system1(dwelling, system):
    # !!! Need to check main sys 2 here
    control = TABLE_4E[dwelling.control_type_code]
    dwelling.temperature_adjustment = control['Tadjustment']
    dwelling.has_room_thermostat = (control['thermostat'] == "TRUE")
    dwelling.has_trvs = control['trv'] == "TRUE"

    dwelling.heating_control_type_sys1 = control['control_type']

    system.heating_control_type = control['control_type']

    other_adj_table = control.get('other_adj_table')
    if other_adj_table is not None:
        # _table_4e_fn_lookup[control['other_adj_table']](dwelling, dwelling.main_sys_1)
        apply_table_4e(other_adj_table, dwelling, dwelling.main_sys_1)

        if other_adj_table == 'Table 4c(2)':
            apply_4c1(dwelling, dwelling.main_sys_1, dwelling.get("sys1_load_compensator"))

    # !!! Special case table 4c4 for warm air heat pumps - needs
    # !!! to apply to sys2 too
    # !!! Should only apply if water is from this system!!
    if dwelling.get('main_heating_type_code') and 521 <= dwelling.main_heating_type_code <= 527:
        system.water_mult = 0.7


def configure_control_system2(dwelling, system):
    # !!! Duplication with function above !!!
    control = TABLE_4E[dwelling.control_2_type_code]

    dwelling.heating_control_type_sys2 = control['control_type']

    system.heating_control_type = control['control_type']

    other_adj_table = control.get('other_adj_table')
    if other_adj_table is not None:
        apply_table_4e(other_adj_table, dwelling, dwelling.main_sys_2)

        if other_adj_table == apply_4c2:
            apply_4c1(dwelling, system, dwelling.get("sys2_load_compensator"))

    # !!! Should only apply if water is from this system!!
    if (dwelling.get('main_heating_2_type_code') and
           dwelling.main_heating_2_type_code >= 521 and
           dwelling.main_heating_type_code <= 527):

        system.water_mult = 0.7


def configure_main_system(dwelling):
    if dwelling.get('main_heating_pcdf_id') and dwelling.main_heating_pcdf_id is not None:
        dwelling.main_sys_1 = pcdf_heating_system(dwelling,
                                                  dwelling.main_heating_pcdf_id,
                                                  dwelling.main_sys_fuel,
                                                  dwelling.use_immersion_heater_summer if dwelling.get(
                                                          'use_immersion_heater_summer') else False)
        # !!! Might need to enforce a secondary system?
    elif (dwelling.get('sys1_sedbuk_2005_effy') and
                  dwelling.sys1_sedbuk_2005_effy is not None):

        dwelling.main_sys_1 = sedbuk_2005_heating_system(
                dwelling,
                dwelling.main_sys_fuel,
                dwelling.sys1_sedbuk_2005_effy,
                dwelling.sys1_sedbuk_range_case_loss_at_full_output if dwelling.get(
                        'sys1_sedbuk_range_case_loss_at_full_output') else None,
                dwelling.sys1_sedbuk_range_full_output if dwelling.get('sys1_sedbuk_range_full_output') else None,
                dwelling.sys1_sedbuk_type,
                dwelling.sys1_sedbuk_fan_assisted,
                dwelling.use_immersion_heater_summer if dwelling.get('use_immersion_heater_summer') else False)

    elif dwelling.get('sys1_sedbuk_2009_effy') and dwelling.sys1_sedbuk_2009_effy is not None:
        dwelling.main_sys_1 = sedbuk_2009_heating_system(
                dwelling,
                dwelling.main_sys_fuel,
                dwelling.sys1_sedbuk_2009_effy,
                dwelling.sys1_sedbuk_range_case_loss_at_full_output if dwelling.get(
                        'sys1_sedbuk_range_case_loss_at_full_output') else None,
                dwelling.sys1_sedbuk_range_full_output if dwelling.get('sys1_sedbuk_range_full_output') else None,
                dwelling.sys1_sedbuk_type,
                True,  # !!! Assumes condensing
                dwelling.sys1_sedbuk_fan_assisted,
                dwelling.use_immersion_heater_summer if dwelling.get('use_immersion_heater_summer') else False)

    elif dwelling.get('main_heating_type_code') == "community":
        # !!! Can Community can be second main system too?
        dwelling.main_sys_1 = CommunityHeating(
                dwelling.community_heat_sources,
                (dwelling.sap_community_distribution_type
                 if dwelling.get('sap_community_distribution_type')
                 else None))
        dwelling.main_sys_fuel = dwelling.main_sys_1.fuel

    else:
        dwelling.main_sys_1 = sap_table_heating_system(
                dwelling,
                dwelling.main_heating_type_code,
                dwelling.main_sys_fuel,
                dwelling.use_immersion_heater_summer if dwelling.get('use_immersion_heater_summer') else False,
                dwelling.sys1_hetas_approved if dwelling.get('sys1_hetas_approved') else False)
        # !!! Should really check here for no main system specified, and
        # !!! use a default if that's the case


def configure_main_system_2(dwelling):
    # !!! Sedbuk systems

    if dwelling.get('main_heating_2_pcdf_id') and dwelling.main_heating_2_pcdf_id is not None:
        dwelling.main_sys_2 = pcdf_heating_system(dwelling,
                                                  dwelling.main_heating_2_pcdf_id,
                                                  dwelling.main_sys_2_fuel,
                                                  dwelling.use_immersion_heater_summer if dwelling.get(
                                                          'use_immersion_heater_summer') else False)
        # !!! Might need to enforce a secondary system?
    elif dwelling.get('main_heating_2_type_code') and dwelling.main_heating_2_type_code is not None:
        dwelling.main_sys_2 = sap_table_heating_system(
                dwelling,
                dwelling.main_heating_2_type_code,
                dwelling.main_sys_2_fuel,
                dwelling.use_immersion_heater_summer if dwelling.get('use_immersion_heater_summer') else False,
                dwelling.sys2_hetas_approved if dwelling.get('sys2_hetas_approved') else False)


def configure_secondary_system(dwelling):
    # !!! Need to apply the rules from A4 here - need to do this
    # before fraction_of_heat_from_main is set.  Also back boiler
    # should have secondary system - see section 9.2.8

    if dwelling.get('secondary_heating_type_code'):
        dwelling.secondary_sys = get_4a_secondary_system(dwelling)
    elif dwelling.get('secondary_sys_manuf_effy'):
        dwelling.secondary_sys = get_manuf_data_secondary_system(dwelling)

    # There must be a secondary system if electric storage heaters
    # or off peak underfloor electric
    if dwelling.get('main_heating_type_code'):
        if not dwelling.get('secondary_sys') and (
                    (401 <= dwelling.main_heating_type_code <= 408) or (
                                    421 <= dwelling.main_heating_type_code <= 425 and
                                dwelling.main_sys_fuel != ELECTRICITY_STANDARD)):
            # !!! Does 24 hour tariff count as being offpeak?
            dwelling.secondary_heating_type_code = 693
            dwelling.secondary_sys_fuel = dwelling.electricity_tariff
            dwelling.secondary_sys = get_4a_secondary_system(dwelling)

    if not dwelling.get('secondary_sys') and exists_and_true(dwelling, 'force_secondary_heating'):
        dwelling.secondary_heating_type_code = 693
        dwelling.secondary_sys_fuel = dwelling.electricity_tariff
        dwelling.secondary_sys = get_4a_secondary_system(dwelling)


def configure_water_system(dwelling):
    if dwelling.get('water_heating_type_code'):  # !!! Why this tests?
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
                    (dwelling.sap_community_distribution_type_dhw
                     if dwelling.get('sap_community_distribution_type_dhw')
                     else None))
            if exists_and_true(dwelling,
                               'community_dhw_flat_rate_charging'):
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
    if dwelling.water_sys.is_community_heating:
        dwelling.has_cylinderstat = True
        dwelling.community_heating_dhw = True  # use for table 3
        # Community heating
        if not dwelling.get('hw_cylinder_volume'):
            dwelling.hw_cylinder_volume = 110
            dwelling.storage_loss_factor = .0152

    if dwelling.water_heating_type_code in [907, 908, 909]:
        dwelling.instantaneous_pou_water_heating = True
        dwelling.has_hw_cylinder = False
        dwelling.primary_circuit_loss_annual = 0
    elif dwelling.has_hw_cylinder:
        if dwelling.get("measured_cylinder_loss") and dwelling.measured_cylinder_loss != None:
            dwelling.temperature_factor = hw_temperature_factor(dwelling, True)
        else:
            # !!! Is this electric CPSU tests in the right place?
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

    configure_secondary_system(dwelling)

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
        configure_control_system1(dwelling, dwelling.main_sys_1)

    if dwelling.get('main_sys_2') and not dwelling.get('heating_control_type_sys2') and dwelling.get(
            "control_2_type_code") and dwelling.control_2_type_code != 2100:
        configure_control_system2(dwelling, dwelling.main_sys_2)


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


def configure_wwhr(dwelling):
    if dwelling.get('wwhr_systems') and not dwelling.wwhr_systems is None:
        for sys in dwelling.wwhr_systems:
            sys['pcdf_sys'] = get_wwhr_system(sys['pcdf_id'])


def configure_fghr(dwelling):
    """
    Configure Flue Gas Heat Recovery (FGHR) for this dwelling

    :param dwelling:
    :return:
    """
    # TODO: Should check that fghr is allowed for this system

    if dwelling.get('fghrs') is not None:
        # !!! Need to add electrical power G1.4
        # !!! Entire fghrs calc is unfinished really
        dwelling.fghrs.update(
                dict(get_fghr_system(dwelling.fghrs['pcdf_id'])))

        if dwelling.fghrs["heat_store"] == "3":
            assert dwelling.water_sys.system_type == HeatingTypes.combi
            assert not dwelling.get('hw_cylinder_volume')
            assert not dwelling.has_hw_cylinder

            dwelling.has_hw_cylinder = True
            dwelling.has_cylinderstat = True
            dwelling.has_hw_time_control = True
            dwelling.hw_cylinder_volume = dwelling.fghrs['heat_store_total_volume']
            dwelling.measured_cylinder_loss = dwelling.fghrs['heat_store_loss_rate']
            dwelling.water_sys.table2b_row = 5

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

        if (dwelling.water_sys.system_type in [HeatingTypes.combi,
                                               HeatingTypes.storage_combi]
            and exists_and_true(dwelling.water_sys, 'has_no_keep_hot')
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
    if dwelling.get('photovoltaic_systems'):
        for pv_system in dwelling.photovoltaic_systems:
            configure_pv_system(pv_system)


def configure_solar_hw(dwelling):
    if dwelling.get('solar_collector_aperture') is not None:
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

        if not dwelling.get('collector_zero_loss_effy'):
            default_params = TABLE_H1[dwelling.collector_type]
            dwelling.collector_zero_loss_effy = default_params[0]
            dwelling.collector_heat_loss_coeff = default_params[1]


def configure_wind_turbines(dwelling):
    if dwelling.get('N_wind_turbines'):
        dwelling.wind_turbine_speed_correction_factor = m1_correction_factor(
                dwelling.terrain_type,
                dwelling.wind_turbine_hub_height)


def configure_ventilation(dwelling):
    if dwelling.ventilation_type == VentilationTypes.MEV_CENTRALISED:
        if dwelling.get('mev_sfp'):
            sfp = dwelling.mev_sfp
            in_use_factor = get_in_use_factor(dwelling.ventilation_type, dwelling.mv_ducttype,
                                              exists_and_true(dwelling, 'mv_approved'))
        else:
            sfp = 0.8  # Table 4g
            in_use_factor = default_in_use_factor()
        dwelling.adjusted_fan_sfp = sfp * in_use_factor
        if exists_and_true(dwelling, 'mv_approved'):
            assert False
    elif dwelling.ventilation_type == VentilationTypes.MEV_DECENTRALISED:
        if dwelling.get('mev_sys_pcdf_id'):
            sys = get_mev_system(dwelling.mev_sys_pcdf_id)
            get_sfp = lambda configuration: sys['configs'][configuration]['sfp']
        else:
            get_sfp = lambda configuration: dwelling["mev_fan_" + configuration + "_sfp"]

        total_flow = 0
        sfp_sum = 0

        for location in ['room', 'duct', 'wall']:
            this_duct_type = (DuctTypes.NONE
                              if location == 'wall'
                              else dwelling.mv_ducttype)
            for fantype in ['kitchen', 'other']:
                configuration = location + '_' + fantype
                countattr = 'mev_fan_' + configuration + '_count'
                if dwelling.get(countattr):
                    count = getattr(dwelling, countattr)
                    sfp = get_sfp(configuration)
                    in_use_factor = get_in_use_factor(dwelling.ventilation_type,
                                                      this_duct_type,
                                                      exists_and_true(dwelling, 'mv_approved'))
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
        if dwelling.get('mvhr_sfp'):
            in_use_factor = get_in_use_factor(dwelling.ventilation_type,
                                              dwelling.mv_ducttype,
                                              exists_and_true(dwelling, 'mv_approved'))
            in_use_factor_hr = get_in_use_factor_hr(dwelling.
                                                    ventilation_type,
                                                    dwelling.mv_ducttype,
                                                    exists_and_true(dwelling, 'mv_approved'))
        else:
            dwelling.mvhr_sfp = 2  # Table 4g
            dwelling.mvhr_effy = 66  # Table 4g

            in_use_factor = default_in_use_factor()
            in_use_factor_hr = default_hr_effy_factor()

            if exists_and_true(dwelling, 'mv_approved'):
                assert False

        dwelling.adjusted_fan_sfp = dwelling.mvhr_sfp * in_use_factor
        dwelling.mvhr_effy = dwelling.mvhr_effy * in_use_factor_hr
    elif dwelling.ventilation_type == VentilationTypes.MV:
        if dwelling.get('mv_sfp'):
            mv_sfp = dwelling.mv_sfp
            in_use_factor = get_in_use_factor(dwelling.ventilation_type, dwelling.mv_ducttype,
                                              exists_and_true(dwelling, 'mv_approved'))
        else:
            mv_sfp = 2  # Table 4g
            in_use_factor = default_in_use_factor()
        dwelling.adjusted_fan_sfp = mv_sfp * in_use_factor
    elif dwelling.ventilation_type == VentilationTypes.PIV_FROM_OUTSIDE:
        if dwelling.get('piv_sfp'):
            piv_sfp = dwelling.piv_sfp
            in_use_factor = get_in_use_factor(dwelling.ventilation_type, dwelling.mv_ducttype,
                                              exists_and_true(dwelling, 'mv_approved'))
        else:
            piv_sfp = 0.8  # Table 4g
            in_use_factor = default_in_use_factor()
        dwelling.adjusted_fan_sfp = piv_sfp * in_use_factor


def gas_boiler_from_pcdf(dwelling, pcdf_data, fuel, use_immersion_in_summer):
    if pcdf_data['main_type'] == "Combi":
        system_type = HeatingTypes.combi
    elif pcdf_data['main_type'] == "CPSU":
        system_type = HeatingTypes.cpsu
    else:
        system_type = HeatingTypes.regular_boiler

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
            assert not dwelling.get('fghrs')
        else:
            if (dwelling.get('fghrs') and
                        dwelling.fghrs is None):
                # inputs expliticly say there is no fghrs, so don't
                # add one even if boiler specifies one
                pass
            else:
                if dwelling.get('fghrs'):
                    assert dwelling.fghrs['pcdf_id'] == pcdf_data['subsidiary_type_index']
                else:
                    dwelling.fghrs = dict(pcdf_id=pcdf_data['subsidiary_type_index'])

    if pcdf_data['storage_type'] != "Unknown":
        # Shouldn't have cylinder data specified if we are going to
        # use pcdf cylinder info
        assert not dwelling.get("hw_cylinder_volume")

    if pcdf_data['main_type'] == 'Regular':
        # !!! Also need to allow this for table 4a systems?
        if exists_and_true(dwelling, 'cylinder_is_thermal_store'):
            if dwelling.thermal_store_type == ThermalStoreTypes.HW_ONLY:
                sys.table2b_row = 6
            else:
                sys.table2b_row = 7
            dwelling.has_cylinderstat = True
        else:
            sys.table2b_row = 2  # !!! Assumes not electric
    elif pcdf_data['main_type'] == 'Combi':
        # !!! introduce a type for storage types
        if pcdf_data['storage_type'] in ['storage combi with primary store', 'storage combi with secondary store']:
            # !!! Should only do this if combi is the hw system - this
            # !!! check for having a defined ins type works for now,
            # !!! but will need improving
            if not dwelling.get('hw_cylinder_insulation_type'):
                dwelling.hw_cylinder_volume = pcdf_data["store_boiler_volume"]
                dwelling.hw_cylinder_insulation = pcdf_data["store_insulation_mms"]
                dwelling.hw_cylinder_insulation_type = CylinderInsulationTypes.FOAM
                # Force calc to use the data from pcdf, don't use a user entered cylinder loss
                dwelling.measured_cylinder_loss = None

        if pcdf_data['storage_type'] == 'storage combi with primary store':
            sys.table2b_row = 3
            dwelling.has_cylinderstat = True
        elif pcdf_data['storage_type'] == 'storage combi with secondary store':
            sys.table2b_row = 4
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
        sys.table2b_row = 7  # !!! Assumes gas-fired
        dwelling.has_cylinderstat = True
        sys.cpsu_Tw = dwelling.cpsu_Tw
        sys.cpsu_not_in_airing_cupboard = exists_and_true(dwelling, 'cpsu_not_in_airing_cupboard')
    else:
        # !!! What about other table rows?
        raise ValueError("Unknown system type")

    if sys.system_type == HeatingTypes.combi:
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
    sys = HeatingSystem(HeatingTypes.regular_boiler,  # !!!
                        effy,
                        effy,
                        summer_immersion=use_immersion_in_summer,
                        has_flue_fan=False,  # !!!
                        has_ch_pump=True,
                        table2b_row=2,  # !!! Solid fuel boilers can only have indirect boiler?
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

    sys = HeatingSystem(HeatingTypes.regular_boiler,  # !!!
                        winter_effy,
                        summer_effy,
                        summer_immersion=use_immersion_in_summer,
                        has_flue_fan=False,  # !!!
                        has_ch_pump=True,
                        table2b_row=2,  # !!! Solid fuel boilers can only have indirect boiler?
                        default_secondary_fraction=0.1,  # !!! Assumes 10% secondary fraction
                        fuel=fuel)

    sys.range_cooker_heat_required_scale_factor = 1 - (
        pcdf_data['case_loss_at_full_output'] / pcdf_data['full_output_power'])

    # !!! Assumes we have a heat emitter - is that always the case?
    sys.responsiveness = USE_TABLE_4D_FOR_RESPONSIVENESS

    # !!!
    sys.has_warm_air_fan = False
    return sys


def pcdf_heating_system(dwelling,
                        pcdf_id,
                        fuel,
                        use_immersion_in_summer):
    pcdf_data = get_boiler(pcdf_id)
    if not pcdf_data is None:
        return gas_boiler_from_pcdf(dwelling, pcdf_data, fuel, use_immersion_in_summer)

    pcdf_data = get_solid_fuel_boiler(pcdf_id)
    if not pcdf_data is None:
        return solid_fuel_boiler_from_pcdf(pcdf_data, fuel, use_immersion_in_summer)

    pcdf_data = get_twin_burner_cooker_boiler(pcdf_id)
    if not pcdf_data is None:
        return twin_burner_cooker_boiler_from_pcdf(pcdf_data, fuel, use_immersion_in_summer)

    pcdf_data = get_heat_pump(pcdf_id)
    if not pcdf_data is None:
        return heat_pump_from_pcdf(dwelling, pcdf_data, fuel, use_immersion_in_summer)

    pcdf_data = get_microchp(pcdf_id)
    if not pcdf_data is None:
        return micro_chp_from_pcdf(dwelling, pcdf_data, fuel, use_immersion_in_summer)


def get_table3_row(dwelling):
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
    elif exists_and_true(dwelling, 'cylinder_is_thermal_store'):
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
    table3row = get_table3_row(dwelling)
    return TABLE_3[table3row](dwelling)


def has_ch_pump(dwelling):
    return (dwelling.get('heating_emitter_type', False) or
            dwelling.get('heating_emitter_type2', False))


def get_4a_main_system(dwelling,
                       system_code,
                       fuel,
                       use_immersion_in_summer,
                       hetas_approved):
    """
    Get the main heating system according to Table 4a for the given dwelling

    :param dwelling:
    :param system_code:
    :param fuel:
    :param use_immersion_in_summer:
    :param hetas_approved:
    :return: HeatingSystem object
    """
    system_data = get_4a_system(dwelling.electricity_tariff, system_code)

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
                           system_data['table2b_row'],
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
        system.cpsu_not_in_airing_cupboard = exists_and_true(dwelling, 'cpsu_not_in_airing_cupboard')

    return system


def get_4a_secondary_system(dwelling):
    """
    Get the secondary heating system according to Table 4a for the
    given dwelling

    :param dwelling:
    :return: SecondarySystem object
    """
    system_data = get_4a_system(dwelling.electricity_tariff, dwelling.secondary_heating_type_code)

    if (exists_and_true(dwelling, 'secondary_hetas_approved') and
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
    sys.table2b_row = system_data['table2b_row']
    sys.fuel = dwelling.secondary_sys_fuel

    if system_data['water_effy'] != "same" and system_data['water_effy'] != "":
        sys.water_effy = float(system_data['water_effy'])

    return sys


def get_manuf_data_secondary_system(dwelling):
    effy = dwelling.secondary_sys_manuf_effy
    sys = SecondarySystem(
            HeatingTypes.misc,
            effy,
            dwelling.get('use_immersion_heater_summer', False))

    # sys.table2b_row=system_data['table2b_row']
    sys.fuel = dwelling.secondary_sys_fuel
    return sys


def get_4b_main_system(dwelling, system_code, fuel, use_immersion_in_summer):
    system_data = TABLE_4B[system_code]
    system = HeatingSystem(system_type_from_sap_code(system_code, system_data),
                           system_data['effy_winter'],
                           system_data['effy_summer'],
                           use_immersion_in_summer,
                           system_data['flue_fan'] == 'TRUE',
                           has_ch_pump(dwelling),
                           system_data['table2b_row'],
                           system_data['fraction_of_heat_from_secondary'],
                           fuel)

    system.responsiveness = system_data['responsiveness']
    system.is_condensing = system_data['condensing']
    if system.system_type in [HeatingTypes.combi,
                              HeatingTypes.storage_combi]:
        system.combi_loss = combi_loss_table_3a(dwelling, system)
    elif system.system_type == HeatingTypes.cpsu:
        system.cpsu_not_in_airing_cupboard = exists_and_true(dwelling, 'cpsu_not_in_airing_cupboard')

    return system


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
    if boiler_type == HeatingTypes.regular_boiler:
        table2b_row = 2
    elif boiler_type == HeatingTypes.storage_combi:
        table2b_row = 3
    elif boiler_type == HeatingTypes.cpsu:
        table2b_row = 7
    else:
        table2b_row = -1

    system = HeatingSystem(boiler_type,
                           effy_winter,
                           effy_summer,
                           use_immersion_heater_summer,
                           has_flue_fan,
                           True,  # CH pump
                           table2b_row,
                           .1,  # !!! 2ndary fraction
                           fuel)

    system.responsiveness = 1
    system.is_condensing = is_condensing
    if system.system_type in [HeatingTypes.combi,
                              HeatingTypes.storage_combi]:
        system.combi_loss = combi_loss_table_3a(dwelling, system)

        if dwelling.get('hw_cylinder_volume') and dwelling.hw_cylinder_volume > 0:
            dwelling.has_cylinderstat = True  # !!! Does this go here?
    elif system.system_type == HeatingTypes.cpsu:
        # !!! Might also need to set cpsu_Tw here?
        system.cpsu_not_in_airing_cupboard = exists_and_true(dwelling, 'cpsu_not_in_airing_cupboard')

    if range_case_loss != None:
        system.range_cooker_heat_required_scale_factor = 1 - (
            range_case_loss / range_full_output)

    return system


def lookup_sap_tables(dwelling):
    """
    Lookup data from SAP tables for given dwelling

    :param dwelling:
    :return:
    """

    # FIXME!!! Globally dynamically changing the meaning of get_fuel_data is a recipe for bugs!
    # global get_fuel_data
    if exists_and_true(dwelling, 'use_pcdf_fuel_prices'):
        fuels.PREFER_PCDF_FUEL_PRICES = True
    else:
        fuels.PREFER_PCDF_FUEL_PRICES = False

    # Fix up fuel types
    if dwelling.get('water_sys_fuel') and dwelling.water_sys_fuel == ELECTRICITY_STANDARD:
        dwelling['water_sys_fuel'] = dwelling.electricity_tariff
    if dwelling.get('secondary_sys_fuel') and dwelling.secondary_sys_fuel == ELECTRICITY_STANDARD:
        dwelling['secondary_sys_fuel'] = dwelling.electricity_tariff

    dwelling['Nocc'] = occupancy(dwelling.GFA)
    dwelling['daily_hot_water_use'] = daily_hw_use(dwelling.low_water_use, dwelling.Nocc)

    region = dwelling['sap_region']
    dwelling['external_temperature_summer'] = TABLE_10[region]['external_temperature']
    dwelling['Igh_summer'] = TABLE_10[region]['solar_radiation']
    dwelling['latitude'] = TABLE_10[region]['latitude']

    if not dwelling.get('living_area_fraction'):
        dwelling['living_area_fraction'] = dwelling.living_area / dwelling.GFA

    if dwelling.get("wall_type"):
        dwelling['structural_infiltration'] = 0.35 if dwelling.wall_type == WallTypes.MASONRY else 0.25

    if dwelling.get('floor_type'):
        dwelling['floor_infiltration'] = FLOOR_INFILTRATION[dwelling.floor_type]

    overshading_factors = TABLE_6D[dwelling.overshading]
    dwelling['light_access_factor'] = overshading_factors["light_access_factor"]
    dwelling['solar_access_factor_winter'] = overshading_factors["solar_access_factor_winter"]
    dwelling['solar_access_factor_summer'] = overshading_factors["solar_access_factor_summer"]

    configure_ventilation(dwelling)
    configure_systems(dwelling)
    configure_cooling_system(dwelling)
    configure_pv(dwelling)
    configure_solar_hw(dwelling)
    configure_wind_turbines(dwelling)
    configure_fans_and_pumps(dwelling)

    # Bit of a special case here!
    if exists_and_true(dwelling, 'reassign_systems_for_test_case_30'):
        # Basically, I have no idea what happens here
        assert False

    if hasattr(dwelling, 'next_stage'):
        dwelling.next_stage()
