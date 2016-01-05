import csv

import numpy

from .constants import DAYS_PER_MONTH

CALC_STAGE = 0
ALL_PARAMS = [set(), set(), set(), set(), set(), set(), set()]



def float_or_none(val):
    return float(val) if val.strip() != "" else None


def int_or_none(val):
    return int(val) if val.strip() != "" else None


def float_or_zero(s):
    return float(s) if s != '' else 0


class SAPCalculationError(RuntimeError):
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


def exists_and_true(d, attr):
    return hasattr(d, attr) and getattr(d, attr)

# class TrackedDict(dict):
#     def __init__(self, data, prefix):
#         super(TrackedDict, self).__init__(data)
#         self.prefix = prefix + "."
#
#         for key in list(data.keys()):
#             ALL_PARAMS[CALC_STAGE].add(self.prefix + key)
#
#     def __setitem__(self, key, value):
#         dict.__setitem__(self, key, value)
#         ALL_PARAMS[CALC_STAGE].add(self.prefix + key)
#

def monthly_to_annual(var):
    return sum(var * DAYS_PER_MONTH) / 365.


def sum_(x):
    try:
        return sum(x)
    except TypeError:
        return x


def weighted_effy(Q_space, Q_water, wintereff, summereff):
    """
    Calculate monthly efficiencies given the space and water heating requirements
    and the winter and summer efficiencies

    :param Q_space: space heating demand
    :param Q_water: water heating demand
    :param wintereff: winter efficiency
    :param summereff: summer efficiency
    :return: array with 12 monthly efficiences
    """
    # If there is no space or water demand then divisor will be zero
    water_effy = numpy.zeros(12)
    divisor = Q_space / wintereff + Q_water / summereff
    for i in range(12):
        if divisor[i] != 0:
            water_effy[i] = (Q_space[i] + Q_water[i]) / divisor[i]
        else:
            water_effy[i] = 100
    return water_effy