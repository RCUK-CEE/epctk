"""
Appendix G: Flue gas heat recovery systems and Waste water heat recovery systems
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
import math

import numpy

from ..constants import DAYS_PER_MONTH
from ..sap_types import HeatingTypes
from ..tables import (MONTHLY_HOT_WATER_TEMPERATURE_RISE, MONTHLY_HOT_WATER_FACTORS, TABLE_H3,
                      combi_loss_table_3a, combi_loss_table_3b, combi_loss_table_3c)
from ..io.pcdf import get_wwhr_system, get_fghr_system
from . import appendix_m


def configure_wwhr(dwelling):
    """
    Configure the waste water heat recovery systems (WWHR) for this dwelling

    Args:
        dwelling:

    """
    if dwelling.get('wwhr_systems'):
        for sys in dwelling.wwhr_systems:
            sys['pcdf_sys'] = get_wwhr_system(sys['pcdf_id'])


def configure_fghr(dwelling):
    """
    Configure Flue Gas Heat Recovery (FGHR) for this dwelling.
    Requires water heating to have been configured already.

    Args:
        dwelling:

    """
    # TODO: Should check that fghr is allowed for this system

    if dwelling.get('fghrs') is not None:
        # TODO: Need to add electrical power G1.4
        # FIXME: Entire fghrs calc is unfinished really
        dwelling.fghrs.update(
                dict(get_fghr_system(dwelling.fghrs['pcdf_id'])))

        if dwelling.fghrs["heat_store"] == "3":
            assert dwelling.water_sys.system_type == HeatingTypes.combi
            assert not dwelling.get('hw_cylinder_volume')
            assert not dwelling.has_hw_cylinder

            dwelling.has_hw_cylinder = True
            dwelling.has_cylinderstat = True
            dwelling.has_hw_time_control = True
            dwelling.hw_cylinder_volume = dwelling.fghrs['heat_store_total_volume']
            dwelling.measured_cylinder_loss = dwelling.fghrs['heat_store_loss_rate']
            dwelling.water_sys.table2b_row = 5

            # !!! This ideally wouldn't be here!  Basically combi loss
            # !!! has already been calculated, but now we are adding a
            # !!! thermal store, so need to recalculate it
            if dwelling.water_sys.get('pcdf_data'):
                configure_combi_loss(dwelling,
                                     dwelling.water_sys,
                                     dwelling.water_sys.pcdf_data)
            else:
                dwelling.water_sys.combi_loss = combi_loss_table_3a(
                        dwelling, dwelling.water_sys)

            if dwelling.fghrs["has_pv_module"]:
                assert "PV_kWp" in dwelling.fghrs
                appendix_m.configure_pv_system(dwelling.fghrs)
                dwelling.fghrs['monthly_solar_hw_factors'] = TABLE_H3[dwelling.fghrs['pitch']]
        else:
            assert not "PV_kWp" in dwelling.fghrs

        if (dwelling.water_sys.system_type in [HeatingTypes.combi,
                                               HeatingTypes.storage_combi] and
                dwelling.water_sys.get('has_no_keep_hot') and not dwelling.has_hw_cylinder):

            dwelling.fghrs['equations'] = dwelling.fghrs['equations_combi_without_keephot_without_ext_store']
        else:
            dwelling.fghrs['equations'] = dwelling.fghrs['equations_other']


def configure_combi_loss(dwelling, sys, pcdf_data):
    """
    Setup the combi losses on the heating system given the dwelling data and the pcdf data

    :param dwelling:
    :param sys:
    :param pcdf_data:
    :return:
    """
    if pcdf_data.get('storage_loss_factor_f2') is not None:
        # FIXME: This will FAIL because combi loss table isn't implemented
        sys.combi_loss = combi_loss_table_3c(dwelling, sys, pcdf_data)

    elif pcdf_data.get('storage_loss_factor_f1') is not None:
        sys.combi_loss = combi_loss_table_3b(pcdf_data)

    else:
        sys.combi_loss = combi_loss_table_3a(dwelling, sys)

    sys.pcdf_data = pcdf_data  # !!! Needed if we later add a store to this boiler


def wwhr_savings(dwelling):
    """
    Calculate the savings (kWh/month) for mixer showers with WWHRS according to equation(G10)
    :param dwelling:
    :return:
    """
    # TODO: Variables were defined but not used
    # savings = 0
    # Nshower_with_bath = 1
    # Nshower_without_bath = 0
    Nshower_and_bath = dwelling.wwhr_total_rooms_with_shower_or_bath

    S_sum = 0
    for sys in dwelling.wwhr_systems:
        effy = sys['pcdf_sys']['effy_mixer_shower'] / 100
        util = sys['pcdf_sys']['utilisation_mixer_shower']
        S_sum += (sys['Nshowers_with_bath'] * .635 * effy *
                  util + sys['Nshowers_without_bath'] * effy * util)

    Seff = S_sum / Nshower_and_bath
    Tcoldm = numpy.array(
            [11.1, 10.8, 11.8, 14.7, 16.1, 18.2, 21.3, 19.2, 18.8, 16.3, 13.3, 11.8])
    Awm = .33 * 25 * MONTHLY_HOT_WATER_TEMPERATURE_RISE / (41 - Tcoldm) + 26.1
    Bwm = .33 * 36 * MONTHLY_HOT_WATER_TEMPERATURE_RISE / (41 - Tcoldm)

    savings = (dwelling.Nocc * Awm + Bwm) * Seff * (35 - Tcoldm) * \
              4.18 * DAYS_PER_MONTH * MONTHLY_HOT_WATER_FACTORS / 3600.

    return savings


def fghr_savings(dwelling):
    if dwelling.fghrs['heat_store'] == 1:
        # !!! untested
        assert False
        Kfl = dwelling.fghrs['direct_useful_heat_recovered']
        return Kfl * Kn * dwelling.total_water_heating

    equation_space_heats = [e['space_heating_requirement']
                            for e in dwelling.fghrs['equations']]

    # !!! Should only use heat provided by this system
    if dwelling.water_sys is dwelling.main_sys_1:
        space_heat_frac = (dwelling.fraction_of_heat_from_main *
                           dwelling.main_heating_fraction)
    elif dwelling.water_sys is dwelling.main_sys_2:
        space_heat_frac = (dwelling.fraction_of_heat_from_main *
                           dwelling.main_heating_2_fraction)
    else:
        # !!! Not allowed to have fghrs on secondary system?
        # !!! Are you even allowed fghrs on hw only systems?
        space_heat_frac = 0

    Qspm = dwelling.Q_required * space_heat_frac

    closest_below = [max(x for x in equation_space_heats
                         if x <= Qspm[month])
                     if Qspm[month] >= min(equation_space_heats)
                     else min(equation_space_heats)
                     for month in range(12)]
    closest_above = [min(x for x in equation_space_heats
                         if x >= Qspm[month])
                     if Qspm[month] <= max(equation_space_heats)
                     else max(equation_space_heats)
                     for month in range(12)]

    closest_below_eqns = [[e for e in dwelling.fghrs['equations']
                           if e['space_heating_requirement'] == Q_req][0]
                          for Q_req in closest_below]
    closest_above_eqns = [[e for e in dwelling.fghrs['equations']
                           if e['space_heating_requirement'] == Q_req][0]
                          for Q_req in closest_above]

    # !!! For some reason solar input from FGHRS doesn't reduce Qhwm
    Qhwm = (dwelling.hw_energy_content +
            dwelling.input_from_solar -
            dwelling.savings_from_wwhrs)

    def calc_S0(equations):
        a = numpy.array([e['a'] for e in equations])
        b = numpy.array([e['b'] for e in equations])
        c = numpy.array([e['c'] for e in equations])

        res = [0, ] * 12
        for month in range(12):
            Q = min(309, max(80, Qhwm[month]))
            res[month] = (a[month] * math.log(Q) +
                          b[month] * Q +
                          c[month]) * min(1, Qhwm[month] / Q)

        return res

    S0_below = calc_S0(closest_below_eqns)
    S0_above = calc_S0(closest_above_eqns)
    S0 = [0, ] * 12
    for month in range(12):
        if closest_above[month] != closest_below[month]:
            S0[month] = S0_below[month] + (S0_above[month] - S0_below[month]) * (
                Qspm[month] - closest_below[month]) / (closest_above[month] - closest_below[month])
        else:
            S0[month] = S0_below[month]

    # !!! Should exit here for intant combi without keep hot and no
    # !!! ext store - S0 is the result

    # !!! Needs factor of 1.3 for CPSU or primary storage combi
    Vk = (dwelling.hw_cylinder_volume if dwelling.get('hw_cylinder_volume')
          else dwelling.fghrs['heat_store_total_volume'])

    if Vk >= 144:
        Kn = 0
    elif Vk >= 75:
        Kn = .48 - Vk / 300.
    elif Vk >= 15:
        Kn = 1.1925 - 0.77 * Vk / 60.
    else:
        Kn = 1

    Kf2 = dwelling.fghrs['direct_total_heat_recovered']
    Sm = S0 + 0.5 * Kf2 * (dwelling.storage_loss +
                           dwelling.primary_circuit_loss +
                           dwelling.combi_loss_monthly -
                           (1 - Kn) * Qhwm)

    # !!! Need to use this for combi with keep hot
    # Sm=S0+0.5*Kf2*(dwelling.combi_loss_monthly-dwelling.water_sys.keep_hot_elec_consumption)

    # savings = [Sm if Qhwm_val > 0 else 0 for Qhwm_val in Qhwm]
    savings = numpy.where(Qhwm > 0,
                          Sm,
                          0)
    return savings