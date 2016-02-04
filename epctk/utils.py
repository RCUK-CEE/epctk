import csv

import numpy

from .constants import DAYS_PER_MONTH


def float_or_none(val):
    return float(val) if val.strip() != "" else None


def int_or_none(val):
    return int(val) if val.strip() != "" else None


def float_or_zero(s):
    return float(s) if s != '' else 0


class SAPCalculationError(RuntimeError):
    pass


class SAPInputError(RuntimeError):
    pass


def csv_to_dict(filename, translator):
    results = {}
    with open(filename, 'r') as infile:
        reader = csv.reader(infile)
        for row in reader:
            if row[0][0] == '#':
                continue
            translator(results, row)
    return results


def monthly_to_annual(var):
    return sum(var * DAYS_PER_MONTH) / 365.


def sum_(x):
    try:
        return sum(x)
    except TypeError:
        return x


def weighted_effy(q_space, q_water, wintereff, summereff):
    """
    Calculate monthly efficiencies given the space and water heating requirements
    and the winter and summer efficiencies

    Args:
        q_space: space heating demand
        q_water: water heating demand
        wintereff: winter efficiency
        summereff: summer efficiency

    Returns:
         array with 12 monthly efficiences
    """
    # If there is no space or water demand then divisor will be zero
    water_effy = numpy.zeros(12)
    divisor = q_space / wintereff + q_water / summereff
    for i in range(12):
        if divisor[i] != 0:
            water_effy[i] = (q_space[i] + q_water[i]) / divisor[i]
        else:
            water_effy[i] = 100
    return water_effy


def sum_summer(l):
    return sum(l[5:9])


def sum_winter(l):
    return sum(l[0:5]) + sum(l[9:])