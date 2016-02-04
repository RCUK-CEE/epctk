"""
 SPACE COOLING REQUIREMENT
~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
import numpy

from .constants import DAYS_PER_MONTH
from .heating import calc_heat_required
from .tables import TABLE_10C


def configure_cooling_system(dwelling):
    """

    The space cooling requirement should always be calculated (section 8c of the worksheet).

    It is included in the DER and ratings if the dwelling has a fixed air conditioning system.
    This is based on standardised cooling patterns of 6 hours/day operation and cooling of part
    of or all the dwelling to 24°C. Details are given in Tables 10, 10a and 10b and the associated equations.

    Args:
        dwelling:

    Returns:

    """
    if dwelling.get('cooled_area', 0) and dwelling.cooled_area > 0:
        fraction_cooled = dwelling.cooled_area / dwelling.GFA

        if dwelling.get("cooling_tested_eer"):
            cooling_eer = dwelling.cooling_tested_eer
        elif dwelling.cooling_packaged_system:
            cooling_eer = TABLE_10C[dwelling.cooling_energy_label]['packaged_sys_eer']
        else:
            cooling_eer = TABLE_10C[dwelling.cooling_energy_label]['split_sys_eer']

        if dwelling.cooling_compressor_control == 'on/off':
            cooling_seer = 1.25 * cooling_eer
        else:
            cooling_seer = 1.35 * cooling_eer
    else:
        fraction_cooled = 0
        cooling_seer = 1  # Need a number, but doesn't matter what

    dwelling.fraction_cooled = fraction_cooled
    dwelling.cooling_seer = cooling_seer


def cooling_requirement(dwelling):
    """
    Calculate the dwelling cooling requirement


    Args:
        dwelling

    Returns:
        Q_cooling_requirement
    """
    fcool = dwelling.fraction_cooled
    if fcool == 0:
        return numpy.array([0., ] * 12)

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

    fintermittent = 0.25
    return Qrequired * fcool * fintermittent
