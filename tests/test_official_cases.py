import logging

import os
import pickle
import sys

from tests import test_case_parser
import input_conversion_rules
import output_checker
import yaml_io
from sap import runner
from utils import *


all_params = [set(), set(), set(), set(), set(), set(), set()]


def log_all_params(d, prefix=""):
    #FIXME dodgy use of global Calc_stage
    param_set = all_params[calc_stage]

    for k, v in list(d.items()):
        if k != "ordered_attrs":
            log_obj(param_set, prefix, k, v)


def create_sap_dwelling(inputs):
    d = ParamTrackerDwelling()  # sap_worksheet.Dwelling()
    input_conversion_rules.process_inputs(d, inputs)

    # if not sap_dwelling_validator.validate(d):
        #logging.error("Bad inputs")
        # exit(0)

    log_all_params(d.__dict__)

    d.nextStage()
    return d


def test_run_all(parser):
    for id in range(28):
        fname = "test_dwellings/%d.rtf" % (id + 2,)
        f = open(fname, 'r')
        txt = f.read()
        txt = txt.replace('\\\'b', '')
        res = []
        for srvrtokens, startloc, endloc in parser.scanString(txt):
            res.append(srvrtokens)

        print((id + 2, len(res)))  # ,res[0][0]


def parse_file(fname, parser):
    f = open(fname, 'r')
    txt = f.read()
    txt = txt.replace('\\\'b', '')
    txt = txt.replace('\\f1', '')
    txt = txt.replace('\\f2', '')
    return parser.parseString(txt)


def scan_file(fname, parser):
    f = open(fname, 'r')
    txt = f.read()
    txt = txt.replace('\\\'b', '')
    txt = txt.replace('\\f2', '')
    res = []
    for srvrtokens, startloc, endloc in parser.scanString(txt):
        res.append(srvrtokens)
    return res


def parse_input_file(test_case_id):
    return parse_file("./test_dwellings/%d.rtf" % (test_case_id,), test_case_parser.whole_file)


def load_or_parse_file(fname, parser, force_reparse):
    basename = os.path.basename(fname) + ".pkl"
    pickled_file = os.path.join("./pickled_test_cases", basename)
    if os.path.exists(pickled_file) and not force_reparse:
        res = pickle.load(open(pickled_file, "r"))
    else:
        print(("Reparsing ", fname))
        res = parse_file(fname, parser)
        pickle.dump(res, open(pickled_file, "w"))

    return res

SAP_REGIONS = {
    './test_dwellings/2.rtf': 11,
    './test_dwellings/3.rtf': 11,
    './test_dwellings/4.rtf': 11,
    './test_dwellings/5.rtf': 11,
    './test_dwellings/6.rtf': 8,
    './test_dwellings/7.rtf': 8,
    './test_dwellings/8.rtf': 4,
    './test_dwellings/9.rtf': 11,
    './test_dwellings/10.rtf': 11,
}


def run_dwelling(fname, d):
    # !!! Bit of a hack here because our tests case files don't include
    # !!! sap region
    if fname in SAP_REGIONS:
        d.sap_region = SAP_REGIONS[fname]
    elif not hasattr(d, "sap_region"):
        d.sap_region = 11

    runner.run_sap(d)
    runner.run_improvements(d)
    runner.run_fee(d)
    runner.run_der(d)
    runner.run_ter(d)


def run_case(fname, reparse):
    logging.info("RUNNING %s" % (fname,))

    try:
        res = load_or_parse_file(fname, test_case_parser.whole_file, reparse)
        d = create_sap_dwelling(res.inputs)

        yaml_file = "yaml_test_cases/" + os.path.basename(fname) + ".yml"
        if os.path.exists(yaml_file) and not reparse:
            d = yaml_io.from_yaml(yaml_file)
        else:
            with open(yaml_file, 'w') as f:
                yaml_io.to_yaml(d, f)

        run_dwelling(fname, d)
        output_checker.check_results(d, res)
    except tables.SAPCalculationError:
        if output_checker.is_err_calc(res):
            return
        else:
            raise
    logging.info("DONE")


def run_sample_cases(force_reparse):
    for i in range(29):
        # What about 1?
        id = i + 2
        # if id<11: continue
        if id == 16:
            continue  # Community heating

        # Don't know what to do
        # if id==15: continue # Adjustments in table 4c2 also apply to solid
        # fuel boilers?
        if id == 20:
            continue  # two systems and sedbuk - uses made up
                            # PCDF boiler and custom secondary system
                            # type (625), also for some reason a 5%
                            # effy penalty is applied to PCDF boiler
                            # and 2 oil pumps are counted
        # if id==28: continue # secondary system assumed for some reason
        if id == 30:
            # two main systems, one reassigned as secondary.  Why?  FSAP
            # doesn't do the reassignment
            continue

        # Cases 8 & 9 - cooling.  Looks like you don't include heat
        # gain from central heating pumps in the summer cooling demand
        # calc?

        run_case("./test_dwellings/%d.rtf" % (id,), force_reparse)


def dump_param_list():
    for i in range(len(all_params)):
        for k in all_params[i]:
            print((i, k))

    print(("Dumped inputs: ", len(all_params[1])))


def run_official_cases(cases, maxruns=None, reparse=False):
    count = 0
    for f in cases:
        if f in official_test_cases.SKIP:
            continue

        fname = './official_test_cases/' + f
        # print "RUNNING: ",fname
        run_case(fname, reparse)
        count += 1
        if maxruns != None and count == maxruns:
            break

    print(("Ran: ", count))


class SingleLevelFilter(logging.Filter):

    def __init__(self, passlevel, reject):
        self.passlevel = passlevel
        self.reject = reject

    def filter(self, record):
        if self.reject:
            return (record.levelno != self.passlevel)
        else:
            return (record.levelno == self.passlevel)


import official_test_cases
from sap import pcdf
from optparse import OptionParser

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("--reparse",
                      action="store_true",
                      dest="reparse",
                      default=False)
    parser.add_option("--show_warnings",
                      action="store_true",
                      dest="show_warnings",
                      default=False)
    parser.add_option("--show_case",
                      action="store_true",
                      dest="show_case",
                      default=False)

    (options, args) = parser.parse_args()

    if options.show_warnings:
        logging.basicConfig(level=logging.INFO)
    elif options.show_case:
        # Shows info and errors
        h1 = logging.StreamHandler(sys.stdout)
        h1.addFilter(SingleLevelFilter(logging.WARNING, True))
        logger = logging.getLogger()
        logger.addHandler(h1)
        logger.setLevel(logging.INFO)
    else:
        logging.basicConfig(level=logging.ERROR)

    """
    h1 = logging.StreamHandler(sys.stdout) 
    h1.addFilter(SingleLevelFilter(logging.WARNING,True))
    logger=logging.getLogger()
    logger.addHandler(h1)
    logger.setLevel(logging.INFO)
    """

    pcdf.DATA_FILE = "./official_test_cases/pcdf2009_test_322.dat"

    run_official_cases(
        official_test_cases.OFFICIAL_CASES_THAT_WORK, reparse=options.reparse)


    #pv_cases = [11, 14, 15, ]
    #wind_cases = [18, 6, 9]
    #hydro_cases = [10, ]
    # for case in pv_cases:
    #    run_case("./test_dwellings/%d.rtf" % (case,))
    # run_case(11)

    # run_case("./test_dwellings/19.rtf",False)
    #run_case("./official_test_cases/EW-2s-semi - Electricaire - water by Range with solar panel.rtf")
    # exit(0)

    # run_official_cases([
    #        "EW-1a-detached.rtf", ],options.reparse)

    # run_sample_cases(options.reparse)

    # dump_param_list()
