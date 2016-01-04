from .pcdf import mech_vent_in_use_factor, mech_vent_in_use_factor_hr, get_mev_system
from .sap_tables import mech_vent_default_in_use_factor, mech_vent_default_hr_effy_factor
from .sap_types import VentilationTypes, DuctTypes


# TODO: change these to output the relevant data so we don't have to pass in dwelling
# -- Probably want to return a dict and use dict-style dwelling.update


def set_mev_centralised_properties(dwelling, mv_ducttype, mv_approved, ventilation_type):
    if dwelling.get('mev_sfp'):
        sfp = dwelling.mev_sfp
        in_use_factor = mech_vent_in_use_factor(ventilation_type, mv_ducttype, mv_approved)
    else:
        sfp = 0.8  # Table 4g
        in_use_factor = mech_vent_default_in_use_factor()

    dwelling.adjusted_fan_sfp = sfp * in_use_factor
    if mv_approved:
        assert False


def set_mev_decentralised_properties(dwelling, mv_ducttype, mv_approved, ventilation_type):
    if dwelling.get('mev_sys_pcdf_id'):
        sys = get_mev_system(dwelling.mev_sys_pcdf_id)
        get_sfp = lambda configuration: sys['configs'][configuration]['sfp']
    else:
        get_sfp = lambda configuration: dwelling["mev_fan_" + configuration + "_sfp"]

    total_flow = 0
    sfp_sum = 0

    for location in ['room', 'duct', 'wall']:
        this_duct_type = (DuctTypes.NONE if location == 'wall' else mv_ducttype)

        for fantype in ['kitchen', 'other']:
            configuration = location + '_' + fantype
            countattr = 'mev_fan_' + configuration + '_count'
            if dwelling.get(countattr):
                count = getattr(dwelling, countattr)
                sfp = get_sfp(configuration)
                in_use_factor = mech_vent_in_use_factor(ventilation_type,
                                                        this_duct_type,
                                                        mv_approved)
                flowrate = 13 if fantype == 'kitchen' else 8
                sfp_sum += sfp * count * flowrate * in_use_factor
                total_flow += flowrate * count

    if total_flow > 0:
        dwelling.adjusted_fan_sfp = sfp_sum / total_flow

    else:
        in_use_factor = mech_vent_default_in_use_factor()
        sfp = 0.8  # Table 4g
        dwelling.adjusted_fan_sfp = sfp * in_use_factor


def set_mvhr_dwelling_properties(dwelling, mv_ducttype, mv_approved, ventilation_type):
    """
    Set the properties for the MVHR unit based on tables 4g and 4h

    :param dwelling:
    :param mv_ducttype:
    :param mv_approved:
    :param ventilation_type:
    :return:
    """
    if dwelling.get('mvhr_sfp'):
        in_use_factor = mech_vent_in_use_factor(ventilation_type,
                                                mv_ducttype,
                                                mv_approved)

        in_use_factor_hr = mech_vent_in_use_factor_hr(ventilation_type,
                                                      mv_ducttype,
                                                      mv_approved)
    else:
        dwelling.mvhr_sfp = 2  # Table 4g
        dwelling.mvhr_effy = 66  # Table 4g

        in_use_factor = mech_vent_default_in_use_factor()
        in_use_factor_hr = mech_vent_default_hr_effy_factor()

        if mv_approved:
            assert False

    dwelling.adjusted_fan_sfp = dwelling.mvhr_sfp * in_use_factor
    dwelling.mvhr_effy = dwelling.mvhr_effy * in_use_factor_hr


def set_mv_dwelling_properties(dwelling, mv_ducttype, mv_approved, ventilation_type):
    if dwelling.get('mv_sfp'):
        mv_sfp = dwelling.mv_sfp
        in_use_factor = mech_vent_in_use_factor(dwelling.ventilation_type, mv_ducttype,
                                                mv_approved)
    else:
        mv_sfp = 2  # Table 4g
        in_use_factor = mech_vent_default_in_use_factor()
    dwelling.adjusted_fan_sfp = mv_sfp * in_use_factor


def set_piv_dwelling_properties(dwelling, mv_ducttype, mv_approved, ventilation_type):

    if dwelling.get('piv_sfp'):
            piv_sfp = dwelling.piv_sfp
            in_use_factor = mech_vent_in_use_factor(dwelling.ventilation_type, mv_ducttype,
                                                    mv_approved)
    else:
        piv_sfp = 0.8  # Table 4g
        in_use_factor = mech_vent_default_in_use_factor()
    dwelling.adjusted_fan_sfp = piv_sfp * in_use_factor


def configure_ventilation(dwelling):

    ventilation_type = dwelling.ventilation_type
    mv_approved = dwelling.get('mv_approved', False)

    # Assume NONE duct type if there is none set for this dwelling.
    mv_ducttype = dwelling.get('mv_ducttype', DuctTypes.NONE)

    if ventilation_type == VentilationTypes.MEV_CENTRALISED:
        set_mev_centralised_properties(dwelling, mv_ducttype, mv_approved, ventilation_type)

    elif ventilation_type == VentilationTypes.MEV_DECENTRALISED:
        set_mev_decentralised_properties(dwelling, mv_ducttype, mv_approved, ventilation_type)

    elif ventilation_type == VentilationTypes.MVHR:
        set_mvhr_dwelling_properties(dwelling, mv_ducttype, mv_approved, ventilation_type)

    elif ventilation_type == VentilationTypes.MV:
        set_mv_dwelling_properties(dwelling, mv_ducttype, mv_approved, ventilation_type)

    elif ventilation_type == VentilationTypes.PIV_FROM_OUTSIDE:
        set_piv_dwelling_properties(dwelling, mv_ducttype, mv_approved, ventilation_type)