import math

import numpy

from sap.constants import DAYS_PER_MONTH


def GL_sum(openings):
    return sum(0.9 * o.area * o.opening_type.frame_factor * o.opening_type.light_transmittance for o in openings)


def lighting_consumption(dwelling):
    mean_light_energy = 59.73 * (dwelling.GFA * dwelling.Nocc) ** 0.4714

    if not dwelling.get('low_energy_bulb_ratio'):
        dwelling.low_energy_bulb_ratio = int(
                100 * float(dwelling.lighting_outlets_low_energy) / dwelling.lighting_outlets_total + .5) / 100.

    C1 = 1 - 0.5 * dwelling.low_energy_bulb_ratio

    window_openings = (o for o in dwelling.openings if not o.opening_type.roof_window and not o.opening_type.bfrc_data)
    GLwin = GL_sum(window_openings) * dwelling.light_access_factor / dwelling.GFA

    roof_openings = (o for o in dwelling.openings if o.opening_type.roof_window and not o.opening_type.bfrc_data)
    GLroof = GL_sum(roof_openings) / dwelling.GFA

    # Use frame factor of 0.7 for bfrc rated windows
    window_bfrc_openings = (o for o in dwelling.openings if not o.opening_type.roof_window and o.opening_type.bfrc_data)
    GLwin_bfrc = GL_sum(window_bfrc_openings) * 0.7 * 0.9 * dwelling.light_access_factor / dwelling.GFA

    roof_bfrc_openings = (o for o in dwelling.openings if o.opening_type.roof_window and o.opening_type.bfrc_data)
    GLroof_bfrc = GL_sum(roof_bfrc_openings) * 0.7 * 0.9 / dwelling.GFA

    GL = GLwin + GLroof + GLwin_bfrc + GLroof_bfrc
    C2 = 52.2 * GL ** 2 - 9.94 * GL + 1.433 if GL <= 0.095 else 0.96
    EL = mean_light_energy * C1 * C2
    light_consumption = EL * \
                        (1 + 0.5 * numpy.cos((2. * math.pi / 12.) * ((numpy.arange(12) + 1) - 0.2))) * \
                        DAYS_PER_MONTH / 365
    dwelling.annual_light_consumption = sum(light_consumption)
    dwelling.full_light_gain = light_consumption * \
                               (0.85 * 1000 / 24.) / DAYS_PER_MONTH

    dwelling.lighting_C1 = C1
    dwelling.lighting_GL = GL
    dwelling.lighting_C2 = C2