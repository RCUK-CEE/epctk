import math

import numpy

from .tables import TABLE_6D
from .constants import SOLAR_HEATING, SolarConstants


def overshading_factors(dwelling_overshading):
    """
    Set dwelling overshading factors from Table 6D, based on the shading amount

    Args:
        dwelling_overshading:

    Returns:
        dict: key -values for overshading, apply to dwelling using .update

    """
    overshading_factors = TABLE_6D[dwelling_overshading]
    return {key: overshading_factors[key] for key in ['light_access_factor',
                                                      'solar_access_factor_winter',
                                                      'solar_access_factor_summer']}


def incident_solar(Igh, details, orientation, is_roof_window):
    if not is_roof_window:
        return incident_solar_vertical(Igh, details, orientation)
    elif orientation > 330 * math.pi / 180 or orientation < 30 * math.pi / 180:
        return incident_solar_vertical(Igh, details, 0)
    else:
        return Igh


def incident_solar_vertical(Igh, details, orientation):
    return Igh * (details.A + details.B * numpy.cos(orientation) + details.C * numpy.cos(2 * orientation))


def solar_access_factor_winter(dwelling, opening):
    if opening.opening_type.roof_window:
        return 1
    else:
        return dwelling.solar_access_factor_winter


def solar_access_factor_summer(dwelling, opening):
    if opening.opening_type.roof_window:
        return 1
    else:
        return dwelling.solar_access_factor_summer


def solar(dwelling):
    solar_gain_winter = sum(
        0.9 * solar_access_factor_winter(dwelling,
                                         o) * o.opening_type.gvalue * o.opening_type.frame_factor * o.area *
        incident_solar(dwelling.Igh_heating,
                       SOLAR_HEATING,
                       o.orientation_degrees * math.pi / 180,
                       o.opening_type.roof_window)
        for o in dwelling.openings)

    # TODO Really only want to do this if we have cooling
    sol_gain = 0
    for o in dwelling.openings:
        sol_inc = incident_solar(dwelling.Igh_summer,
                                 SolarConstants(dwelling.latitude),
                                 o.orientation_degrees * math.pi / 180,
                                 o.opening_type.roof_window)
        sol_access = solar_access_factor_summer(dwelling, o)
        o_type = o.opening_type

        sol_gain += 0.9 * sol_access * o_type.gvalue * o_type.frame_factor * o.area * sol_inc

    dwelling.solar_gain_summer = sol_gain

    dwelling.summer_heat_gains = dwelling.total_internal_gains_summer + sol_gain

    dwelling.solar_gain_winter = solar_gain_winter

    dwelling.winter_heat_gains = dwelling.total_internal_gains + solar_gain_winter

    return dict(solar_gain_summer=sol_gain,
                summer_heat_gains=dwelling.total_internal_gains_summer + sol_gain,
                solar_gain_winter=solar_gain_winter,
                winter_heat_gains = dwelling.total_internal_gains + solar_gain_winter)
