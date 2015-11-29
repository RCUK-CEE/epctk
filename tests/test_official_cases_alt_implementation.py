import argparse
import logging
import os
import pickle
import sys

import output_checker
import yaml_io
from sap import pcdf
from sap import runner
from sap.io import input_conversion_rules
from sap.utils import SAPCalculationError, CALC_STAGE, ALL_PARAMS
from sap.dwelling import log_dwelling_params, log_dwelling, ParamTrackerDwelling
from tests import reference_case_parser
from tests.reference_cases_lists import OFFICIAL_CASES_THAT_WORK, SKIP

all_params = [set(), set(), set(), set(), set(), set(), set()]




def dump_param_list():
    for i in range(len(ALL_PARAMS)):
        for k in ALL_PARAMS[i]:
            print((i, k))

    print(("Dumped inputs: ", len(ALL_PARAMS[1])))


def log_all_params(d, prefix=""):
    param_set = ALL_PARAMS[CALC_STAGE]

    for k, v in list(d.items()):
        if k != "ordered_attrs":
            log_dwelling_params(param_set, prefix, k, v)


def create_sap_dwelling(inputs):
    dwelling = ParamTrackerDwelling()  # sap_worksheet.Dwelling()
    input_conversion_rules.process_inputs(dwelling, inputs)

    # if not sap_dwelling_validator.validate(d):
        #logging.error("Bad inputs")
        # exit(0)

    log_dwelling(dwelling.__dict__)

    dwelling.next_stage()
    return dwelling


def scan_file(fname, parser):
    f = open(fname, 'rU')
    txt = f.read()
    txt = txt.replace('\\\'b', '')
    txt = txt.replace('\\f1', '')
    txt = txt.replace('\\f2', '')
    res = []
    for srvrtokens, startloc, endloc in parser.scanString(txt):
        res.append(srvrtokens)
    return res


# -- not used
def run_all_dwellings(parser):
    for id in range(28):
        fname = "reference_dwellings/%d.rtf" % (id + 2,)
        res = scan_file(fname)

        print((id + 2, len(res)))  # ,res[0][0]


def parse_input_file(id):
    return parse_file("./reference_dwellings/%d.rtf" % id, reference_case_parser.whole_file)

# -- end not used


def parse_file(fname):
    parser = reference_case_parser.whole_file

    with open(fname, 'r') as rtf_file:
        txt = rtf_file.read()
        txt = txt.replace('\\\'b', '')
        txt = txt.replace('\\f1', '')
        txt = txt.replace('\\f2', '')

    return parser.parseString(txt)


SAP_REGIONS = {
    './reference_dwellings/2.rtf': 11,
    './reference_dwellings/3.rtf': 11,
    './reference_dwellings/4.rtf': 11,
    './reference_dwellings/5.rtf': 11,
    './reference_dwellings/6.rtf': 8,
    './reference_dwellings/7.rtf': 8,
    './reference_dwellings/8.rtf': 4,
    './reference_dwellings/9.rtf': 11,
    './reference_dwellings/10.rtf': 11,
}


def add_sap_region(dwelling, fname):
    # !!! Bit of a hack here because our tests case files don't includ
    # !!! sap region
    if fname in SAP_REGIONS:
        dwelling.sap_region = SAP_REGIONS[fname]
    elif not hasattr(dwelling, "sap_region"):
        dwelling.sap_region = 11

    return dwelling


def run_dwelling(dwelling):
    runner.run_sap(dwelling)
    runner.run_improvements(dwelling)
    runner.run_fee(dwelling)
    runner.run_der(dwelling)
    runner.run_ter(dwelling)


def get_dwelling(fname, force_reparse):
    """
    Get dwelling data, reparsing the raw input if no cache is found

    TODO: figure difference between dwelling and parsed output, at the moment
    have a bit of a hack by returning both together
    """
    basename = os.path.basename(fname)
    pickled_fname = os.path.join("pickled_reference_cases", basename + ".pkl")
    yaml_fname = os.path.join("yaml_test_cases", basename + ".yml")

    if os.path.exists(pickled_fname) and not force_reparse:
        dwelling_data = pickle.load(open(pickled_fname, "r"))

        if os.path.exists(yaml_fname):
            # YAML load directly produces a dwelling, not dwelling data!
            dwelling = yaml_io.from_yaml(yaml_fname)
        else:
            dwelling = create_sap_dwelling(dwelling_data.inputs)
            with open(yaml_fname, 'w') as yaml_file:
                yaml_io.to_yaml(dwelling, yaml_file)

    else:
        print(("Reparsing ", fname))

        dwelling_data = parse_file(fname)
        dwelling = create_sap_dwelling(dwelling_data.inputs)

        pickle.dump(dwelling_data, open(pickled_fname, "w"))

        with open(yaml_fname, 'w') as yaml_file:
            yaml_io.to_yaml(dwelling, yaml_file)

    # ! Append the SAP region for the cases where it doesn't exist
    add_sap_region(dwelling, fname)

    return dwelling_data, dwelling


def run_case(fname, force_reparse):
    print(("RUNNING %s" % fname))

    try:
        dwelling_data, dwelling = get_dwelling(fname, force_reparse)

        #dwelling = create_sap_dwelling(dwelling_data.inputs)

        run_dwelling(dwelling)

        output_checker.check_results(dwelling, dwelling_data)

    except SAPCalculationError:
        if output_checker.is_err_calc(dwelling_data):
            return
        else:
            raise

    logging.info("DONE")


def run_official_cases(cases, maxruns=None, reparse=False):
    count = 0
    for f in cases:
        if f in SKIP:
            continue

        fname = os.path.join('official_reference_cases', f)
        run_case(fname, reparse)
        count += 1
        if maxruns is not None and count >= int(maxruns):
            break

    print(("Ran: ", count))


class SingleLevelFilter(logging.Filter):

    def __init__(self, passlevel, reject):
        self.passlevel = passlevel
        self.reject = reject

    def filter(self, record):
        if self.reject:
            return record.levelno != self.passlevel
        else:
            return record.levelno == self.passlevel




if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the SAP code against tests files')

    parser.add_argument("--maxruns", default=None)
    parser.add_argument("--reparse",
                        action="store_true",
                        default=False)

    parser.add_argument("--silent",
                        action="store_true",
                        default=False)
    parser.add_argument("--show_case",
                        action="store_true",
                        default=False)

    options = parser.parse_args()

    if options.show_case:
        # Shows info and errors
        h1 = logging.StreamHandler(sys.stdout)
        h1.addFilter(SingleLevelFilter(logging.WARNING, True))
        logger = logging.getLogger()
        logger.addHandler(h1)
        logger.setLevel(logging.INFO)
    elif options.silent:
        logging.basicConfig(level=logging.ERROR)
    else:
        logging.basicConfig(level=logging.INFO)

    pcdf.DATA_FILE = "./official_reference_cases/pcdf2009_test_322.dat"

    run_official_cases(
        OFFICIAL_CASES_THAT_WORK, maxruns=options.maxruns, reparse=options.reparse)
