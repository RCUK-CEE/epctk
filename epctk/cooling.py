"""
Part 10 SPACE COOLING REQUIREMENT
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
from .tables import TABLE_10C


def configure_cooling_system(dwelling):
    """
    Part 10 SPACE COOLING REQUIREMENT

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