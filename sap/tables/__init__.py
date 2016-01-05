"""
Hide the implementation details of the tables inside this package

Import the relevant functions as needed by other parts of saptk

Aim to reduce the API surface of tables over time by encapsulating functionality inside it.
"""
import os.path

from .sap_tables import (TABLE_3, TABLE_6D, TABLE_10, TABLE_10C, TABLE_D7,
                         TABLE_H1, TABLE_H2, TABLE_H3, TABLE_H4, TABLE_H5, TABLE_M1,
                         FLOOR_INFILTRATION, MONTHLY_HOT_WATER_FACTORS, MONTHLY_HOT_WATER_TEMPERATURE_RISE,
                         table_1b_occupancy, table_1b_daily_hot_water,
                         table_2_hot_water_store_loss_factor, table_2a_hot_water_vol_factor,
                         table_2b_hot_water_temp_factor,
                         table_5a_fans_and_pumps_gain,
                         combi_loss_table_3a, combi_loss_instant_without_keep_hot,
                         combi_loss_table_3b, combi_loss_table_3c,
                         combi_loss_instant_with_timed_heat_hot,
                         combi_loss_instant_with_untimed_heat_hot, get_seasonal_effy_offset,
                         system_efficiency, system_type_from_sap_code,
                         interpolate_efficiency, interpolate_psr_table,
                         table_n8_secondary_fraction, table_n4_heating_days)

from .part_four_tables import (TABLE_4A, TABLE_4B, get_4a_system, TABLE_4D, TABLE_4E,
                               get_4a_system, table_4f_fans_pumps_keep_hot, apply_table_4e)

_DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')
