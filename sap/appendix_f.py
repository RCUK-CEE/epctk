"""
Appendix F: Electric CPSUs
~~~~~~~~~~~~~~~~~~~~~~~~~~

An electric CPSU is a central heating system providing space and domestic water heating.
Primary water heated mainly during low-rate periods to up to 95°C in winter is stored
in a thermal store. If the CPSU volume is less than 270 litres, the resulting high-rate
fraction can lead to a poor SAP rating.

The procedure in this appendix applies for a 10-hour off-peak tariff providing 3 low-rate
periods per day. It is not valid for other tariffs.

"""
import numpy

from .sap_constants import DAYS_PER_MONTH


def appendix_f_cpsu_on_peak(system, dwelling):
    """
    39m=dwelling.h
    45m=hw_energy_content
    93m=Tmean
    95m=useful gains
    98m=Q_required

    :param dwelling:
    :param system:
    """

    Vcs = dwelling.hw_cylinder_volume
    Tw = dwelling.water_sys.cpsu_Tw
    Cmax = .1456 * Vcs * (Tw - 48)
    nm = DAYS_PER_MONTH

    Tmin = ((dwelling.h * dwelling.heat_calc_results['Tmean']) - Cmax + (
        1000 * dwelling.hw_energy_content / (24 * nm)) -
            dwelling.heat_calc_results['useful_gain']) / dwelling.h

    Text = dwelling.Texternal_heating
    Eonpeak = numpy.where(
            Tmin - Text == 0,
            0.024 * dwelling.h * nm,
            (0.024 * dwelling.h * nm * (Tmin - Text)) / (1 - numpy.exp(-(Tmin - Text))))

    F = Eonpeak / (dwelling.hw_energy_content + dwelling.Q_required)
    for i in range(5, 9):
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