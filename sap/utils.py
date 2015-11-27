import csv


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


def true_and_not_missing(d, attr):
    return hasattr(d, attr) and getattr(d, attr)