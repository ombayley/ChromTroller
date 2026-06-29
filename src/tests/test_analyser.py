#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import pytest
import os
import pandas as pd
from src.analysis.ct_analyser import Analyser


def test_load_chromatogram():
    analyser = Analyser()


def test_process_chromatogram():
    pass


def test_plot_chromatogram():
    pass


def test_get_abs_time():
    path = r"D:\CDSProjects\RoboChem_1\Polymer_Degradation\Results\Polyurethanes\TEST2_20250923_2.rslt\run2_06.dx"
    analyser = Analyser()
    res = analyser.get_abs_at_time(sample_filepath=path, elution_time=0.5)
    print(res)


def test_run_analysis():
    path = r"Z:\personal_file_transfer\olly_file_transfer\NN_PhOTMS_Telescope_Manual_Test_2.rslt\Sample_2026-01-24 23-27-23+01-00-r010.dx"
    analyser = Analyser()
    run_result = analyser.run_analysis(sample_filepath=path, save_data=True)
    print(run_result)


def test_plot_all_spectra():
    pass



def test_save_all_spectra():
    pass


def test_batch_process_chromatograms():
    path = r"Z:\personal_file_transfer\olly_file_transfer\NN_PhOTMS_Telescope_Manual_Test_2.rslt"
    analyser = Analyser()
    all_peaks = pd.DataFrame()

    for file in os.listdir(path=path):
        if file.endswith(".dx"):
            run_result = analyser.run_analysis(sample_filepath=os.path.join(path, file))
            run_result['name'] = file
            all_peaks = pd.concat([all_peaks, run_result], ignore_index=True)

    analyser.save_analysis_results(path=path, peak_data=all_peaks, name="full-peak-summary")


def test_extract_compound_info():
    path = r"D:\CDSProjects\RoboChem_1\eRoboChem\Results\Oxidative\RbC_Oxidative_Campaign_CF3_Anisole_Calibration.rslt\CF3_Anisole_15mM_1,4uL_11-r002.dx"
    analyser = Analyser()
    run_result = analyser.run_analysis(sample_filepath=path)
    run_result = analyser.add_assignments(peak_data=run_result)
    analyser.save_analysis_results(peak_data=run_result, name="assignment-test")


if __name__ == "__main__":
    pytest.main(["-s", __file__])
