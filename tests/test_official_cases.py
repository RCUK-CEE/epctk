import logging
import os
import pickle
import unittest

from epctk.appendix import appendix_t
from epctk.dwelling import Dwelling
from epctk.io import input_conversion_rules, yaml_io
from epctk.runner import run_sap, run_fee, run_der
from epctk.utils import SAPCalculationError
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


class TestOfficial(unittest.TestCase):
    def __init__(self, methodName='runTest', fname=None):
        super().__init__(methodName)
        self.param = fname

    def setUp(self):
        self.dwelling = dwelling_from_file(self.param, False)

    # TODO: check the actual SAP results...
    def test_sap(self):
        out = run_sap(self.dwelling)

    def test_fee(self):
        out = run_fee(self.dwelling)

    def test_der(self):
        out = run_der(self.dwelling)

    def test_ter(self):
        out = appendix_t.run_ter(self.dwelling)

        # logging.warning('TER improvements not run, file {}'.format(os.path.basename(self.param)))
        # FIXME: ongoing problems in applying Appendix T improvements
        appendix_t.run_improvements(out)


def load_tests(loader, tests, pattern):
    """
    Dynamically generate test cases for all the test input files,
    so that instead of having one big test for everything, we end up
    with on set of tests for each test input

    Args:
        loader:
        tests:
        pattern:

    Returns:

    """
    suite = unittest.TestSuite()
    for casenum, filename in enumerate(OFFICIAL_CASES):
        if filename in SKIP:
            continue

        fname = os.path.join(_FOLDER, 'official_reference_cases', filename)
        suite.addTest(set_up(loader, fname))
    return suite


def set_up(loader, fname):
    """
    Dynamically set up a new test case suite for each input file.
    Creates a copy of the TestOfficial class and appends the test
    case code (EW_xx) to the name. This makes it easy to identify
    the test when running the test suite, for example in PyCharm
    this will result in a nice readable output from the test runner.

    Args:
        loader:
        fname:

    Returns:

    """
    testnames = loader.getTestCaseNames(TestOfficial)
    suite = unittest.TestSuite()

    class NewClass(TestOfficial): pass

    s = os.path.basename(fname)
    s = s.replace('(','')
    s = s.replace(')','')
    s_parts = s.split('-')
    s = '_'.join(s_parts[1])

    NewClass.__name__ = "{}_{}".format(TestOfficial.__name__, s)
    for name in testnames:
        suite.addTest(NewClass(name, fname=fname))
    return suite


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
        # print("Reparsing ", case_path)
        case = parse_file(case_path, parser)
        pickle.dump(case, open(pickled_file, "w"))

    return case


def create_sap_dwelling(inputs):
    """
    Create a SAP dwelling object from parsed SAP input file
    :param inputs:
    :return:
    """
    dwelling = Dwelling()
    input_conversion_rules.process_inputs(dwelling, inputs)

    # TODO validate inputs
    # if not sap_dwelling_validator.validate(dwelling):
    # logging.error("Bad inputs")

    return dwelling


def dwelling_from_file(fname, reparse):
    yaml_file = os.path.join(_FOLDER, "yaml_test_cases", os.path.basename(fname) + ".yml")
    if os.path.exists(yaml_file) and not reparse:
        dwelling = yaml_io.from_yaml(yaml_file)
    else:
        # Reparse...
        parsed_ref_case = load_reference_case(fname, reference_case_parser.whole_file, reparse)
        dwelling = create_sap_dwelling(parsed_ref_case.inputs)
        with open(yaml_file, 'w') as f:
            yaml_io.to_yaml(dwelling, f)
        output_checker.check_results(dwelling, parsed_ref_case)


    # FIXME Bit of a hack here because some of our tests case files don't include sap region
    if fname in SAP_REGIONS:
        dwelling['sap_region'] = SAP_REGIONS[os.path.basename(fname)]
    elif not dwelling.get("sap_region"):
        dwelling['sap_region'] = 11

    return dwelling


# @unittest.skip("Fast test by skipping official test cases")
# class TestOfficialCases(unittest.TestCase):
#
#     def test_all(self):
#
#         for casenum, filename in enumerate(OFFICIAL_CASES):
#             if filename in SKIP:
#                 continue
#
#             fname = os.path.join(_FOLDER, 'official_reference_cases', filename)
#             dwelling = dwelling_from_file(fname, False)
#
#             run_all_calculation_varieties(dwelling)
#
# def run_all_calculation_varieties(dwelling):
#     run_sap(dwelling)
#     run_fee(dwelling)
#     run_der(dwelling)
#     appendix_t.run_ter(dwelling)
#
#     logging.warning('TER improvements not run')
#     # FIXME: ongoing problems in applying Appendix T improvements
#     # sap.appendix.appendix_t.run_improvements(dwelling)
#

#
#
# def run_sample_cases(force_reparse):
#     for i in range(29):
#         # What about 1?
#         id = i + 2
#         # if id<11: continue
#         if id == 16:
#             continue  # Community heating
#
#         # Don't know what to do
#         # if id==15: continue # Adjustments in table 4c2 also apply to solid
#         # fuel boilers?
#         if id == 20:
#             continue  # two systems and sedbuk - uses made up
#             # PCDF boiler and custom secondary system
#             # type (625), also for some reason a 5%
#             # effy penalty is applied to PCDF boiler
#             # and 2 oil pumps are counted
#         # if id==28: continue # secondary system assumed for some reason
#         if id == 30:
#             # two main systems, one reassigned as secondary.  Why?  FSAP
#             # doesn't do the reassignment
#             continue
#
#         # Cases 8 & 9 - cooling.  Looks like you don't include heat
#         # gain from central heating pumps in the summer cooling demand
#         # calc?
#
#         run_case(os.path.join("reference_dwellings", "%d.rtf" % id), force_reparse)
#

if __name__ == '__main__':
    unittest.main()
