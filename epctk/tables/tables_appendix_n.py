"""
Tables in N section take up enough space to
 warrant their own file
"""
import numpy

from ..utils import SAPCalculationError


def interpolate_psr_table(psr, table,
                          key=lambda x: x[0],
                          data=numpy.array):
    if psr >= key(table[-1]):
        return data(table[-1])

    elif psr < key(table[0]):
        return data(table[0])

    # TODO: Interpolation will fail if psr is off bottom of range. Explicitly throw error?
    psr_data_below = max((p for p in table if key(p) < psr),
                         key=key)

    psr_data_above = min((p for p in table if key(p) > psr),
                         key=key)

    frac = (psr - key(psr_data_below)) / (key(psr_data_above) - key(psr_data_below))
    return (1 - frac) * data(psr_data_below) + frac * data(psr_data_above)


def interpolate_efficiency(psr, psr_dataset):
    if psr > psr_dataset[-1]['psr']:
        raise SAPCalculationError("PSR too large for this system")
    if psr < psr_dataset[0]['psr']:
        raise SAPCalculationError("PSR too small for this system")

    return 1 / interpolate_psr_table(psr, psr_dataset,
                                     key=lambda x: x['psr'],
                                     data=lambda x: 1 / x['space_effy'])


def table_n4_heating_days(psr):
    data = interpolate_psr_table(psr, TABLE_N4)
    N24_16 = int(0.5 + data[1])
    N24_9 = int(0.5 + data[2])
    N16_9 = int(0.5 + data[3])
    return N24_16, N24_9, N16_9


def table_n8_secondary_fraction(psr, heating_duration):
    data = interpolate_psr_table(psr, TABLE_N8)
    if heating_duration == "24":
        table_col = 1
    elif heating_duration == "16":
        table_col = 2
    elif heating_duration == "11":
        table_col = 3
    else:
        assert heating_duration == "V"
        table_col = 4

    interpolated = data[table_col]
    return int(interpolated * 1000 + .5) / 1000.


TABLE_N4 = [
    (0.2, 57, 143, 8),  # PSR;N24.16;N24,9;N16,9;
    (0.25, 54, 135, 2),
    (0.3, 51, 127, 10),
    (0.35, 40, 99, 20),
    (0.4, 35, 88, 29),
    (0.45, 31, 77, 40),
    (0.5, 26, 65, 31),
    (0.55, 21, 54, 41),
    (0.6, 17, 43, 30),
    (0.65, 8, 20, 51),
    (0.7, 6, 15, 36),
    (0.75, 4, 10, 40),
    (0.8, 3, 6, 24),
    (0.85, 2, 4, 27),
    (0.9, 0, 1, 15),
    (0.95, 0, 0, 15),
    (1, 0, 0, 14),
    (1.05, 0, 0, 7),
    (1.1, 0, 0, 6),
    (1.15, 0, 0, 3),
    (1.2, 0, 0, 2),
    (1.25, 0, 0, 1),
    (1.3, 0, 0, 0),
]
TABLE_N8 = [
    # psr;24 hr heating secondary fraction; 16 hr; 11hr; variable
    (0.2, 0.4, 0.53, 0.64, 0.41),
    (0.25, 0.28, 0.43, 0.57, 0.3),
    (0.3, 0.19, 0.34, 0.49, 0.2),
    (0.35, 0.12, 0.27, 0.42, 0.13),
    (0.4, 0.06, 0.2, 0.35, 0.07),
    (0.45, 0.03, 0.14, 0.29, 0.03),
    (0.5, 0.01, 0.09, 0.24, 0.01),
    (0.55, 0, 0.06, 0.19, 0),
    (0.6, 0, 0.03, 0.15, 0),
    (0.65, 0, 0.02, 0.11, 0),
    (0.7, 0, 0.01, 0.09, 0),
    (0.75, 0, 0, 0.05, 0),
    (0.8, 0, 0, 0.05, 0),
    (0.85, 0, 0, 0.03, 0),
    (0.9, 0, 0, 0.02, 0),
    (0.95, 0, 0, 0.01, 0),
    (1, 0, 0, 0.01, 0),
    (1.05, 0, 0, 0, 0),
]