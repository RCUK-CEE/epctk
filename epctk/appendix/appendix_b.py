"""
Gas and oil boiler systems, boilers with a thermal store, and range cooker boilers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. todo::
  Determine what code should be moved into Appendix B. The main thing seems to be products in the PCDF database

"""


def range_cooker_factor(dwelling):
    """
    Check if the main, system1 or system2 heating has a
    range cooker scaling factor and return it. If not, return 1

    :param dwelling:
    :return: the range cooker scaling factor or 1
    """
    if dwelling.get('range_cooker_heat_required_scale_factor'):
        return dwelling.range_cooker_heat_required_scale_factor

    elif dwelling.main_sys_1.get('range_cooker_heat_required_scale_factor'):
        return dwelling.main_sys_1.range_cooker_heat_required_scale_factor

    elif dwelling.get("main_sys_2") and dwelling.main_sys_2.get('range_cooker_heat_required_scale_factor'):
        return dwelling.main_sys_2.range_cooker_heat_required_scale_factor
    else:
        return 1