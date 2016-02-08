import numpy

from .appendix import appendix_b
from .constants import SUMMER_MONTHS, DAYS_PER_MONTH


def heat_utilisation_factor(a, heat_gains, heat_loss):
    """
    Based on Table 9a

    Args:
        a:
        heat_gains:
        heat_loss:

    Returns:

    """
    gamma = heat_gains / heat_loss
    if 1 in gamma:
        # !!! Is this really right??
        raise Exception("Do we ever get here?")
        return numpy.where(gamma != 1,
                           (1 - gamma ** a) / (1 - gamma ** (a + 1)),
                           a / (a + 1))
    else:
        return (1 - gamma ** a) / (1 - gamma ** (a + 1))


def heating_requirement(dwelling):

    dwelling.heat_calc_results = calc_heat_required(
        dwelling, dwelling.Texternal_heating, dwelling.winter_heat_gains)

    q_required = dwelling.heat_calc_results['heat_required']

    for i in SUMMER_MONTHS:
        q_required[i] = 0
        dwelling.heat_calc_results['loss'][i] = 0
        dwelling.heat_calc_results['utilisation'][i] = 0
        dwelling.heat_calc_results['useful_gain'][i] = 0

    return q_required


def calc_heat_required(dwelling, Texternal, heat_gains):
    tau = dwelling.thermal_mass_parameter / (3.6 * dwelling.hlp)
    a = 1 + tau / 15.

    # These are for pcdf heat pumps - when heat pump is undersized it
    # can operator for longer hours on some days
    if dwelling.get('longer_heating_days'):
        N24_16_m, N24_9_m, N16_9_m = dwelling.longer_heating_days()
    else:
        N24_16_m, N24_9_m, N16_9_m = (None, None, None)

    living_area_Theating = dwelling.living_area_Theating
    living_area_fraction = dwelling.living_area_fraction

    L = dwelling.h * (living_area_Theating - Texternal)
    util_living = heat_utilisation_factor(a, heat_gains, L)
    Tno_heat_living = temperature_no_heat(Texternal,
                                          living_area_Theating,
                                          dwelling.heating_responsiveness,
                                          util_living,
                                          heat_gains,
                                          dwelling.h)

    Tmean_living_area = Tmean(
        Texternal, living_area_Theating, Tno_heat_living,
        tau, dwelling.heating_control_type_sys1, N24_16_m, N24_9_m, N16_9_m, living_space=True)

    if dwelling.main_heating_fraction < 1 and dwelling.get('heating_systems_heat_separate_areas'):
        if dwelling.main_heating_fraction > living_area_fraction:
            # both systems contribute to rest of house
            weight_1 = 1 - dwelling.main_heating_2_fraction / (1 - living_area_fraction)

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

    # if not dwelling.get('living_area_fraction'):
    #     # TODO: this should probably be verified right at the start!
    #     living_area_fraction = dwelling.living_area / dwelling.GFA
    #
    #     dwelling.living_area_fraction = living_area_fraction
    # else:
    #     living_area_fraction = dwelling.living_area_fraction

    mean_T = living_area_fraction * Tmean_living_area + (1 - living_area_fraction) * \
                                                       Tmean_other + dwelling.temperature_adjustment
    L = dwelling.h * (mean_T - Texternal)
    utilisation = heat_utilisation_factor(a, heat_gains, L)

    heat_req = (appendix_b.range_cooker_factor(dwelling) * 0.024 * (L - utilisation * heat_gains) * DAYS_PER_MONTH)

    return dict(
        tau=tau,
        alpha=a,
        Texternal=Texternal,
        Tmean_living_area=Tmean_living_area,
        Tmean_other=Tmean_other,
        util_living=util_living,
        Tmean=mean_T,
        loss=L,
        utilisation=utilisation,
        useful_gain=utilisation * heat_gains,
        heat_required=heat_req,
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


def Tmean(Texternal, T_heat, T_no_heat, tau, control_type, N24_16_m, N24_9_m, N16_9_m, living_space):
    """

    Args:
        Texternal:
        T_heat:
        T_no_heat:
        tau:
        control_type:
        N24_16_m:
        N24_9_m:
        N16_9_m:
        living_space:

    Returns:

    """
    # FIXME: why is Texternal supplied but not used?
    tc = 4 + 0.25 * tau
    dT = T_heat - T_no_heat

    if control_type == 1 or control_type == 2 or living_space:
        # toff1=7
        # toff2=8
        # toff3=0
        # toff4=8
        # weekday
        u1 = temperature_reduction(dT, tc, 7)
        u2 = temperature_reduction(dT, tc, 8)
        Tweekday = T_heat - (u1 + u2)

        # weekend
        u3 = 0  # (since Toff3=0)
        u4 = u2  # (since Toff4=Toff2)
        Tweekend = T_heat - (u3 + u4)
    else:
        # toff1=9
        # toff2=8
        # toff3=9
        # toff4=8
        u1 = temperature_reduction(dT, tc, 9)
        u2 = temperature_reduction(dT, tc, 8)
        Tweekday = T_heat - (u1 + u2)
        Tweekend = Tweekday

    if N24_16_m is None:
        return (5. / 7.) * Tweekday + (2. / 7.) * Tweekend
    else:
        WEm = numpy.array([9, 8, 9, 8, 9, 9, 9, 9, 8, 9, 8, 9])
        WDm = numpy.array([22, 20, 22, 22, 22, 21, 22, 22, 22, 22, 22, 22])
        return ((N24_16_m + N24_9_m) * T_heat + (WEm - N24_16_m + N16_9_m) * Tweekend + (
            WDm - N16_9_m - N24_9_m) * Tweekday) / (WEm + WDm)


def temperature_reduction(delta_T, tc, time_off):
    return numpy.where(time_off <= tc,
                       (0.5 * time_off ** 2 / 24) * delta_T / tc,
                       delta_T * (time_off / 24. - (0.5 / 24.) * tc))


def temperature_no_heat(
        Texternal, Theat, responsiveness, heat_utilisation_factor, gains, h):
    return (1 - responsiveness) * (Theat - 2) + responsiveness * (Texternal + heat_utilisation_factor * gains / h)


def heating_temperature_other_space(hlp, control_type):
    hlp = numpy.where(hlp < 6, hlp, 6)
    if control_type == 1:
        return 21. - 0.5 * hlp
    else:
        return 21. - hlp + 0.085 * hlp ** 2


