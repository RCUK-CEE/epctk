"""
Appendix M: Energy from Photovoltaic (PV) technology, small and micro wind turbines
and small- scale hydro-electric generators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
import math

from sap.sap_tables import TABLE_H2, TABLE_H4, TABLE_M1


def configure_pv_system(pv_system):
    pv_system['overshading_factor'] = TABLE_H4[pv_system['overshading_category']]

    if str(pv_system['pitch']).lower() != "Horizontal".lower():
        pv_system['Igh'] = TABLE_H2[pv_system['pitch']][pv_system['orientation']]
    else:
        pv_system['Igh'] = TABLE_H2[pv_system['pitch']]


def configure_pv(dwelling):
    for pv_system in dwelling.get('photovoltaic_systems', []):
        configure_pv_system(pv_system)


def configure_wind_turbines(dwelling):
    """
    Set the wind turbine speed correction factor `wind_turbine_speed_correction_factor`
    if the dwelling has 1 or more wind turbines, using interpolated values from Table M1

    :param dwelling:
    :return:
    """
    if dwelling.get('N_wind_turbines', 0) != 0:
        dwelling.wind_turbine_speed_correction_factor = m1_correction_factor(
                dwelling.terrain_type,
                dwelling.wind_turbine_hub_height)


def m1_correction_factor(terrain_type, wind_speed):
    """
    Interpolate the correction factor for the given terrain type
    and standardised wind speed using Table M1

    :param terrain_type:
    :param wind_speed:
    :return:
    """
    interpolation_vals = TABLE_M1[terrain_type]

    closest_above = 999
    closest_below = 0

    for k in list(interpolation_vals.keys()):
        if wind_speed <= k < closest_above:
            closest_above = k
        if wind_speed >= k > closest_below:
            closest_below = k

    if closest_above == 999:
        # Outside of range, return largest
        return interpolation_vals[closest_below]
    elif closest_above == closest_below:
        return interpolation_vals[closest_below]
    else:
        v1 = interpolation_vals[closest_below]
        v2 = interpolation_vals[closest_above]
        return v1 + (v2 - v1) * (wind_speed - closest_below) / (closest_above - closest_below)


def pv(dwelling):
    if dwelling.get('photovoltaic_systems'):
        dwelling.pv_electricity_onsite_fraction = 0.5
        dwelling.pv_electricity = 0
        for pv_system in dwelling.photovoltaic_systems:
            dwelling.pv_electricity += (0.8 * pv_system['kWp'] *
                                        pv_system['Igh'] *
                                        pv_system['overshading_factor'])
    else:
        dwelling.pv_electricity = 0
        dwelling.pv_electricity_onsite_fraction = 0.


def wind_turbines(dwelling):
    """
    Calculate the wind power generated and the graction of wind energy generated onsite

    :param dwelling:
    :return:
    """
    if dwelling.get('N_wind_turbines', 0) > 0:
        wind_speed = 5 * dwelling.wind_turbine_speed_correction_factor
        PA = .6125 * wind_speed ** 3
        CP_G_IE = .24
        A = .25 * math.pi * dwelling.wind_turbine_rotor_diameter ** 2
        p_wind = A * PA * CP_G_IE

        dwelling.wind_electricity = dwelling.N_wind_turbines * p_wind * 1.9 * 8766 * 0.001
        dwelling.wind_electricity_onsite_fraction = 0.7
    else:
        dwelling.wind_electricity = 0
        dwelling.wind_electricity_onsite_fraction = 0


def hydro(dwelling):
    if dwelling.get('hydro_electricity'):
        dwelling.hydro_electricity_onsite_fraction = 0.4
    else:
        dwelling.hydro_electricity = 0
        dwelling.hydro_electricity_onsite_fraction = 0.