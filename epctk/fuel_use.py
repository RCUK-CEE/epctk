"""
SAP Section 12: Total energy use and fuel costs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
from collections import namedtuple

import numpy

from .heating_loaders import immersion_on_peak_fraction
from .elements import HeatingTypes
from .constants import SUMMER_MONTHS
from .fuels import ELECTRICITY_SOLD, ELECTRICITY_OFFSET
from .utils import sum_

# Some private namedtuples to make it easier and more reliable to track results
# and avoid unintended changes to the values
_EnergySubtotal = namedtuple('_EnergySumResults', 'energy_use, primary_energy, emissions, fuel_cost')
_EnergyTotals = namedtuple('_EnergyTotals',
                           'energy_use, energy_use_offset, emissions, emissions_offset, fuel_cost, cost_offset, primary_energy, primary_energy_offset')


def calc_totals(energy, primary_energy_factor, co2_factor, cost):
    energy_use = sum_(energy)
    emissions = sum_(energy * co2_factor)
    fuel_cost = sum_(energy * cost)
    primary_energy = sum_(energy * primary_energy_factor)
    return _EnergySubtotal(energy_use, primary_energy, emissions, fuel_cost)


def label_results(totals: _EnergySubtotal, label):
    """
    Return a dict with the energy_sums named using label according to convention
    Args:
        totals:
        label:

    Returns:

    """
    energy_use_varname = "energy_use_%s" % label
    primary_energy_varname = "primary_energy_%s" % label
    emissions_varname = "emissions_%s" % label
    cost_varname = "cost_%s" % label
    labels = (energy_use_varname, primary_energy_varname, emissions_varname, cost_varname)

    return dict(zip(labels, totals))


def calc_overall_total(energy_stats, cost_standing):
    energy_use=0
    energy_use_offset=0
    emissions=0
    emissions_offset=0
    fuel_cost=cost_standing
    cost_offset=0
    primary_energy=0
    primary_energy_offset=0

    for label, sub_total in energy_stats.items():
        # Only cooking, mech vent and fans, and appliances are 'unregulated'
        regulated = True if label not in ['cooking', 'mech_vent_fans','appliances'] else False


        # Offset energy is always regulated?
        if sub_total.energy_use < 0:
            energy_use_offset += sub_total.energy_use,
            emissions_offset += sub_total.emissions,
            cost_offset += sub_total.fuel_cost,
            primary_energy_offset += sub_total.primary_energy


        if regulated:
            energy_use += sub_total.energy_use,
            emissions += sub_total.emissions,
            fuel_cost += sub_total.fuel_cost,
            primary_energy += sub_total.primary_energy


    return _EnergyTotals(energy_use,
                       energy_use_offset,
                       emissions,
                       emissions_offset,
                       fuel_cost,
                       cost_offset,
                       primary_energy,
                       primary_energy_offset)

def flatten_for_now(energy_stats):
    flat = {}
    for label, vals in energy_stats.items():
        energy_use_varname = "energy_use_%s" % label
        primary_energy_varname = "primary_energy_%s" % label
        emissions_varname = "emissions_%s" % label
        cost_varname = "cost_%s" % label

        flat[energy_use_varname] = vals['energy_use']
        flat[primary_energy_varname] = vals['primary_energy']
        flat[emissions_varname] = vals['emissions']
        flat[cost_varname] = vals['fuel_cost']

    return flat

def accumulate_energy(totals: _EnergyTotals, sub_total: _EnergySubtotal, regulated):
    # If we need to offset or add regulated energy, create new namedtuple with updated feild values

    # Offset energy is always regulated?
    if sub_total.energy_use < 0:
        totals = totals._replace(
            energy_use_offset=totals.energy_use_offset + sub_total.energy_use,
            emissions_offset=totals.emissions_offset + sub_total.emissions,
            cost_offset=totals.cost_offset + sub_total.fuel_cost,
            primary_energy_offset=totals.primary_energy_offset + sub_total.primary_energy
        )

    if regulated:
        totals = totals._replace(
            energy_use=totals.energy_use + sub_total.energy_use,
            emissions=totals.emissions + sub_total.emissions,
            fuel_cost=totals.fuel_cost + sub_total.fuel_cost,
            primary_energy=totals.primary_energy + sub_total.primary_energy
        )

    return totals


def fuel_use(dwelling):
    """
    Calculate the fuel use for the dwelling

    Args:
        dwelling:

    """
    # TODO write a test for this
    # TODO: break this into smaller parts
    cost_export = ELECTRICITY_SOLD.unit_price() / 100
    C_el_offset = ELECTRICITY_OFFSET.co2_factor
    primary_el_offset = ELECTRICITY_OFFSET.primary_energy_factor

    C_el = dwelling.general_elec_co2_factor
    cost_el = dwelling.general_elec_price / 100
    PE_el = dwelling.general_elec_PE

    system_1 = dwelling.main_sys_1
    water_sys = dwelling.water_sys
    q_spaceheat_main = dwelling.Q_spaceheat_main

    # This accumulates
    totals = _EnergyTotals(energy_use=0,
                           energy_use_offset=0,
                           emissions=0,
                           emissions_offset=0,
                           fuel_cost=dwelling.cost_standing,
                           cost_offset=0,
                           primary_energy=0,
                           primary_energy_offset=0)

    q_water_heater, immersion_results, totals = immersion_fuel(totals, C_el, PE_el, dwelling.Q_waterheat,
                                                               dwelling.get('use_immersion_heater_summer', False),
                                                               dwelling.get('water_fuel_price_immersion', 0))


    main_1_fuel, totals = system_fuel(dwelling, system_1, q_spaceheat_main, "heating_main", totals)
    water_fuel, totals = system_fuel(dwelling, water_sys, q_water_heater, "water", totals)

    main_2_fuel, totals = system_fuel(dwelling, dwelling.get('main_sys_2'), dwelling.Q_spaceheat_main_2,
                                      "heating_main_2", totals)
    secondary_fuel, totals = system_fuel(dwelling, dwelling.get('secondary_sys'), dwelling.Q_spaceheat_secondary,
                                         "heating_secondary", totals)

    chp_result, totals = chp_fuel(system_1, water_sys, C_el_offset, q_water_heater, q_spaceheat_main, primary_el_offset,
                                  totals)

    community_neg_fuel, community_fuel_result, totals = community_fuel(system_1, water_sys, q_water_heater,
                                                                       q_spaceheat_main, dwelling, totals)

    misc_use_results, totals = misc_electric_usage(C_el, PE_el, cost_el,
                                                   dwelling.Q_spacecooling,
                                                   dwelling.Q_fans_and_pumps,
                                                   dwelling.annual_light_consumption,
                                                   sum(dwelling.appliance_consumption),
                                                   dwelling.Q_mech_vent_fans,
                                                   dwelling.mech_vent_elec_price,
                                                   totals)

    cooking_results, totals = cooking_fuel(PE_el, cost_el, dwelling.Nocc, dwelling.GFA, totals)

    gen_results, totals = generators_fuels(dwelling, C_el_offset, cost_el, cost_export, primary_el_offset, totals)

    appendix_q_gen, appendix_q_used, totals = appendix_q_fuel(C_el, PE_el, cost_el, dwelling, totals)

    # Collect all the fuel use result variables
    fuel_use_results = {}
    fuel_use_results.update(main_1_fuel)
    fuel_use_results.update(main_2_fuel)
    fuel_use_results.update(water_fuel)
    fuel_use_results.update(secondary_fuel)

    fuel_use_results.update(immersion_results)
    fuel_use_results.update(misc_use_results)
    fuel_use_results.update(chp_result)
    fuel_use_results.update(community_fuel_result)
    fuel_use_results.update(community_neg_fuel)
    fuel_use_results.update(gen_results)

    fuel_use_results.update(appendix_q_gen)
    fuel_use_results.update(appendix_q_used)

    fuel_use_results.update(totals._asdict())

    return fuel_use_results


def generators_fuels(dwelling, c_el_offset, cost_el, cost_export, primary_el_offset, totals):
    # convenience closures
    def net_cost(gen_frac):
        return cost_el * gen_frac + cost_export * (1 - gen_frac)

    def calc_gen_totals(energy, cost):
        return calc_totals(energy, primary_el_offset, c_el_offset, cost)

    pv_frac = dwelling.pv_electricity_onsite_fraction
    sub_totals = calc_gen_totals(-dwelling.pv_electricity, net_cost(pv_frac))
    totals = accumulate_energy(totals, sub_totals, True)

    pv = label_results(sub_totals, 'pv')

    wind_frac = dwelling.wind_electricity_onsite_fraction
    sub_totals = calc_gen_totals(-dwelling.wind_electricity, net_cost(wind_frac))
    totals = accumulate_energy(totals, sub_totals, True)
    wind = label_results(sub_totals, 'wind')

    hydro_frac = dwelling.hydro_electricity_onsite_fraction
    sub_totals = calc_gen_totals(-dwelling.hydro_electricity, net_cost(hydro_frac))
    totals = accumulate_energy(totals, sub_totals, True)
    hydro = label_results(sub_totals, 'hydro')

    chp_frac = dwelling.chp_electricity_onsite_fraction
    sub_totals = calc_gen_totals(-dwelling.hydro_electricity, net_cost(chp_frac))
    totals = accumulate_energy(totals, sub_totals, True)
    chp = label_results(sub_totals, 'chp')

    # TODO: could use dict unpacking but would require python 3.5 :(
    collected = {}
    collected.update(pv)
    collected.update(wind)
    collected.update(hydro)
    collected.update(chp)

    return collected, totals


def system_fuel(dwelling, system, heat, label, totals):
    if system is not None:
        sub_totals = calc_totals(heat, system.primary_energy_factor(),
                                 system.co2_factor(),
                                 system.fuel_price(dwelling) / 100)

    else:
        sub_totals = calc_totals(0, 0, 0, 0)

    results = label_results(sub_totals, label)

    totals = accumulate_energy(totals, sub_totals, True)

    return results, totals


def get_fuel_stats(curent_total, label, regulated,
                   energy, primary_energy_factor, co2_factor, cost
                   ):
    """
    Calculate the energy and emmissions and assign to the
    appropriate variable names

    Args:

        curent_total
        label:
        regulated:
        energy:
        co2_factor:
        cost:
        primary_energy_factor:

    Returns:

    """
    sub_totals = calc_totals(energy, primary_energy_factor, co2_factor, cost)

    results_for_label = label_results(sub_totals, label)

    totals = accumulate_energy(curent_total, sub_totals, regulated)
    return totals, results_for_label


def misc_electric_usage(C_el, PE_el, cost_el, Q_spacecooling, Q_fans_and_pumps, annual_light_consumption,
                        E_appliance_consumption, Q_mech_vent_fans, mech_vent_elec_price, totals):
    collected = {}
    sub_totals = calc_totals(Q_spacecooling, PE_el, C_el, cost_el)
    collected.update(label_results(sub_totals, "cooling"))
    totals = accumulate_energy(totals, sub_totals, True)

    sub_totals = calc_totals(Q_fans_and_pumps, PE_el, C_el, cost_el)
    collected.update(label_results(sub_totals, "fans_and_pumps"))
    totals = accumulate_energy(totals, sub_totals, True)

    sub_totals = calc_totals(annual_light_consumption, PE_el, C_el, cost_el)
    collected.update(label_results(sub_totals, "lighting"))
    totals = accumulate_energy(totals, sub_totals, True)

    sub_totals = calc_totals(E_appliance_consumption, PE_el, C_el, cost_el)
    collected.update(label_results(sub_totals, "appliances"))
    totals = accumulate_energy(totals, sub_totals, False)

    sub_totals = calc_totals(Q_mech_vent_fans, PE_el, C_el, mech_vent_elec_price / 100)
    collected.update(label_results(sub_totals, "mech_vent_fans"))
    totals = accumulate_energy(totals, sub_totals, False)

    return collected, totals


def cooking_fuel(PE_el, cost_el, Nocc, GFA, totals):
    # For cooking cost, assume that 40% of cooking is by gas, 60% by
    # electric (matches the emissions calc)
    cost_cooking_fuel = .4 * .031 + .6 * cost_el
    pe_cooking_fuel = .4 * 1.02 + .6 * PE_el
    cooking_fuel_kWh = (35 + 7 * Nocc) * 8.76
    C_cooking = (119 + 24 * Nocc) / GFA / cooking_fuel_kWh

    subtotal = calc_totals(cooking_fuel_kWh, pe_cooking_fuel, C_cooking, cost_cooking_fuel)

    # Actually since cooking is both unregulated and energy demand always >0, this will do nothing...
    totals = accumulate_energy(totals, subtotal, False)

    cooking_results = label_results(subtotal, 'cooking')
    return cooking_results, totals


def immersion_fuel(curent_total, co2_factor, primary_energy_elec, q_waterheat, use_immersion_heater_summer,
                   water_fuel_price_immersion=0):
    immersion_months = numpy.array([0, ] * 12)
    label = "water_summer_immersion"

    if use_immersion_heater_summer:
        for i in SUMMER_MONTHS:
            immersion_months[i] = 1

        q_summer_immersion = q_waterheat * immersion_months
        sub_totals = calc_totals(q_summer_immersion, primary_energy_elec, co2_factor, water_fuel_price_immersion / 100.)
    else:
        q_summer_immersion = q_waterheat * immersion_months
        sub_totals = calc_totals(0, 0, 0, 0)

    totals = accumulate_energy(curent_total, sub_totals, True)

    labeled_subtotals = label_results(sub_totals, label)

    q_water_heater = q_waterheat - q_summer_immersion

    return q_water_heater, labeled_subtotals, totals


def community_fuel(system_1, water_sys, q_water_heater, Q_spaceheat_main, dwelling, totals):
    community_result = {}
    community_neg_result = {}

    community_distribution_elec = 0
    # TODO Can main sys 2 be community heating?


    if system_1.system_type == HeatingTypes.community:
        community_distribution_elec += 0.01 * sum(Q_spaceheat_main)
    if water_sys.system_type == HeatingTypes.community:
        community_distribution_elec += 0.01 * sum(q_water_heater)

    if community_distribution_elec > 0:
        # TODO Fuel costs should come from sap_tables

        sub_totals = calc_totals(community_distribution_elec, 2.92, 0.517, 0)
        community_result = label_results(sub_totals, "community_distribution")
        totals = accumulate_energy(totals, sub_totals, True)

        heat_emissions = dwelling.emissions_heating_main if system_1.system_type == HeatingTypes.community else 0
        water_emissions = dwelling.emissions_water if water_sys.system_type == HeatingTypes.community else 0
        distribution_emissions = dwelling.emissions_community_distribution + dwelling.get(
            'emissions_community_elec_credits', 0)

        total_community_emissions = heat_emissions + water_emissions + distribution_emissions

        if total_community_emissions < 0:
            sub_totals = calc_totals(community_distribution_elec, 0, -total_community_emissions, 0)
            community_neg_result = label_results(sub_totals, "negative_community_emissions_correction")
            totals = accumulate_energy(totals, sub_totals, True)

    return community_neg_result, community_result, totals


def appendix_q_fuel(co2_factor, primary_energy_factor, cost_el, dwelling, totals):
    def subtotal_sum(t1, t2):
        return _EnergySubtotal((x + y for x, y in zip(t1, t2)))

    gen_subtotal = _EnergySubtotal(0, 0, 0, 0)
    used_subtotal = _EnergySubtotal(0, 0, 0, 0)
    q_systems = dwelling.get('appendix_q_systems')
    if q_systems is not None:
        for sys in q_systems:
            if 'fuel_saved' in sys:
                sub_totals = calc_totals(-sys['generated'],
                                         sys['fuel_saved'].primary_energy_factor,
                                         sys['fuel_saved'].co2_factor,
                                         sys['fuel_saved'].unit_price() / 100)
            else:
                sub_totals = calc_totals(-sys['generated'],
                                         primary_energy_factor,
                                         co2_factor,
                                         cost_el)

            gen_subtotal = subtotal_sum(gen_subtotal, sub_totals)
            totals = accumulate_energy(totals, sub_totals, True)

            if 'fuel_used' in sys:
                sub_totals = calc_totals(sys['used'],
                                         sys['fuel_saved'].primary_energy_factor,
                                         sys['fuel_saved'].co2_factor,
                                         sys['fuel_saved'].unit_price() / 100)
            else:
                sub_totals = calc_totals(sys['used'],
                                         primary_energy_factor,
                                         co2_factor,
                                         cost_el)

            used_subtotal = subtotal_sum(gen_subtotal, sub_totals)
            totals = accumulate_energy(totals, sub_totals, True)

    appendix_q_gen = label_results(gen_subtotal, "appendix_q_generated")
    appendix_q_used = label_results(used_subtotal, "appendix_q_used")

    return appendix_q_gen, appendix_q_used, totals


def chp_fuel(system_1, water_sys, C_el_offset, Q_water_heater, Q_spaceheat_main, primary_el_offset, totals):
    chp_result = {}
    chp_elec = 0
    # !!! Can main sys 2 be community heating?

    if system_1.get('heat_to_power_ratio', 0) != 0:
        chp_elec += (sum(Q_spaceheat_main)) / system_1.heat_to_power_ratio

    if hasattr(water_sys, 'heat_to_power_ratio') and water_sys.heat_to_power_ratio != 0:
        chp_elec += (sum(Q_water_heater)) / water_sys.heat_to_power_ratio

    if chp_elec > 0:
        chp_result = calc_totals(-chp_elec,
                                 primary_el_offset,
                                 C_el_offset,
                                 0)
        totals = accumulate_energy(totals, chp_result, True)
        chp_result = label_results(chp_result, "community_elec_credits")

    return chp_result, totals


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
