import numpy

from .constants import SUMMER_MONTHS
from .utils import sum_

from .fuels import ELECTRICITY_SOLD, ELECTRICITY_OFFSET
from .sap_types import HeatingTypes


def set_fuel_use(dwelling, label, regulated,
                 energy, co2_factor, cost,
                 primary_energy_factor):
    """

    Args:
        dwelling:
        label:
        regulated:
        energy:
        co2_factor:
        cost:
        primary_energy_factor:

    Returns:

    """
    emissions = sum_(energy * co2_factor)
    fuel_cost = sum_(energy * cost)
    primary_energy = sum_(energy * primary_energy_factor)

    if dwelling.get("energy_use_%s" % label):
        old_energy = dwelling["energy_use_%s" % label]
        old_emissions = dwelling["emissions_%s" % label]
        old_cost = dwelling["cost_%s" % label]
        old_pe = dwelling["primary_energy_%s" % label]
    else:
        old_energy = 0
        old_emissions = 0
        old_cost = 0
        old_pe = 0

    dwelling["energy_use_%s" % label] = sum_(energy) + old_energy
    dwelling["emissions_%s" % label] = emissions + old_emissions
    dwelling["cost_%s" % label] = fuel_cost + old_cost
    dwelling["primary_energy_%s" % label] = primary_energy + old_pe

    # Offset energy is always regulated?
    if sum_(energy) < 0:
        dwelling.energy_use_offset += sum_(energy)
        dwelling.emissions_offset += emissions
        dwelling.cost_offset += fuel_cost
        dwelling.primary_energy_offset += primary_energy

    if regulated:
        dwelling.energy_use += sum_(energy)
        dwelling.emissions += emissions
        dwelling.fuel_cost += fuel_cost
        dwelling.primary_energy += primary_energy


def fuel_use(dwelling):
    """
    Calculate the fuel use for the dwelling

    Args:
        dwelling:

    """
    # TODO: break this into smaller parts
    cost_export = ELECTRICITY_SOLD.unit_price() / 100
    C_el_offset = ELECTRICITY_OFFSET.co2_factor
    primary_el_offset = ELECTRICITY_OFFSET.primary_energy_factor

    C_el = dwelling.general_elec_co2_factor
    cost_el = dwelling.general_elec_price / 100.
    PE_el = dwelling.general_elec_PE

    dwelling.energy_use = 0
    dwelling.energy_use_offset = 0
    dwelling.emissions = 0
    dwelling.emissions_offset = 0
    dwelling.fuel_cost = dwelling.cost_standing
    dwelling.cost_offset = 0
    dwelling.primary_energy = 0
    dwelling.primary_energy_offset = 0

    immersion_months = numpy.array([0, ] * 12)
    if dwelling.get('use_immersion_heater_summer', False):
        for i in SUMMER_MONTHS:
            immersion_months[i] = 1

        Q_summer_immersion = dwelling.Q_waterheat * immersion_months
        set_fuel_use(dwelling, "water_summer_immersion", True,
                     Q_summer_immersion,
                     C_el,
                     dwelling.water_fuel_price_immersion / 100.,
                     PE_el)

    else:
        Q_summer_immersion = dwelling.Q_waterheat * immersion_months
        set_fuel_use(dwelling, "water_summer_immersion", True,
                     0, 0, 0, 0)

    Q_water_heater = dwelling.Q_waterheat - Q_summer_immersion

    set_fuel_use(dwelling, "water", True,
                 Q_water_heater,
                 dwelling.water_sys.co2_factor(),
                 dwelling.water_sys.water_fuel_price(dwelling) / 100.,
                 dwelling.water_sys.primary_energy_factor())

    set_fuel_use(dwelling, "heating_main", True,
                 dwelling.Q_spaceheat_main,
                 dwelling.main_sys_1.co2_factor(),
                 dwelling.main_sys_1.fuel_price(dwelling) / 100.,
                 dwelling.main_sys_1.primary_energy_factor())

    chp_elec = 0
    # !!! Can main sys 2 be community heating?
    if dwelling.main_sys_1.get('heat_to_power_ratio') is not None:
        if dwelling.main_sys_1.heat_to_power_ratio != 0:
            chp_elec += (sum(dwelling.Q_spaceheat_main)
                         ) / dwelling.main_sys_1.heat_to_power_ratio

    if hasattr(dwelling.water_sys, 'heat_to_power_ratio'):
        if dwelling.water_sys.heat_to_power_ratio != 0:
            chp_elec += (sum(Q_water_heater)
                         ) / dwelling.water_sys.heat_to_power_ratio

    if chp_elec > 0:
        set_fuel_use(dwelling, "community_elec_credits", True,
                     -chp_elec,
                     C_el_offset,
                     0,
                     primary_el_offset)

    community_distribution_elec = 0
    # !!! Can main sys 2 be community heating?
    if dwelling.main_sys_1.system_type == HeatingTypes.community:
        community_distribution_elec += 0.01 * sum(dwelling.Q_spaceheat_main)
    if dwelling.water_sys.system_type == HeatingTypes.community:
        community_distribution_elec += 0.01 * sum(Q_water_heater)
    if community_distribution_elec > 0:
        # !!! Fuel costs should come from sap_tables
        set_fuel_use(dwelling, "community_distribution", True,
                     community_distribution_elec,
                     .517,
                     0,
                     2.92)

        total_community_emissions = (
            (dwelling.emissions_heating_main
             if dwelling.main_sys_1.system_type == HeatingTypes.community
             else 0) +
            (dwelling.emissions_water
             if dwelling.water_sys.system_type == HeatingTypes.community
             else 0) +
            dwelling.emissions_community_distribution + dwelling.get('emissions_community_elec_credits', 0))

        if total_community_emissions < 0:
            set_fuel_use(dwelling,
                         "negative_community_emissions_correction", True,
                         1,
                         -total_community_emissions,
                         0,
                         0)

    if dwelling.get('main_sys_2') is not None:
        set_fuel_use(dwelling, "heating_main_2", True,
                     dwelling.Q_spaceheat_main_2,
                     dwelling.main_sys_2.co2_factor(),
                     dwelling.main_sys_2.fuel_price(dwelling) / 100,
                     dwelling.main_sys_2.primary_energy_factor())
    else:
        set_fuel_use(dwelling, "heating_main_2", True,
                     0, 0, 0, 0)

    if dwelling.get('secondary_sys') is not None:
        set_fuel_use(dwelling, "heating_secondary", True,
                     dwelling.Q_spaceheat_secondary,
                     dwelling.secondary_sys.co2_factor(),
                     dwelling.secondary_sys.fuel_price(dwelling) / 100.,
                     dwelling.secondary_sys.primary_energy_factor())
    else:
        set_fuel_use(dwelling, "heating_secondary", True,
                     0, 0, 0, 0)

    set_fuel_use(dwelling, "cooling", True,
                 dwelling.Q_spacecooling, C_el, cost_el, PE_el)

    set_fuel_use(dwelling, "fans_and_pumps", True,
                 dwelling.Q_fans_and_pumps, C_el, cost_el, PE_el)

    set_fuel_use(dwelling, "mech_vent_fans", True,
                 dwelling.Q_mech_vent_fans, C_el,
                 dwelling.mech_vent_elec_price / 100,
                 PE_el)

    set_fuel_use(dwelling, "lighting", True,
                 dwelling.annual_light_consumption, C_el, cost_el, PE_el)

    set_fuel_use(dwelling, "appliances", False,
                 sum(dwelling.appliance_consumption), C_el, cost_el, PE_el)

    # For cooking cost, assume that 40% of cooking is by gas, 60% by
    # electric (matches the emissions calc)
    cost_cooking_fuel = .4 * .031 + .6 * cost_el
    pe_cooking_fuel = .4 * 1.02 + .6 * PE_el
    cooking_fuel_kWh = (35 + 7 * dwelling.Nocc) * 8.76
    C_cooking = (119 + 24 * dwelling.Nocc) / dwelling.GFA / cooking_fuel_kWh

    set_fuel_use(dwelling, "cooking", False,
                 cooking_fuel_kWh, C_cooking, cost_cooking_fuel, pe_cooking_fuel)

    set_fuel_use(dwelling, "pv", True,
                 -dwelling.pv_electricity, C_el_offset,
                 (cost_el * dwelling.pv_electricity_onsite_fraction +
                  cost_export * (1 - dwelling.pv_electricity_onsite_fraction)),
                 primary_el_offset)

    set_fuel_use(dwelling, "wind", True,
                 -dwelling.wind_electricity, C_el_offset,
                 (cost_el * dwelling.wind_electricity_onsite_fraction +
                  cost_export * (
                      1 - dwelling.wind_electricity_onsite_fraction)),
                 primary_el_offset)

    set_fuel_use(dwelling, "hydro", True,
                 -dwelling.hydro_electricity, C_el_offset,
                 (cost_el * dwelling.hydro_electricity_onsite_fraction +
                  cost_export * (
                      1 - dwelling.hydro_electricity_onsite_fraction)),
                 primary_el_offset)

    set_fuel_use(dwelling, "chp", True,
                 -dwelling.chp_electricity, C_el_offset,
                 (cost_el * dwelling.chp_electricity_onsite_fraction +
                  cost_export * (
                      1 - dwelling.chp_electricity_onsite_fraction)),
                 primary_el_offset)

    if dwelling.get('appendix_q_systems') is not None:
        for sys in dwelling.appendix_q_systems:
            if 'fuel_saved' in sys:
                set_fuel_use(dwelling, "appendix_q_generated", True,
                             -sys['generated'],
                             sys['fuel_saved'].co2_factor,
                             sys['fuel_saved'].unit_price() / 100,
                             sys['fuel_saved'].primary_energy_factor)
            else:
                set_fuel_use(dwelling, "appendix_q_generated", True,
                             -sys['generated'],
                             C_el,
                             cost_el,
                             PE_el)

            if 'fuel_used' in sys:
                set_fuel_use(dwelling, "appendix_q_used", True,
                             sys['used'],
                             sys['fuel_used'].co2_factor,
                             sys['fuel_used'].unit_price() / 100,
                             sys['fuel_used'].primary_energy_factor)
            else:
                set_fuel_use(dwelling, "appendix_q_used", True,
                             sys['used'],
                             C_el,
                             cost_el,
                             PE_el)