import math

import numpy

from .constants import DAYS_PER_MONTH
from .cooling import cooling_requirement
from .heating import heating_requirement
from .domestic_hot_water import hot_water_use
from .fuel_use import fuel_use
from .lighting import lighting_consumption
from .solar import solar
from .utils import monthly_to_annual
from .ventilation import ventilation
from .appendix import appendix_m, appendix_g, appendix_c


def heat_loss(dwelling):
    """
    Return the attributes
    `h` (Total heat loss),
    `hlp` (Heat Loss Parameter per square meter),
    `h_fabric`,
    `h_bridging`,
    `h_vent`,
    `h_vent_annual`

    Args:
        dwelling:

    Returns:
        dict of heat loss attributes, to be added to dwelling using `update()`
    """
    # TODO: what is "h"?
    if dwelling.get('hlp') is not None:
        return dict(h=dwelling.hlp * dwelling.GFA, hlp=dwelling.hlp)

    UA = sum(e.Uvalue * e.area for e in dwelling.heat_loss_elements)
    A_bridging = sum(e.area for e in dwelling.heat_loss_elements if e.is_external)

    if dwelling.get("Uthermalbridges") is not None:
        h_bridging = dwelling.Uthermalbridges * A_bridging
    else:
        h_bridging = sum(x['length'] * x['y'] for x in dwelling.y_values)

    h_vent = 0.33 * dwelling.infiltration_ach * dwelling.volume

    h = UA + h_bridging + h_vent
    return dict(
        h=h,
        hlp=h / dwelling.GFA,  # TODO shouldn't this be Total floor area?
        h_fabric=UA,
        h_bridging=h_bridging,
        h_vent=h_vent,
        h_vent_annual=monthly_to_annual(h_vent))


def calculate_savings_from_fghrs(dwelling):
    # Calculate flue gas heat recovery savings
    if dwelling.get('fghrs') is not None:
        return appendix_g.fghr_savings(dwelling)
    else:
        return 0


def water_heater_output(dwelling):
    """
    Calculate the water heater output

    Note: requires that total_water_heating, input_from_solar,fghrs_input_from_solar,
    savings_from_wwhrs, savings_from_fghrs have been calculated and assigned on dwelling object

    Args:
        dwelling:

    Returns:

    """

    return max(0,
               dwelling.total_water_heating +
               dwelling.input_from_solar +
               dwelling.fghrs_input_from_solar -
               dwelling.savings_from_wwhrs -
               dwelling.savings_from_fghrs)


    # return dict(output_from_water_heater = max(0,
    #                      dwelling.total_water_heating +
    #                      dwelling.input_from_solar +
    #                      dwelling.fghrs_input_from_solar -
    #                      dwelling.savings_from_wwhrs -
    #                      dwelling.savings_from_fghrs),
    #             savings_from_fghrs=
    #             )


def internal_heat_gain(dwelling):
    """
    Calculate internal heat games.

    .. note::
        must have calculated the lighting first so that it can be
            included in the internal heat gains

    Args:
        dwelling:

    Returns:

    """
    losses_gain = -40 * dwelling.Nocc
    water_heating_gains = (1000. / 24.) * dwelling.heat_gains_from_hw / DAYS_PER_MONTH

    mean_appliance_energy = 207.8 * (dwelling.GFA * dwelling.Nocc) ** 0.4714
    appliance_consumption_per_day = (mean_appliance_energy / 365.) * (
        1 + 0.157 * numpy.cos((2. * math.pi / 12.) * (numpy.arange(12) - .78)))

    appliance_consumption = appliance_consumption_per_day * DAYS_PER_MONTH

    if dwelling.reduced_gains:
        met_gain = 50 * dwelling.Nocc
        cooking_gain = 23 + 5 * dwelling.Nocc
        appliance_gain = (0.67 * 1000. / 24) * appliance_consumption_per_day
        light_gain = 0.4 * dwelling.full_light_gain
    else:
        met_gain = 60 * dwelling.Nocc
        cooking_gain = 35 + 7 * dwelling.Nocc
        appliance_gain = (1000. / 24) * appliance_consumption_per_day
        light_gain = dwelling.full_light_gain

    total_internal_gains = (met_gain
                            + light_gain
                            + appliance_gain
                            + cooking_gain
                            + water_heating_gains
                            + dwelling.pump_gain
                            + losses_gain)

    if dwelling.reduced_gains:
        summer_met_gain = 60 * dwelling.Nocc
        summer_cooking_gain = 35 + 7 * dwelling.Nocc
        summer_appliance_gain = (1000. / 24) * appliance_consumption_per_day
        summer_light_gain = dwelling.full_light_gain
        total_internal_gains_summer = (summer_met_gain +
                                       water_heating_gains +
                                       summer_light_gain +
                                       summer_appliance_gain +
                                       summer_cooking_gain +
                                       dwelling.pump_gain +
                                       losses_gain
                                       - dwelling.heating_system_pump_gain)
    else:
        total_internal_gains_summer = total_internal_gains - dwelling.heating_system_pump_gain

    # Apply results to dwelling
    return dict(appliance_consumption=appliance_consumption,
                met_gain=met_gain,
                cooking_gain=cooking_gain,
                appliance_gain=appliance_gain,
                light_gain=light_gain,
                water_heating_gains=water_heating_gains,
                losses_gain=losses_gain,
                total_internal_gains=total_internal_gains,
                total_internal_gains_summer=total_internal_gains_summer)


def heating_systems_energy(dwelling):
    Q_main_1 = dwelling.fraction_of_heat_from_main * dwelling.main_heating_fraction * dwelling.Q_required

    sys1_space_effy = dwelling.main_sys_1.space_heat_effy(Q_main_1)

    Q_spaceheat_main = 100 * Q_main_1 / sys1_space_effy

    if dwelling.get('main_sys_2'):
        Q_main_2 = dwelling.fraction_of_heat_from_main * \
                   dwelling.main_heating_2_fraction * dwelling.Q_required

        sys2_space_effy = dwelling.main_sys_2.space_heat_effy(Q_main_2)

        Q_spaceheat_main_2 = 100 * Q_main_2 / sys2_space_effy

    else:
        Q_spaceheat_main_2 = numpy.zeros(12)
        Q_main_2 = [0, ]
        sys2_space_effy = None

    if dwelling.fraction_of_heat_from_main < 1:
        q_secondary = (1 - dwelling.fraction_of_heat_from_main) * dwelling.Q_required

        secondary_space_effy = dwelling.secondary_sys.space_heat_effy(q_secondary)
        q_spaceheat_secondary = 100 * q_secondary / secondary_space_effy

    else:
        q_spaceheat_secondary = numpy.zeros(12)
        secondary_space_effy = None

    water_effy = dwelling.water_sys.water_heat_effy(dwelling.output_from_water_heater)

    if hasattr(dwelling.water_sys, "keep_hot_elec_consumption"):
        Q_waterheat = 100 * (
            dwelling.output_from_water_heater - dwelling.combi_loss_monthly) / water_effy
    else:
        Q_waterheat = 100 * dwelling.output_from_water_heater / water_effy

    return dict(
        Q_main_1=Q_main_1,
        sys1_space_effy=sys1_space_effy,
        Q_spaceheat_main=Q_spaceheat_main,
        Q_main_2=Q_main_2,
        Q_spaceheat_main_2=Q_spaceheat_main_2,
        sys2_space_effy=sys2_space_effy,
        secondary_space_effy=secondary_space_effy,
        Q_spaceheat_secondary=q_spaceheat_secondary,
        water_effy=water_effy,
        Q_waterheat=Q_waterheat,
        Q_spacecooling=dwelling.Q_cooling_required / dwelling.cooling_seer)


def sap(ground_floor_area, fuel_cost):
    sap_rating_energy_cost = fuel_cost
    ecf = 0.47 * sap_rating_energy_cost / (ground_floor_area + 45)
    energy_cost_factor = ecf
    sap_value = 117 - 121 * math.log10(ecf) if ecf >= 3.5 else 100 - 13.95 * ecf
    return sap_value, energy_cost_factor


    # report = dwelling.report
    # report.start_section("", "SAP Calculation")
    # report.add_single_result("SAP value", "258", dwelling.sap_value)


def fee(ground_floor_area, q_required, q_cooling_required):
    return (sum(q_required) + sum(q_cooling_required)) / ground_floor_area

    # r = dwelling.report
    # r.start_section("", "FEE Calculation")
    # r.add_single_result(
    #     "Fabric energy efficiency (kWh/m2)", "109", dwelling.fee_rating)


def der(ground_floor_area, emissions):
    return emissions / ground_floor_area

    # r = dwelling.report
    # r.start_section("", "DER Calculation")
    # r.add_single_result(
    #     "Dwelling emissions (kg/yr)", "272", dwelling.emissions)
    # r.add_single_result("DER rating (kg/m2/year)", "273", dwelling.der_rating)


def ter(dwelling, heating_fuel):
    # Need to convert from 2010 emissions factors used in the calc to
    # 2006 factors
    C_h = ((dwelling.emissions_water +
            dwelling.emissions_heating_main) / dwelling.main_sys_1.fuel.emission_factor_adjustment +
           (dwelling.emissions_heating_secondary +
            dwelling.emissions_fans_and_pumps) / dwelling.electricity_tariff.emission_factor_adjustment)
    C_l = dwelling.emissions_lighting / \
          dwelling.electricity_tariff.emission_factor_adjustment

    FF = heating_fuel.fuel_factor
    EFA_h = heating_fuel.emission_factor_adjustment
    EFA_l = dwelling.electricity_tariff.emission_factor_adjustment
    dwelling.ter_rating = (C_h * FF * EFA_h + C_l * EFA_l) * (
        1 - 0.2) * (1 - 0.25) / dwelling.GFA

    r = dwelling.report
    r.start_section("", "TER Calculation")
    r.add_single_result(
        "Emissions per m2 for space and water heating", "272a", C_h / dwelling.GFA)
    r.add_single_result(
        "Emissions per m2 for lighting", "272b", C_l / dwelling.GFA)
    r.add_single_result("Heating fuel factor", None, FF)
    r.add_single_result("Heating fuel emission factor adjustment", None, EFA_h)
    r.add_single_result("Electricity emission factor adjustment", None, EFA_l)
    r.add_single_result("TER", 273, dwelling.ter_rating)


def perform_demand_calc(dwelling):
    """
    Calculate the SAP energy demand for a dwelling, adding the result to
    the dwelling object

    Args:
        dwelling (Dwelling):

    """

    # TODO: modify functions to take only the arguments they need instead of the whole dwelling data.
    dwelling.update(ventilation(dwelling))

    dwelling.update(heat_loss(dwelling))

    dwelling.update(hot_water_use(dwelling))

    dwelling.update(lighting_consumption(dwelling))

    dwelling.update(internal_heat_gain(dwelling))

    dwelling.update(solar(dwelling))

    # Need to copy the Q_required from the heat calc results to it's own attribute for compatibility
    dwelling.heat_calc_results = heating_requirement(dwelling)
    dwelling.Q_required = dwelling.heat_calc_results['heat_required']

    dwelling.Q_cooling_required = cooling_requirement(dwelling)

    dwelling.savings_from_fghrs = calculate_savings_from_fghrs(dwelling)

    dwelling.output_from_water_heater = water_heater_output(dwelling)

    return dwelling


def perform_full_calc(dwelling):
    """
    Perform a full SAP worksheet calculation on a dwelling, adding the results
    to the dwelling provided.
    This performs a demand calculation, and a renewable energies calculation

    Args:
        dwelling:


    """
    dwelling = perform_demand_calc(dwelling)
    dwelling.update(heating_systems_energy(dwelling))
    dwelling.update(appendix_m.pv(dwelling))
    dwelling.update(appendix_m.wind_turbines(dwelling))
    dwelling.update(appendix_m.hydro(dwelling))
    dwelling.update(appendix_c.chp(dwelling))

    dwelling.update(fuel_use(dwelling))

    return dwelling
