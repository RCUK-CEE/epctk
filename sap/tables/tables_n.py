import numpy

from sap.tables.sap_tables import TABLE_N4, TABLE_N8
from sap.utils import SAPCalculationError


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