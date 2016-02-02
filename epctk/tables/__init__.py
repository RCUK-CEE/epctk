"""
Hide the implementation details of the tables inside this package

Import the relevant functions as needed by other parts of saptk.
When you add, modify, or remove functions from the tables modules,
you must make the corresponding change in this file.

Aim to reduce the API surface of tables over time by encapsulating
functionality inside it, and reducing the number of imports into this
file.

"""
import os.path

from .tables_ import (TABLE_3, TABLE_6D, TABLE_10, TABLE_10C, TABLE_D7,TABLE_M1,
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
                         )
from .tables_appendix_h import TABLE_H1, TABLE_H2, TABLE_H3, TABLE_H4, TABLE_H5
from .tables_appendix_n import table_n4_heating_days, table_n8_secondary_fraction, interpolate_psr_table, interpolate_efficiency

from .tables_part_four import (TABLE_4A, TABLE_4B, get_4a_system, TABLE_4D, TABLE_4E,
                               get_4a_system, table_4f_fans_pumps_keep_hot, apply_table_4e,
                               mech_vent_default_in_use_factor, mech_vent_default_hr_effy_factor,
                               mech_vent_in_use_factor, mech_vent_in_use_factor_hr)

_DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')
