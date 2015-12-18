"""
Appendix M: Energy from Photovoltaic (PV) technology, small and micro wind turbines
and small- scale hydro-electric generators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
from sap.sap_tables import TABLE_H4, TABLE_H2, m1_correction_factor


def configure_pv_system(pv_system):
    pv_system['overshading_factor'] = TABLE_H4[pv_system['overshading_category']]

    if str(pv_system['pitch']).lower() != "Horizontal".lower():
        pv_system['Igh'] = TABLE_H2[pv_system['pitch']][pv_system['orientation']]
    else:
        pv_system['Igh'] = TABLE_H2[pv_system['pitch']]


def configure_pv(dwelling):
    if dwelling.get('photovoltaic_systems'):
        for pv_system in dwelling.photovoltaic_systems:
            configure_pv_system(pv_system)


def configure_wind_turbines(dwelling):
    if dwelling.get('N_wind_turbines'):
        dwelling.wind_turbine_speed_correction_factor = m1_correction_factor(
                dwelling.terrain_type,
                dwelling.wind_turbine_hub_height)