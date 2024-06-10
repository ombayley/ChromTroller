#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Original code by: HaasCP
Source: https://github.com/HaasCP/mocca
Licensed under the MIT License

Modified code for the LAMA package by: O.Bayley

To make reporting easier and more modular when calling the program, the reporting has been consolidated to 'main' which
then calls the desired report functions.
"""

from LAMA.LCMSLama.report.chromatograms import report_chroms
from LAMA.LCMSLama.report.peak_library import report_peak_library
from LAMA.LCMSLama.report.single_run_analysis import report_run


def full_report(camp, export_path):
    """
    Consolidated report calling function.
    """
    report_chroms(camp.chroms, camp.settings, export_path)
    report_peak_library(camp.peak_db, export_path)


def report_single_run(camp, export_path, run_file):
    run_rep = report_run(camp.peak_db, run_file)
    return run_rep
