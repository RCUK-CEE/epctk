"""
Solar Hot Water
~~~~~~~~~~~~~~~

"""
from ..tables import TABLE_H1, TABLE_H2, TABLE_H3, TABLE_H4


def configure_solar_hw(dwelling):
    if dwelling.get('solar_collector_aperture') is not None:
        dwelling.collector_overshading_factor = TABLE_H4[dwelling.collector_overshading]

        if str(dwelling.collector_pitch).lower() != "Horizontal".lower():
            dwelling.collector_Igh = TABLE_H2[dwelling.collector_pitch][dwelling.collector_orientation]

        else:
            dwelling.collector_Igh = TABLE_H2[dwelling.collector_pitch]

        dwelling.monthly_solar_hw_factors = TABLE_H3[dwelling.collector_pitch]

        if dwelling.solar_storage_combined_cylinder:
            dwelling.solar_effective_storage_volume = dwelling.solar_dedicated_storage_volume + 0.3 * (
                dwelling.hw_cylinder_volume - dwelling.solar_dedicated_storage_volume)
        else:
            dwelling.solar_effective_storage_volume = dwelling.solar_dedicated_storage_volume

        if not dwelling.get('collector_zero_loss_effy'):
            default_params = TABLE_H1[dwelling.collector_type]
            dwelling.collector_zero_loss_effy = default_params[0]
            dwelling.collector_heat_loss_coeff = default_params[1]