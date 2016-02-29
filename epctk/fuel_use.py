"""
SAP Section 12: Total energy use and fuel costs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
from collections import namedtuple, OrderedDict
from typing import Dict

import numpy

from .heating_loaders import immersion_on_peak_fraction
from .elements import HeatingTypes
from .constants import SUMMER_MONTHS
from .fuels import ELECTRICITY_SOLD, ELECTRICITY_OFFSET
from .utils import sum_

# Some private namedtuples to make it easier and more reliable to track results
# and avoid unintended changes to the values
EnergySubtotal = namedtuple('_EnergySumResults', 'energy_use, primary_energy, emissions, fuel_cost')
EnergyTotals = namedtuple('_EnergyTotals',
                           'energy_use, energy_use_offset, emissions, emissions_offset, fuel_cost, cost_offset, primary_energy, primary_energy_offset')


def sub_total(energy, primary_energy_factor, co2_factor, cost):
    """
    Calculate the total energy use, primary energy, emissions, and
    cost from the energy value (either a single value or an array e.g.
    a monthly array) and the relevant conversion factors.

    Args:
        energy (float | array): the energy demand kWh
        primary_energy_factor: conversion factor from final to primary energy
        co2_factor: CO2 content per kWh
        cost: cost per kWh final energy

    Returns:
        _EnergySubtotal (namedtuple)
    """
    energy_use = sum_(energy)
    emissions = sum_(energy * co2_factor)
    fuel_cost = sum_(energy * cost)
    primary_energy = sum_(energy * primary_energy_factor)
    return EnergySubtotal(energy_use, primary_energy, emissions, fuel_cost)


def sum_energy_stats(energy_stats, cost_standing):
    energy_use = 0
    energy_use_offset = 0
    emissions = 0
    emissions_offset = 0
    fuel_cost = cost_standing
    cost_offset = 0
    primary_energy = 0
    primary_energy_offset = 0

    for label, subtot in energy_stats.items():
        # Only cooking, mech vent and fans, and appliances are 'unregulated'
        regulated = True if label not in ['cooking', 'mech_vent_fans', 'appliances'] else False

        # Offset energy is always regulated?
        if subtot.energy_use < 0:
            energy_use_offset += subtot.energy_use
            emissions_offset += subtot.emissions
            cost_offset += subtot.fuel_cost
            primary_energy_offset += subtot.primary_energy

        if regulated:
            energy_use += subtot.energy_use
            emissions += subtot.emissions
            fuel_cost += subtot.fuel_cost
            primary_energy += subtot.primary_energy

    return EnergyTotals(energy_use,
                        energy_use_offset,
                        emissions,
                        emissions_offset,
                        fuel_cost,
                        cost_offset,
                        primary_energy,
                        primary_energy_offset)


def flatten_for_now(energy_stats: Dict[str, EnergySubtotal]):
    """
    Flatten the energy stats dict to fit the legacy format used in EPCTK

    .. note::
      in the future may prefer to keep subtotal results in nested format.

    Args:
        energy_stats: a dict of (label: _EnergySubtotal tuple) key-value pairs

    Returns:
        a new dict, flattened by appending label to the energy stat name.
        e.g. heating_main.emissions becomes emissions_heating_main
    """
    flat = {}
    for label, vals in energy_stats.items():
        energy_use_varname = "energy_use_%s" % label
        primary_energy_varname = "primary_energy_%s" % label
        emissions_varname = "emissions_%s" % label
        cost_varname = "cost_%s" % label

        flat[energy_use_varname] = vals.energy_use
        flat[primary_energy_varname] = vals.primary_energy
        flat[emissions_varname] = vals.emissions
        flat[cost_varname] = vals.fuel_cost

    return flat


def fuel_use(dwelling):
    """
    Calculate the fuel/energy stats for each dwelling subsystem and
    sum them up.

    Calculates the total energy, primary energy, CO2 emissions, and Cost
    based on the previously calculated energy demands of subsystems including
    space heating, water heating, cooking, appliances, fans, etc...

    Args:
        dwelling:

    """
    cost_export = ELECTRICITY_SOLD.unit_price() / 100
    C_el_offset = ELECTRICITY_OFFSET.co2_factor
    primary_el_offset = ELECTRICITY_OFFSET.primary_energy_factor

    C_el = dwelling.general_elec_co2_factor
    cost_el = dwelling.general_elec_price / 100
    PE_el = dwelling.general_elec_PE

    n_occupants = dwelling.Nocc
    gfa = dwelling.GFA

    system_1 = dwelling.main_sys_1
    water_sys = dwelling.water_sys
    q_spaceheat_main = dwelling.Q_spaceheat_main
    q_spacecooling = dwelling.Q_spacecooling
    q_fans_and_pumps = dwelling.Q_fans_and_pumps
    waterheat = dwelling.Q_waterheat
    light_consumption = dwelling.annual_light_consumption
    total_appliance_consumption = sum(dwelling.appliance_consumption)

    q_water_heater, immersion_results = immersion_fuel(C_el, PE_el, waterheat,
                                                       dwelling.get('use_immersion_heater_summer', False),
                                                       dwelling.get('water_fuel_price_immersion', 0))

    main_1_fuel = system_fuel(dwelling, system_1, q_spaceheat_main)
    water_fuel = system_fuel(dwelling, water_sys, q_water_heater)

    main_2_fuel = system_fuel(dwelling, dwelling.get('main_sys_2'), dwelling.get('Q_spaceheat_main_2', 0))
    secondary_fuel = system_fuel(dwelling, dwelling.get('secondary_sys'), dwelling.get('Q_spaceheat_secondary', 0))

    credit_result = community_credit(system_1, water_sys, C_el_offset, q_water_heater, q_spaceheat_main,
                                     primary_el_offset)

    cooking_results = cooking_fuel(PE_el, cost_el, n_occupants, gfa)

    gen_results = generators_fuels(dwelling, C_el_offset, cost_el, cost_export, primary_el_offset)

    appendix_q_gen, appendix_q_used = appendix_q_fuel(C_el, PE_el, cost_el, dwelling)

    cooling = sub_total(q_spacecooling, PE_el, C_el, cost_el)
    fans_and_pumps = sub_total(q_fans_and_pumps, PE_el, C_el, cost_el)
    lighting = sub_total(light_consumption, PE_el, C_el, cost_el)
    appliances = sub_total(total_appliance_consumption, PE_el, C_el, cost_el)
    mech_vent_fans = sub_total(dwelling.Q_mech_vent_fans, PE_el, C_el, dwelling.mech_vent_elec_price / 100)

    community_neg, community_result = community_fuel(system_1, water_sys, q_water_heater, q_spaceheat_main,
                                                     main_1_fuel.emissions, water_fuel.emissions,
                                                     credit_result.emissions)

    # Collect all the fuel use result variables
    fuel_stats = OrderedDict(
        heating_main=main_1_fuel,
        heating_main_2=main_2_fuel,
        water=water_fuel,
        heating_secondary=secondary_fuel,
        water_summer_immersion=immersion_results,
        community_elec_credits=credit_result,
        community_distribution=community_result,
        negative_community_emissions_correction=community_neg,
        cooking=cooking_results,
        appendix_q_generated=appendix_q_gen, appendix_q_used=appendix_q_used,
        cooling=cooling,
        fans_and_pumps=fans_and_pumps,
        lighting=lighting,
        appliances=appliances,
        mech_vent_fans=mech_vent_fans)

    fuel_stats.update(gen_results)

    totals = sum_energy_stats(fuel_stats, dwelling.cost_standing)

    flat_stats = flatten_for_now(fuel_stats)

    flat_stats.update(totals._asdict())
    return flat_stats


def system_fuel(dwelling, system, heat):
    if system is not None:
        sub_totals = sub_total(heat, system.primary_energy_factor(),
                               system.co2_factor(),
                               system.fuel_price(dwelling) / 100)

    else:
        sub_totals = sub_total(0, 0, 0, 0)

    return sub_totals


def generators_fuels(dwelling, c_el_offset, cost_el, cost_export, primary_el_offset):
    # convenience closures
    def net_cost(gen_frac):
        return cost_el * gen_frac + cost_export * (1 - gen_frac)

    def calc_gen_totals(energy, cost):
        return sub_total(energy, primary_el_offset, c_el_offset, cost)

    pv_frac = dwelling.pv_electricity_onsite_fraction
    wind_frac = dwelling.wind_electricity_onsite_fraction
    hydro_frac = dwelling.hydro_electricity_onsite_fraction
    chp_frac = dwelling.chp_electricity_onsite_fraction

    collected = {'pv': calc_gen_totals(-dwelling.pv_electricity, net_cost(pv_frac)),
                 'wind': calc_gen_totals(-dwelling.wind_electricity, net_cost(wind_frac)),
                 'hydro': calc_gen_totals(-dwelling.hydro_electricity, net_cost(hydro_frac)),
                 'chp': calc_gen_totals(-dwelling.hydro_electricity, net_cost(chp_frac))}
    return collected


def cooking_fuel(PE_el, cost_el, Nocc, GFA):
    # For cooking cost, assume that 40% of cooking is by gas, 60% by
    # electric (matches the emissions calc)
    cost_cooking_fuel = 0.4 * 0.031 + 0.6 * cost_el
    pe_cooking_fuel = 0.4 * 1.02 + 0.6 * PE_el
    cooking_fuel_kWh = (35 + 7 * Nocc) * 8.76
    C_cooking = (119 + 24 * Nocc) / GFA / cooking_fuel_kWh

    subtotal = sub_total(cooking_fuel_kWh, pe_cooking_fuel, C_cooking, cost_cooking_fuel)
    return subtotal


def immersion_fuel(co2_factor, primary_energy_elec, q_waterheat, use_immersion_heater_summer,
                   water_fuel_price_immersion=0):
    immersion_months = numpy.array([0, ] * 12)

    if use_immersion_heater_summer:
        for i in SUMMER_MONTHS:
            immersion_months[i] = 1

        q_summer_immersion = q_waterheat * immersion_months
        sub_totals = sub_total(q_summer_immersion, primary_energy_elec, co2_factor, water_fuel_price_immersion / 100.)
    else:
        q_summer_immersion = q_waterheat * immersion_months
        sub_totals = sub_total(0, 0, 0, 0)

    q_water_heater = q_waterheat - q_summer_immersion

    return q_water_heater, sub_totals


def community_fuel(system_1, water_sys, q_water_heater, q_spaceheat_main,
                   emissions_heating_main, emissions_water, emissions_community_elec_credits):
    community_result = EnergySubtotal(0, 0, 0, 0)
    community_neg_result = EnergySubtotal(0, 0, 0, 0)

    community_distribution_elec = 0

    # TODO Can main sys 2 be community heating?
    if system_1.system_type == HeatingTypes.community:
        community_distribution_elec += 0.01 * sum(q_spaceheat_main)
    if water_sys.system_type == HeatingTypes.community:
        community_distribution_elec += 0.01 * sum(q_water_heater)

    if community_distribution_elec > 0:
        # TODO Fuel costs should come from sap_tables

        community_result = sub_total(community_distribution_elec, 2.92, 0.517, 0)

        heat_emissions = emissions_heating_main if system_1.system_type == HeatingTypes.community else 0
        water_emissions = emissions_water if water_sys.system_type == HeatingTypes.community else 0

        distribution_emissions = community_result.emissions + emissions_community_elec_credits

        total_community_emissions = heat_emissions + water_emissions + distribution_emissions

        if total_community_emissions < 0:
            community_neg_result = sub_total(community_distribution_elec, 0, -total_community_emissions, 0)

    return community_neg_result, community_result


def appendix_q_fuel(co2_factor, primary_energy_factor, cost_el, dwelling):
    def subtotal_sum(t1, t2):
        return EnergySubtotal(*(x + y for x, y in zip(t1, t2)))

    gen_subtotal = EnergySubtotal(0, 0, 0, 0)
    used_subtotal = EnergySubtotal(0, 0, 0, 0)
    q_systems = dwelling.get('appendix_q_systems')
    if q_systems is not None:
        for sys in q_systems:
            if 'fuel_saved' in sys:
                gen_sub = sub_total(-sys['generated'],
                                       sys['fuel_saved'].primary_energy_factor,
                                       sys['fuel_saved'].co2_factor,
                                       sys['fuel_saved'].unit_price() / 100)
                use_sub = sub_total(sys['used'],
                                       sys['fuel_saved'].primary_energy_factor,
                                       sys['fuel_saved'].co2_factor,
                                       sys['fuel_saved'].unit_price() / 100)
            else:
                gen_sub = sub_total(-sys['generated'],
                                       primary_energy_factor,
                                       co2_factor,
                                       cost_el)

                use_sub = sub_total(sys['used'],
                                       primary_energy_factor,
                                       co2_factor,
                                       cost_el)

            gen_subtotal = subtotal_sum(gen_subtotal, gen_sub)
            used_subtotal = subtotal_sum(used_subtotal, use_sub)

    return gen_subtotal, used_subtotal


def community_credit(system_1, water_sys, C_el_offset, Q_water_heater, Q_spaceheat_main, primary_el_offset):
    chp_elec = 0

    # TODO Can main sys 2 be community heating?
    if system_1.get('heat_to_power_ratio', 0) != 0:
        chp_elec += (sum(Q_spaceheat_main)) / system_1.heat_to_power_ratio

    if hasattr(water_sys, 'heat_to_power_ratio') and water_sys.heat_to_power_ratio != 0:
        chp_elec += (sum(Q_water_heater)) / water_sys.heat_to_power_ratio

    if chp_elec > 0:
        chp_result = sub_total(-chp_elec,
                               primary_el_offset,
                               C_el_offset,
                               0)
    else:
        chp_result = EnergySubtotal(0, 0, 0, 0)

    return chp_result


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
