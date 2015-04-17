import logging
import sys
import yaml
import yaml_io

from sap import sap_runner


def print_header(header):
    print("**********************")
    print(header)
    print("**********************")


def main():
    if len(sys.argv) == 1:
        logging.error("Specify a filename")
        sys.exit(-1)

    fname = sys.argv[1]
    dwelling = yaml_io.from_yaml(fname)
    sap_runner.run_sap(dwelling)
    sap_runner.run_der(dwelling)
    sap_runner.run_ter(dwelling)
    sap_runner.run_fee(dwelling)

    print_header("SAP RESULTS")
    print((dwelling.er_results.report.print_report()))

    print_header("DER RESULTS")
    print((dwelling.der_results.report.print_report()))

    print_header("TER RESULTS")
    print((dwelling.ter_results.report.print_report()))

    print_header("FEE RESULTS")
    print((dwelling.fee_results.report.print_report()))


if __name__ == '__main__':
    main()
