import csv

from sap.sap_constants import DAYS_PER_MONTH

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


def sum_it(x):
    try:
        return sum(x)
    except TypeError:
        return x