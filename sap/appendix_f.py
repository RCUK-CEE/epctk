"""
Appendix F: Electric CPSUs
~~~~~~~~~~~~~~~~~~~~~~~~~~

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