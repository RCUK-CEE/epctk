import logging
import os
import pickle
import sys
import unittest

from epctk import runner
from epctk.dwelling import Dwelling
from epctk.io import input_conversion_rules, yaml_io
from epctk.utils import SAPCalculationError
import epctk.appendix.appendix_t

from tests import output_checker
from tests import reference_case_parser
from tests.reference_cases_lists import OFFICIAL_CASES, SKIP

_FOLDER = os.path.join(os.path.dirname(__file__), '..', '..', 'data_private', 'bre_test_cases')

SAP_REGIONS = {
    '2.rtf': 11,
    '3.rtf': 11,
    '4.rtf': 11,
    '5.rtf': 11,
    '6.rtf': 8,
    '7.rtf': 8,
    '8.rtf': 4,
    '9.rtf': 11,
    '10.rtf': 11,
}


class SingleLevelFilter(logging.Filter):
    def __init__(self, passlevel, reject):
        super().__init__()
        self.passlevel = passlevel
        self.reject = reject

    def filter(self, record):
        if self.reject:
            return record.levelno != self.passlevel
        else:
            return record.levelno == self.passlevel


def create_sap_dwelling(inputs):
    """
    Create a SAP dwelling object from parsed SAP input file
    :param inputs:
    :return:
    """
    dwelling = Dwelling()
    input_conversion_rules.process_inputs(dwelling, inputs)

    # if not sap_dwelling_validator.validate(dwelling):
    # logging.error("Bad inputs")
    # exit(0)

    return dwelling


def parse_file(fname, parser):
    with open(fname, 'r') as f:
        txt = f.read()
        txt = txt.replace('\\\'b', '')
        txt = txt.replace('\\f1', '')
        txt = txt.replace('\\f2', '')
        return parser.parseString(txt)


def parse_input_file(test_case_id):
    return parse_file(os.path.join("reference_dwellings", "%d.rtf" % (test_case_id,)),
                      reference_case_parser.whole_file)


def load_reference_case(case_path, parser, force_reparse):
    """
    Load the given file with the given parser. First attempts to
    load the cached parsed file (pickled), if that does not exist
    or if force_reparse is true, will reparse the original file

    :param case_path:
    :param parser:
    :param force_reparse:
    :return:
    """
    pickled_file = os.path.join(_FOLDER, 'pickled_reference_cases', os.path.basename(case_path) + ".pkl")

    if os.path.exists(pickled_file) and not force_reparse:
        case = pickle.load(open(pickled_file, "rb"))
    else:
        print("Reparsing ", case_path)
        case = parse_file(case_path, parser)
        pickle.dump(case, open(pickled_file, "w"))

    return case


def run_dwelling(fname, dwelling):
    """
    Run dwelling that was loaded from fname

    :param fname: file name needed to lookup SAP region
    :param dwelling: dwelling definition loaded from file
    :return:
    """

    # FIXME !!! Bit of a hack here because our tests case files don't include sap region
    if fname in SAP_REGIONS:
        dwelling['sap_region'] = SAP_REGIONS[os.path.basename(fname)]
    elif not dwelling.get("sap_region"):
        dwelling['sap_region'] = 11

    runner.run_sap(dwelling)
    runner.run_fee(dwelling)
    runner.run_der(dwelling)
    epctk.appendix.appendix_t.run_ter(dwelling)

    # FIXME: ongoing problems in applying Appendix T improvements
    # sap.appendix.appendix_t.run_improvements(dwelling)


def run_sap_only(fname, dwelling):
    """
    Run dwelling that was loaded from fname

    :param fname: file name needed to lookup SAP region
    :param dwelling: dwelling definition loaded from file
    :return:
    """

    # FIXME !!! Bit of a hack here because our tests case files don't include sap region
    if fname in SAP_REGIONS:
        dwelling['sap_region'] = SAP_REGIONS[os.path.basename(fname)]
    elif not dwelling.get("sap_region"):
        dwelling['sap_region'] = 11

    runner.run_sap(dwelling)


def run_case(fname, reparse):
    logging.warning("RUNNING %s" % (fname,))

    try:
        yaml_file = os.path.join(_FOLDER, "yaml_test_cases", os.path.basename(fname) + ".yml")
        if os.path.exists(yaml_file) and not reparse:
            dwelling = yaml_io.from_yaml(yaml_file)
        else:
            parsed_ref_case = load_reference_case(fname, reference_case_parser.whole_file, reparse)
            dwelling = create_sap_dwelling(parsed_ref_case.inputs)
            with open(yaml_file, 'w') as f:
                yaml_io.to_yaml(dwelling, f)
            output_checker.check_results(dwelling, parsed_ref_case)
        run_dwelling(fname, dwelling)

    except SAPCalculationError:
        # if output_checker.is_err_calc(parsed_ref_case):
        #     return
        # else:
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

        run_case(os.path.join("reference_dwellings", "%d.rtf" % id), force_reparse)


def run_official_cases(cases, maxruns=None, reparse=False):
    count = 0
    for filename in cases:
        if filename in SKIP:
            continue

        fname = os.path.join(_FOLDER, 'official_reference_cases', filename)
        # print "RUNNING: ",fname
        run_case(fname, reparse)
        count += 1
        if maxruns != None and count == maxruns:
            break

    print(("Ran: ", count))


class TestOfficialCases(unittest.TestCase):
    def test_run_all_known_working_noparse(self):
        run_official_cases(
            OFFICIAL_CASES, reparse=False)
    #
    # def test_run_all_known_working_parse(self):
    #     run_official_cases(
    #         OFFICIAL_CASES_THAT_WORK, reparse=True)


if __name__ == '__main__':
    from optparse import OptionParser

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

    # h1 = logging.StreamHandler(sys.stdout)
    # h1.addFilter(SingleLevelFilter(logging.WARNING,True))
    # logger=logging.getLogger()
    # logger.addHandler(h1)
    # logger.setLevel(logging.INFO)


    run_official_cases(
        OFFICIAL_CASES, reparse=options.reparse)


    # pv_cases = [11, 14, 15, ]
    # wind_cases = [18, 6, 9]
    # hydro_cases = [10, ]
    # for case in pv_cases:
    #    run_case("./reference_dwellings/%d.rtf" % (case,))
    # run_case(11)

    # run_case("./reference_dwellings/19.rtf",False)
    # run_case("./official_reference_cases/EW-2s-semi - Electricaire - water by Range with solar panel.rtf")
    # exit(0)

    # run_official_cases([
    #        "EW-1a-detached.rtf", ],options.reparse)

    # run_sample_cases(options.reparse)

    # dump_param_list()

if __name__ == "__main__":
    unittest.main()