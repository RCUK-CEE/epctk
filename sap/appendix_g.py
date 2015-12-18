"""
Appendix G: Flue gas heat recovery systems and Waste water heat recovery systems
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
from .appendix_m import configure_pv_system
from .pcdf import get_wwhr_system, get_fghr_system
from .sap_tables import TABLE_H3, combi_loss_table_3a, combi_loss_table_3b, combi_loss_table_3c
from .sap_types import HeatingTypes
from .utils import exists_and_true


def configure_wwhr(dwelling):
    """
    Configure the waste water heat recovery systems (WWHR) for this dwelling

    :param dwelling:
    :return:
    """
    if dwelling.get('wwhr_systems') and not dwelling.wwhr_systems is None:
        for sys in dwelling.wwhr_systems:
            sys['pcdf_sys'] = get_wwhr_system(sys['pcdf_id'])


def configure_fghr(dwelling):
    """
    Configure Flue Gas Heat Recovery (FGHR) for this dwelling

    :param dwelling:
    :return:
    """
    # TODO: Should check that fghr is allowed for this system

    if dwelling.get('fghrs') is not None:
        # !!! Need to add electrical power G1.4
        # !!! Entire fghrs calc is unfinished really
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
            if hasattr(dwelling.water_sys, 'pcdf_data'):
                configure_combi_loss(dwelling,
                                     dwelling.water_sys,
                                     dwelling.water_sys.pcdf_data)
            else:
                dwelling.water_sys.combi_loss = combi_loss_table_3a(
                        dwelling, dwelling.water_sys)

            if dwelling.fghrs["has_pv_module"]:
                assert "PV_kWp" in dwelling.fghrs
                configure_pv_system(dwelling.fghrs)
                dwelling.fghrs['monthly_solar_hw_factors'] = TABLE_H3[dwelling.fghrs['pitch']]
        else:
            assert not "PV_kWp" in dwelling.fghrs

        if (dwelling.water_sys.system_type in [HeatingTypes.combi,
                                               HeatingTypes.storage_combi]
            and exists_and_true(dwelling.water_sys, 'has_no_keep_hot')
            and not dwelling.has_hw_cylinder):
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