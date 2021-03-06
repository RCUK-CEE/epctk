"""
Ventilation
~~~~~~~~~~~

Configure the ventilation according to section 2 of SAP

"""
import numpy

from .elements import VentilationTypes, DuctTypes, WallTypes
from .io.pcdf import get_mev_system
from .tables import (mech_vent_default_in_use_factor, mech_vent_default_hr_effy_factor,
                     mech_vent_in_use_factor, mech_vent_in_use_factor_hr, FLOOR_INFILTRATION)
from .utils import monthly_to_annual, SAPInputError


def ventilation_properties(dwelling):
    """

    Calculate the adjusted Specific Fan Power (SFP) as a function of the ventilation
    system configuration

    Mechanical ventilation:

    (a) Positive input ventilation (PIV)
        Positive input ventilation is a fan driven ventilation system, which
        often provides ventilation to the dwelling from the loft space. The
        SAP calculation procedure for systems which use the loft to pre-heat
        the ventilation air is the same as for natural ventilation, including
        20 m3/h ventilation rate equivalent to two extract fans or passive vents.
        (The energy used by the fan is taken as counterbalancing the effect of
        using slightly warmer air from the loft space compared with outside).
        Some positive input ventilation systems supply the air directly from
        the outside and the procedure for these systems is the same as for
        mechanical extract ventilation.

    (b) Mechanical extract ventilation (MEV)
        MEV is a fan driven ventilation system, which only extracts air from
        the dwelling. The SAP calculation is based on a throughput of 0.5 air
        changes per hour through the mechanical system, plus infiltration.
        MEV can be either:

            - Centralised: air is extracted from wet rooms via ducting and expelled by
              means of a central fan., or
            - Decentralised: air is extracted by continuously-running fans in each wet room.

    (c) Balanced whole house mechanical ventilation
        Balanced ventilation provides fresh air to habitable rooms in the
        dwelling and extracts exhaust air from wet rooms.
        A balanced system without heat recovery extracts from wet rooms via
        ducting and expelled by a central fan. Air is also supplied to habitable
        rooms, either via ducting and a central fan or by individual supply air
        fans in each habitable room.
        In a balanced system with heat recovery (MVHR) both the extract and supply
        air are provided via ducting, with a heat exchanger between the outgoing and incoming air.

    Args:
        dwelling:

    Returns:

    """
    ventilation_type = dwelling.ventilation_type
    mv_approved = dwelling.get('mv_approved', False)

    # Assume NONE duct type if there is none set for this dwelling.
    mv_ducttype = dwelling.get('mv_ducttype')

    extra_props = {}

    if ventilation_type == VentilationTypes.PIV_FROM_OUTSIDE:
        adjusted_fan_sfp = piv_sfp(mv_ducttype, mv_approved, ventilation_type, dwelling.get('piv_sfp'))

    elif ventilation_type == VentilationTypes.MEV_CENTRALISED:
        adjusted_fan_sfp = mev_centralised_sfp(mv_ducttype, mv_approved, ventilation_type,
                                               dwelling.get('mev_sfp'))

    elif ventilation_type == VentilationTypes.MEV_DECENTRALISED:
        adjusted_fan_sfp = mev_decentralised_sfp(dwelling, mv_ducttype, mv_approved, ventilation_type, dwelling.get('mev_sys_pcdf_id'))

    elif ventilation_type == VentilationTypes.MVHR:
        adjusted_fan_sfp = mvhr_sfp(mv_ducttype, mv_approved, ventilation_type, dwelling.get('mvhr_sfp'))

        # Special case for MVHR where we need to set additional properties
        extra_props = mvhr_additional_properties(mv_ducttype, mv_approved, ventilation_type, dwelling.get('mvhr_effy'), dwelling.get('mvhr_sfp'))

    elif ventilation_type == VentilationTypes.MV:
        adjusted_fan_sfp = set_mv_dwelling_properties(mv_ducttype, mv_approved, ventilation_type, dwelling.get('mv_sfp'))

    elif ventilation_type == VentilationTypes.NATURAL:
        # TODO: should we just not set this, or set it to None?
        adjusted_fan_sfp = 0
    else:
        raise SAPInputError(ventilation_type)

    return dict(adjusted_fan_sfp=adjusted_fan_sfp, **extra_props)


def mev_centralised_sfp(mv_ducttype, mv_approved, ventilation_type, mev_sfp=None):
    if mev_sfp:
        sfp = mev_sfp
        in_use_factor = mech_vent_in_use_factor(ventilation_type, mv_ducttype, mv_approved)
    else:
        sfp = 0.8  # Table 4g
        in_use_factor = mech_vent_default_in_use_factor()

    if mv_approved:
        assert False

    return sfp * in_use_factor


def mev_decentralised_sfp(dwelling, mv_ducttype, mv_approved, ventilation_type, mev_sys_pcdf_id=None):
    """
    Specific fan power for decentralised MEV.

    Args:
        dwelling: dwelling is (unfortunately) required to lookup each MEV config.
          .. todo::
           if decentralised MEV was just stored as array could just pass in the array,
           making things clearere and more testable. Need to find where this is set and correct throughout
           code base.
        mv_ducttype:
        mv_approved:
        ventilation_type:
        mev_sys_pcdf_id:

    Returns:

    """
    if mev_sys_pcdf_id:
        sys = get_mev_system(mev_sys_pcdf_id)
        get_sfp = lambda conf: sys['configs'][conf]['sfp']
    else:
        get_sfp = lambda conf: dwelling["mev_fan_" + conf + "_sfp"]

    total_flow = 0
    sfp_sum = 0

    for location in ['room', 'duct', 'wall']:
        this_duct_type = (DuctTypes.NONE if location == 'wall' else mv_ducttype)

        for fantype in ['kitchen', 'other']:
            configuration = location + '_' + fantype
            countattr = 'mev_fan_' + configuration + '_count'

            count = dwelling.get(countattr)
            if count:
                sfp = get_sfp(configuration)
                in_use_factor = mech_vent_in_use_factor(ventilation_type,
                                                        this_duct_type,
                                                        mv_approved)
                flowrate = 13 if fantype == 'kitchen' else 8
                sfp_sum += sfp * count * flowrate * in_use_factor
                total_flow += flowrate * count

    if total_flow > 0:
        adjusted_fan_sfp = sfp_sum / total_flow

    else:
        in_use_factor = mech_vent_default_in_use_factor()
        sfp = 0.8  # Table 4g
        adjusted_fan_sfp = sfp * in_use_factor

    return adjusted_fan_sfp


def mvhr_sfp(mv_ducttype, mv_approved, ventilation_type, mvhr_sfp=None):
    """
    Set the properties for the MVHR unit based on tables 4g and 4h

    :param dwelling:
    :param mv_ducttype:
    :param mv_approved:
    :param ventilation_type:
    :return:
    """
    if mvhr_sfp:
        in_use_factor = mech_vent_in_use_factor(ventilation_type,
                                                mv_ducttype,
                                                mv_approved)
    else:
        if mv_approved:
            raise SAPInputError("Cannot be mv_approved without mvhr_sfp being set")

        mvhr_sfp = 2  # Table 4g

        in_use_factor = mech_vent_default_in_use_factor()

    # FIXME: Don't think you actually need to set mvhr sfp if youget it from table 4g
    # dwelling.mvhr_sfp = mvhr_sfp
    return mvhr_sfp * in_use_factor


def mvhr_additional_properties(mv_ducttype, mv_approved, ventilation_type, mvhr_effy=None, mvhr_sfp=None):
    if mvhr_sfp:
        in_use_factor_hr = mech_vent_in_use_factor_hr(ventilation_type,
                                                      mv_ducttype,
                                                      mv_approved)
    else:
        mvhr_sfp = 2  # Table 4g
        mvhr_effy = 66  # Table 4g

        in_use_factor_hr = mech_vent_default_hr_effy_factor()

    return dict(mvhr_sfp=mvhr_sfp,
                mvhr_effy=mvhr_effy * in_use_factor_hr)


def set_mv_dwelling_properties(mv_ducttype, mv_approved, ventilation_type, mv_sfp=None):
    if mv_sfp:
        in_use_factor = mech_vent_in_use_factor(ventilation_type, mv_ducttype, mv_approved)
    else:
        mv_sfp = 2  # Table 4g
        in_use_factor = mech_vent_default_in_use_factor()

    return mv_sfp * in_use_factor


def piv_sfp(mv_ducttype, mv_approved, ventilation_type, piv_sfp=None):
    if piv_sfp:
        piv_sfp = piv_sfp
        in_use_factor = mech_vent_in_use_factor(ventilation_type, mv_ducttype, mv_approved)
    else:
        piv_sfp = 0.8  # Table 4g
        in_use_factor = mech_vent_default_in_use_factor()

    return piv_sfp * in_use_factor


def infiltration(wall_type=None, floor_type=None):
    out = {}
    if wall_type:
        out['structural_infiltration'] = 0.35 if wall_type == WallTypes.MASONRY else 0.25

    if floor_type:
        out['floor_infiltration'] = FLOOR_INFILTRATION[floor_type]
    return out


def ventilation(dwelling):
    """
    Ventilation part of the worksheet.

    This is run after the dwelling has been suitably configured

    Args:
        dwelling:

    Returns:

    """
    if dwelling.get('hlp') is not None:
        # Heat loss parameter already defined so don't need to
        # calculate the ventilation separately
        return {}

    if not dwelling.get('Nfansandpassivevents'):
        dwelling.Nfansandpassivevents = dwelling.Nintermittentfans + \
                                        dwelling.Npassivestacks

    inf_chimneys_ach = (dwelling.Nchimneys * 40 + dwelling.Nflues * 20 +
                        dwelling.Nfansandpassivevents * 10 + dwelling.Nfluelessgasfires * 40) / dwelling.volume

    if dwelling.get('pressurisation_test_result') is not None:
        base_infiltration_rate = dwelling.pressurisation_test_result / 20 + inf_chimneys_ach
    elif dwelling.get('pressurisation_test_result_average') is not None:
        base_infiltration_rate = (dwelling.pressurisation_test_result_average + 2) / 20. + inf_chimneys_ach
    else:
        additional_infiltration = (dwelling.Nstoreys - 1) * 0.1
        draught_infiltration = 0.05 if not dwelling.has_draught_lobby else 0
        window_infiltration = 0.25 - 0.2 * dwelling.draught_stripping

        base_infiltration_rate = (additional_infiltration
                                  + dwelling.structural_infiltration
                                  + dwelling.floor_infiltration
                                  + draught_infiltration
                                  + window_infiltration
                                  + inf_chimneys_ach)

    shelter_factor = 1 - 0.075 * dwelling.Nshelteredsides
    adjusted_infiltration_rate = shelter_factor * base_infiltration_rate

    effective_inf_rate = adjusted_infiltration_rate * dwelling.wind_speed / 4.

    if dwelling.ventilation_type == VentilationTypes.NATURAL:
        infiltration_ach = numpy.where(
            effective_inf_rate < 1.,
            0.5 + (effective_inf_rate ** 2) * 0.5,
            effective_inf_rate)

    elif dwelling.ventilation_type == VentilationTypes.MV:
        system_ach = 0.5
        infiltration_ach = effective_inf_rate + system_ach

    elif dwelling.ventilation_type in [VentilationTypes.MEV_CENTRALISED,
                                       VentilationTypes.MEV_DECENTRALISED,
                                       VentilationTypes.PIV_FROM_OUTSIDE]:
        system_ach = 0.5
        infiltration_ach = numpy.where(
            effective_inf_rate < 0.5 * system_ach,
            system_ach,
            effective_inf_rate + 0.5 * system_ach)
    elif dwelling.ventilation_type == VentilationTypes.MVHR:
        system_ach = 0.5
        infiltration_ach = (
            effective_inf_rate + system_ach * (1 - dwelling.mvhr_effy / 100)
        )
    else:
        # TODO: should this be allowed?
        infiltration_ach = None

    if dwelling.get('appendix_q_systems') is not None:
        for appendix_q_system in dwelling.appendix_q_systems:
            if 'ach_rates' in appendix_q_system:
                # TODO: Should really check that we don't get two sets of ach rates
                infiltration_ach = numpy.array(appendix_q_system['ach_rates'])

    return dict(
        base_infiltration_rate=base_infiltration_rate,
        infiltration_ach=infiltration_ach,
        inf_chimneys_ach=inf_chimneys_ach,
        infiltration_ach_annual=monthly_to_annual(infiltration_ach))
