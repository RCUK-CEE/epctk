"""
Electric CPSUs
~~~~~~~~~~~~~~

An electric CPSU is a central heating system providing space and domestic water heating.
Primary water heated mainly during low-rate periods to up to 95°C in winter is stored
in a thermal store. If the CPSU volume is less than 270 litres, the resulting high-rate
fraction can lead to a poor SAP rating.

The procedure in this appendix applies for a 10-hour off-peak tariff providing 3 low-rate
periods per day. It is not valid for other tariffs.

"""
import numpy

from ..constants import DAYS_PER_MONTH, SUMMER_MONTHS, T_EXTERNAL_HEATING


def cpsu_on_peak(cpsu_Tw, heat_calc_results, hw_cylinder_volume, hw_energy_content, h):
    """
    39m=dwelling.h
    45m=hw_energy_content
    93m=Tmean
    95m=useful gains
    98m=Q_required

    :param dwelling:
    :param system:
    """

    Vcs = hw_cylinder_volume
    Tw = cpsu_Tw
    Text = T_EXTERNAL_HEATING
    Cmax = 0.1456 * Vcs * (Tw - 48)
    nm = DAYS_PER_MONTH

    Tmin = ((h * heat_calc_results['Tmean']) - Cmax + (
        1000 * hw_energy_content / (24 * nm)) -
            heat_calc_results['useful_gain']) / h

    Eonpeak = numpy.where(
            Tmin - Text == 0,
            0.024 * h * nm,
            (0.024 * h * nm * (Tmin - Text)) / (1 - numpy.exp(-(Tmin - Text))))

    q_required = heat_calc_results['heat_required']

    F = Eonpeak / (hw_energy_content + q_required)
    for i in SUMMER_MONTHS:
        F[i] = 0
    return F


def cpsu_store(dwelling):
    if dwelling.get('measured_cylinder_loss'):
        temperature_factor = .89
    else:
        temperature_factor = 1.08

    if dwelling.get('has_hw_time_control'):
        temperature_factor *= 0.81

    # Check airing cupboard
    if getattr(dwelling.water_sys, 'cpsu_not_in_airing_cupboard', False) is True:
        # !!! Actually this is if cpsu or thermal store not in airing cupboard
        temperature_factor *= 1.1

    return temperature_factor


def elec_cpsu_store(dwelling):
    if dwelling.get('measured_cylinder_loss'):
        return 1.09 + 0.012 * (dwelling.water_sys.cpsu_Tw - 85)
    else:
        return 1