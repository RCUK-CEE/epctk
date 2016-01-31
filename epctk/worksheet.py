import math

import numpy


from .appendix import appendix_m, appendix_g, appendix_c
from .constants import DAYS_PER_MONTH, SUMMER_MONTHS
from .domestic_hot_water import hot_water_use
from .fuel_use import fuel_use
from .lighting import lighting_consumption
from .solar import solar
from .utils import monthly_to_annual
from .ventilation import ventilation


def heat_loss(dwelling):
    """
    Set the attributes `h`, `hlp`, `h_fabric`, `h_bridging`, `h_vent`, `h_vent_annual`
    on the given dwelling object

    Args:
        dwelling:
    """
    if dwelling.get('hlp') is not None:
        # TODO: what is "h"?
        dwelling.h = dwelling.hlp * dwelling.GFA
        return

    UA = sum(e.Uvalue * e.area for e in dwelling.heat_loss_elements)
    A_bridging = sum(e.area for e in dwelling.heat_loss_elements if e.is_external)

    if dwelling.get("Uthermalbridges") is not None:
        h_bridging = dwelling.Uthermalbridges * A_bridging
    else:
        h_bridging = sum(x['length'] * x['y'] for x in dwelling.y_values)

    h_vent = 0.33 * dwelling.infiltration_ach * dwelling.volume

    dwelling.h = UA + h_bridging + h_vent
    dwelling.hlp = dwelling.h / dwelling.GFA

    dwelling.h_fabric = UA
    dwelling.h_bridging = h_bridging
    dwelling.h_vent = h_vent

    dwelling.h_vent_annual = monthly_to_annual(h_vent)


def water_heater_output(dwelling):
    if dwelling.get('fghrs') is not None:
        dwelling.savings_from_fghrs = appendix_g.fghr_savings(dwelling)
    else:
        dwelling.savings_from_fghrs = 0

    dwelling.output_from_water_heater = numpy.maximum(0,
                                                      dwelling.total_water_heating +
                                                      dwelling.input_from_solar +
                                                      dwelling.fghrs_input_from_solar -
                                                      dwelling.savings_from_wwhrs -
                                                      dwelling.savings_from_fghrs)


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


def heating_requirement(dwelling):
    if not dwelling.get('thermal_mass_parameter'):
        ka = 0
        for t in dwelling.thermal_mass_elements:
            ka += t.area * t.kvalue
        dwelling.thermal_mass_parameter = ka / dwelling.GFA

    dwelling.heat_calc_results = calc_heat_required(
        dwelling, dwelling.Texternal_heating, dwelling.winter_heat_gains)
    Q_required = dwelling.heat_calc_results['heat_required']
    for i in SUMMER_MONTHS:
        Q_required[i] = 0
        dwelling.heat_calc_results['loss'][i] = 0
        dwelling.heat_calc_results['utilisation'][i] = 0
        dwelling.heat_calc_results['useful_gain'][i] = 0

    dwelling.Q_required = Q_required


def calc_heat_required(dwelling, Texternal, heat_gains):
    tau = dwelling.thermal_mass_parameter / (3.6 * dwelling.hlp)
    a = 1 + tau / 15.

    # These are for pcdf heat pumps - when heat pump is undersized it
    # can operator for longer hours on some days
    if dwelling.get('longer_heating_days'):
        N24_16_m, N24_9_m, N16_9_m = dwelling.longer_heating_days()
    else:
        N24_16_m, N24_9_m, N16_9_m = (None, None, None)

    L = dwelling.h * (dwelling.living_area_Theating - Texternal)
    util_living = heat_utilisation_factor(a, heat_gains, L)
    Tno_heat_living = temperature_no_heat(Texternal,
                                          dwelling.living_area_Theating,
                                          dwelling.heating_responsiveness,
                                          util_living,
                                          heat_gains,
                                          dwelling.h)

    Tmean_living_area = Tmean(
        Texternal, dwelling.living_area_Theating, Tno_heat_living,
        tau, dwelling.heating_control_type_sys1, N24_16_m, N24_9_m, N16_9_m, living_space=True)

    if dwelling.main_heating_fraction < 1 and dwelling.get('heating_systems_heat_separate_areas'):
        if dwelling.main_heating_fraction > dwelling.living_area_fraction:
            # both systems contribute to rest of house
            weight_1 = 1 - dwelling.main_heating_2_fraction / \
                           (1 - dwelling.living_area_fraction)

            Tmean_other_1 = temperature_rest_of_dwelling(
                dwelling, Texternal, tau, a, L, heat_gains, dwelling.heating_control_type_sys1, N24_16_m, N24_9_m,
                N16_9_m)
            Tmean_other_2 = temperature_rest_of_dwelling(
                dwelling, Texternal, tau, a, L, heat_gains, dwelling.heating_control_type_sys2, N24_16_m, N24_9_m,
                N16_9_m)

            Tmean_other = Tmean_other_1 * \
                          weight_1 + Tmean_other_2 * (1 - weight_1)
        else:
            # only sys2 does rest of house
            Tmean_other = temperature_rest_of_dwelling(
                dwelling, Texternal, tau, a, L, heat_gains, dwelling.heating_control_type_sys2, N24_16_m, N24_9_m,
                N16_9_m)
    else:
        Tmean_other = temperature_rest_of_dwelling(
            dwelling, Texternal, tau, a, L, heat_gains, dwelling.heating_control_type_sys1, N24_16_m, N24_9_m,
            N16_9_m)

    if not dwelling.get('living_area_fraction'):
        dwelling.living_area_fraction = dwelling.living_area / dwelling.GFA

    meanT = dwelling.living_area_fraction * Tmean_living_area + \
            (1 - dwelling.living_area_fraction) * \
            Tmean_other + dwelling.temperature_adjustment
    L = dwelling.h * (meanT - Texternal)
    utilisation = heat_utilisation_factor(a, heat_gains, L)
    return dict(
        tau=tau,
        alpha=a,
        Texternal=Texternal,
        Tmean_living_area=Tmean_living_area,
        Tmean_other=Tmean_other,
        util_living=util_living,
        Tmean=meanT,
        loss=L,
        utilisation=utilisation,
        useful_gain=utilisation * heat_gains,
        heat_required=(range_cooker_factor(dwelling) *
                       0.024 * (
                           L - utilisation * heat_gains) * DAYS_PER_MONTH),
    )


def temperature_rest_of_dwelling(dwelling, Texternal, tau, a, L, heat_gains, control_type, N24_16_m, N24_9_m, N16_9_m):
    Theat_other = heating_temperature_other_space(dwelling.hlp, control_type)
    L = dwelling.h * (Theat_other - Texternal)
    Tno_heat_other = temperature_no_heat(Texternal,
                                         Theat_other,
                                         dwelling.heating_responsiveness,
                                         heat_utilisation_factor(
                                             a, heat_gains, L),
                                         heat_gains,
                                         dwelling.h)
    return Tmean(Texternal, Theat_other, Tno_heat_other, tau, control_type, N24_16_m, N24_9_m, N16_9_m,
                 living_space=False)


def Tmean(Texternal, Theat, Tno_heat, tau, control_type, N24_16_m, N24_9_m, N16_9_m, living_space):
    tc = 4 + 0.25 * tau
    dT = Theat - Tno_heat

    if control_type == 1 or control_type == 2 or living_space:
        # toff1=7
        # toff2=8
        # toff3=0
        # toff4=8
        # weekday
        u1 = temperature_reduction(dT, tc, 7)
        u2 = temperature_reduction(dT, tc, 8)
        Tweekday = Theat - (u1 + u2)

        # weekend
        u3 = 0  # (since Toff3=0)
        u4 = u2  # (since Toff4=Toff2)
        Tweekend = Theat - (u3 + u4)
    else:
        # toff1=9
        # toff2=8
        # toff3=9
        # toff4=8
        u1 = temperature_reduction(dT, tc, 9)
        u2 = temperature_reduction(dT, tc, 8)
        Tweekday = Theat - (u1 + u2)
        Tweekend = Tweekday

    if N24_16_m is None:
        return (5. / 7.) * Tweekday + (2. / 7.) * Tweekend
    else:
        WEm = numpy.array([9, 8, 9, 8, 9, 9, 9, 9, 8, 9, 8, 9])
        WDm = numpy.array([22, 20, 22, 22, 22, 21, 22, 22, 22, 22, 22, 22])
        return ((N24_16_m + N24_9_m) * Theat + (WEm - N24_16_m + N16_9_m) * Tweekend + (
            WDm - N16_9_m - N24_9_m) * Tweekday) / (WEm + WDm)


def temperature_reduction(delta_T, tc, time_off):
    return numpy.where(time_off <= tc,
                       (0.5 * time_off ** 2 / 24) * delta_T / tc,
                       delta_T * (time_off / 24. - (0.5 / 24.) * tc))


def temperature_no_heat(
        Texternal, Theat, responsiveness, heat_utilisation_factor,
        gains, h):
    return (1 - responsiveness) * (Theat - 2) + responsiveness * (Texternal + heat_utilisation_factor * gains / h)


def range_cooker_factor(dwelling):
    """
    Check if the main, system1 or system2 heating has a
    range cooker scaling factor and return it. If not, return 1

    :param dwelling:
    :return: the range cooker scaling factor or 1
    """
    if dwelling.get('range_cooker_heat_required_scale_factor'):
        return dwelling.range_cooker_heat_required_scale_factor

    elif dwelling.main_sys_1.get('range_cooker_heat_required_scale_factor'):
        return dwelling.main_sys_1.range_cooker_heat_required_scale_factor

    elif dwelling.get("main_sys_2") and dwelling.main_sys_2.get('range_cooker_heat_required_scale_factor'):
        return dwelling.main_sys_2.range_cooker_heat_required_scale_factor
    else:
        return 1


def cooling_requirement(dwelling):
    """
    Assign the cooling requirement to the dwelling.
    Note that this modifies the dwelling properties rather than
    returning values

    :param dwelling:
    :return:
    """
    fcool = dwelling.fraction_cooled
    if fcool == 0:
        dwelling.Q_cooling_required = numpy.array([0., ] * 12)
        return

    Texternal_summer = dwelling.external_temperature_summer
    L = dwelling.h * (dwelling.Tcooling - Texternal_summer)
    G = dwelling.summer_heat_gains

    gamma = G / L
    assert not 1 in gamma  # !!! Sort this out!

    tau = dwelling.thermal_mass_parameter / (3.6 * dwelling.hlp)
    a = 1 + tau / 15.
    utilisation = numpy.where(gamma <= 0,
                              1,
                              (1 - gamma ** -a) / (1 - gamma ** -(a + 1)))

    Qrequired = numpy.array([0., ] * 12)
    Qrequired[5:8] = (0.024 * (G - utilisation * L) * DAYS_PER_MONTH)[5:8]

    # No cooling in months where heating would be more than half of cooling
    heat_calc_results = calc_heat_required(
        dwelling, Texternal_summer, G + dwelling.heating_system_pump_gain)
    Qheat_summer = heat_calc_results['heat_required']
    Qrequired = numpy.where(3 * Qheat_summer < Qrequired,
                            Qrequired,
                            0)

    fintermittent = .25
    dwelling.Q_cooling_required = Qrequired * fcool * fintermittent


def heating_temperature_other_space(hlp, control_type):
    hlp = numpy.where(hlp < 6, hlp, 6)
    if control_type == 1:
        return 21. - 0.5 * hlp
    else:
        return 21. - hlp + 0.085 * hlp ** 2


def heat_utilisation_factor(a, heat_gains, heat_loss):
    gamma = heat_gains / heat_loss
    if 1 in gamma:
        # !!! Is this really right??
        raise Exception("Do we ever get here?")
        return numpy.where(gamma != 1,
                           (1 - gamma ** a) / (1 - gamma ** (a + 1)),
                           a / (a + 1))
    else:
        return (1 - gamma ** a) / (1 - gamma ** (a + 1))


def systems(dwelling):
    dwelling.Q_main_1 = dwelling.fraction_of_heat_from_main * dwelling.main_heating_fraction * dwelling.Q_required

    dwelling.sys1_space_effy = dwelling.main_sys_1.space_heat_effy(dwelling.Q_main_1)

    dwelling.Q_spaceheat_main = 100 * dwelling.Q_main_1 / dwelling.sys1_space_effy

    if dwelling.get('main_sys_2'):
        dwelling.Q_main_2 = dwelling.fraction_of_heat_from_main * \
                            dwelling.main_heating_2_fraction * dwelling.Q_required

        dwelling.sys2_space_effy = dwelling.main_sys_2.space_heat_effy(dwelling.Q_main_2)

        dwelling.Q_spaceheat_main_2 = 100 * dwelling.Q_main_2 / dwelling.sys2_space_effy

    else:
        dwelling.Q_spaceheat_main_2 = numpy.zeros(12)
        dwelling.Q_main_2 = [0, ]

    if dwelling.fraction_of_heat_from_main < 1:
        Q_secondary = (1 - dwelling.fraction_of_heat_from_main) * dwelling.Q_required

        dwelling.secondary_space_effy = dwelling.secondary_sys.space_heat_effy(Q_secondary)
        dwelling.Q_spaceheat_secondary = 100 * Q_secondary / dwelling.secondary_space_effy

    else:
        dwelling.Q_spaceheat_secondary = numpy.zeros(12)

    dwelling.water_effy = dwelling.water_sys.water_heat_effy(dwelling.output_from_water_heater)

    if hasattr(dwelling.water_sys, "keep_hot_elec_consumption"):
        dwelling.Q_waterheat = 100 * (
            dwelling.output_from_water_heater - dwelling.combi_loss_monthly) / dwelling.water_effy
    else:
        dwelling.Q_waterheat = 100 * dwelling.output_from_water_heater / dwelling.water_effy

    dwelling.Q_spacecooling = dwelling.Q_cooling_required / dwelling.cooling_seer


def sap(dwelling):
    sap_rating_energy_cost = dwelling.fuel_cost
    ecf = 0.47 * sap_rating_energy_cost / (dwelling.GFA + 45)
    dwelling.sap_energy_cost_factor = ecf
    dwelling.sap_value = 117 - 121 * math.log10(ecf) if ecf >= 3.5 else 100 - 13.95 * ecf

    report = dwelling.report
    report.start_section("", "SAP Calculation")
    report.add_single_result("SAP value", "258", dwelling.sap_value)


def fee(dwelling):
    dwelling.fee_rating = (sum(dwelling.Q_required) + sum(dwelling.Q_cooling_required)) / dwelling.GFA

    r = dwelling.report
    r.start_section("", "FEE Calculation")
    r.add_single_result(
        "Fabric energy efficiency (kWh/m2)", "109", dwelling.fee_rating)


def der(dwelling):
    dwelling.der_rating = dwelling.emissions / dwelling.GFA

    r = dwelling.report
    r.start_section("", "DER Calculation")
    r.add_single_result(
        "Dwelling emissions (kg/yr)", "272", dwelling.emissions)
    r.add_single_result("DER rating (kg/m2/year)", "273", dwelling.der_rating)


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
    Calculate the SAP energy demand for a dwelling
    :param dwelling:
    :return:
    """

    # todo: convert the rest of these to use "update" semantics
    ventilation(dwelling)
    heat_loss(dwelling)
    hot_water_use(dwelling)

    dwelling.update(lighting_consumption(dwelling))

    dwelling.update(internal_heat_gain(dwelling))

    solar(dwelling)
    heating_requirement(dwelling)
    cooling_requirement(dwelling)
    water_heater_output(dwelling)


def perform_full_calc(dwelling):
    """
    Perform a full SAP worksheet calculation on a dwelling, adding the results
    to the dwelling provided.
    This performs a demand calculation, and a renewable energies calculation

    :param dwelling:
    :return:
    """
    perform_demand_calc(dwelling)
    systems(dwelling)

    dwelling.update(appendix_m.pv(dwelling))
    dwelling.update(appendix_m.wind_turbines(dwelling))
    dwelling.update(appendix_m.hydro(dwelling))
    dwelling.update(appendix_c.chp(dwelling))

    fuel_use(dwelling)
