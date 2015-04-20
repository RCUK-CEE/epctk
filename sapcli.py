__author__ = 'jonathanchambers'

import logging
import sys
import yaml_io
import argparse

from sap import runner


def print_header(header):
    print("**********************")
    print(header)
    print("**********************")

def sap_from_yaml(fname):
    dwelling = yaml_io.from_yaml(fname)
    runner.run_sap(dwelling)
    runner.run_der(dwelling)
    runner.run_ter(dwelling)
    runner.run_fee(dwelling)

    print_header("SAP RESULTS")
    print((dwelling.er_results.report.print_report()))

    print_header("DER RESULTS")
    print((dwelling.der_results.report.print_report()))

    print_header("TER RESULTS")
    print((dwelling.ter_results.report.print_report()))

    print_header("FEE RESULTS")
    print((dwelling.fee_results.report.print_report()))


def cli():
    parser = argparse.ArgumentParser(description='Run sap on site defined in input file.')
    parser.add_argument('file', metavar='filename', nargs='+',
                        help='path of file(s) to use as SAP inputs')
    return parser


def handle_inputs(parser):
    args = vars(parser.parse_args())
    file_names = args['file']

    # If we only have one file, wrap it in list
    if isinstance(file_names, str):
        file_names = [file_names]

    # TODO: handle other kinds of file input
    for fname in file_names:
        sap_from_yaml(fname)


if __name__ == '__main__':
    handle_inputs(cli())

