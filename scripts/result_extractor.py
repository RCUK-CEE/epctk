import sys
import logging
import numpy
from tests.test_official_cases import parse_input_file


def print_results(casenum, res):
    results = [
        casenum,
        res.er.energy_lighting,
        res.er.energy_water_heat,
        res.er.energy_water_heat_immersion,
        res.er.energy_water_heat_high_rate,
        res.er.energy_water_heat_low_rate,
        res.er.energy_heating_main,
        res.er.energy_heating_main_1,
        res.er.energy_heating_main_2,
        res.er.energy_heating_main_high_rate,
        res.er.energy_heating_main_low_rate,
        res.er.energy_heating_secondary,
        res.er.energy_fans_and_pumps,
        res.er.energy_mech_vent,
    ]

    for val in results:
        sys.stdout.write("%s," % (val,))
    sys.stdout.write("\n")
    sys.stdout.flush()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

    casenums_skip_test_case = []  # [10,16,20,28,30]

    casenums = numpy.arange(29) + 2
    for casenum in casenums:
        if casenum in casenums_skip_test_case: continue

        logging.info("RUNNING %d" % (casenum,))
        res = parse_input_file(casenum)
        # res,d=v0.run_dwelling(casenum)

        print_results(casenum, res)
