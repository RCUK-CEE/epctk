import math

import numpy

from .constants import DAYS_PER_MONTH


def _lighting_sum(openings):
    return sum(0.9 * o.area * o.opening_type.frame_factor * o.opening_type.light_transmittance for o in openings)


def calc_low_energy_bulb_ratio(lighting_outlets_total, lighting_outlets_low_energy):
    """
    Calculate the low energy bulb ratio according to

    .. todo::
        Determine where in SAP this is defined

    Args:
        lighting_outlets_low_energy:
        lighting_outlets_total:

    Returns:

    """
    return int(100 * float(lighting_outlets_low_energy) / lighting_outlets_total + 0.5) / 100.0


def lighting_consumption_variables(N_occ, grnd_flr_a, openings, light_access_factor, low_energy_bulb_ratio):
    """
    Get the lighting consumption variables according to

    .. todo::
        Determine where in SAP this is defined and note here.

    Args:
        N_occ:
        grnd_flr_a:
        openings:
        light_access_factor:
        low_energy_bulb_ratio:

    Returns:
        dict: with keys
                low_energy_bulb_ratio
                annual_light_consumption
                full_light_gain
                lighting_C1
                lighting_GL,
                lighting_C2
    """

    mean_light_energy = 59.73 * (grnd_flr_a * N_occ) ** 0.4714

    C1 = 1 - 0.5 * low_energy_bulb_ratio

    window_openings = (o for o in openings if not o.opening_type.roof_window and not o.opening_type.bfrc_data)

    GLwin = _lighting_sum(window_openings) * light_access_factor / grnd_flr_a

    roof_openings = (o for o in openings if o.opening_type.roof_window and not o.opening_type.bfrc_data)
    GLroof = _lighting_sum(roof_openings) / grnd_flr_a

    # Use frame factor of 0.7 for bfrc rated windows
    window_bfrc_openings = (o for o in openings if not o.opening_type.roof_window and o.opening_type.bfrc_data)
    GLwin_bfrc = _lighting_sum(window_bfrc_openings) * 0.7 * 0.9 * light_access_factor / grnd_flr_a

    roof_bfrc_openings = (o for o in openings if o.opening_type.roof_window and o.opening_type.bfrc_data)
    GLroof_bfrc = _lighting_sum(roof_bfrc_openings) * 0.7 * 0.9 / grnd_flr_a

    GL = GLwin + GLroof + GLwin_bfrc + GLroof_bfrc
    C2 = 52.2 * GL ** 2 - 9.94 * GL + 1.433 if GL <= 0.095 else 0.96
    EL = mean_light_energy * C1 * C2
    light_consumption = EL * \
                        (1 + 0.5 * numpy.cos((2. * math.pi / 12.) * ((numpy.arange(12) + 1) - 0.2))) * \
                        DAYS_PER_MONTH / 365

    return dict(low_energy_bulb_ratio=low_energy_bulb_ratio,
                annual_light_consumption=sum(light_consumption),
                full_light_gain=light_consumption * (0.85 * 1000 / 24.) / DAYS_PER_MONTH,
                lighting_C1=C1,
                lighting_GL=GL,
                lighting_C2=C2)


def lighting_consumption(dwelling):
    low_energy_bulb_ratio = dwelling.get('low_energy_bulb_ratio')
    if not low_energy_bulb_ratio:
        low_energy_bulb_ratio = calc_low_energy_bulb_ratio(dwelling.lighting_outlets_total,
                                                           dwelling.lighting_outlets_low_energy)
        dwelling.low_energy_bulb_ratio = low_energy_bulb_ratio

    lights = lighting_consumption_variables(dwelling.Nocc,
                                   dwelling.GFA,
                                   dwelling.openings,
                                   dwelling.light_access_factor,
                                   low_energy_bulb_ratio)
    return lights

