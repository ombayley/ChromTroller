#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import os
import pandas as pd
from src.ct_components import Analyser

def test_load_chromatogram():
    analyser = Analyser()

def test_process_chromatogram():
    pass

def test_plot_chromatogram():
    pass

def test_run_analysis():
    path = r""
    analyser = Analyser()
    run_result = analyser.run_analysis(sample_filepath=path)
    print(run_result)

def test_plot_all_spectra():
    pass

def test_save_all_spectra():
    pass

def test_batch_process_chromatograms():
    path = r"C:\Users\obayley\OneDrive - UvA\Desktop\test\racemic"
    analyser = Analyser()
    all_peaks = pd.DataFrame()

    for file in os.listdir(path=path):
        if file.endswith(".dx"):
            run_result = analyser.run_analysis(sample_filepath=os.path.join(path, file))
            run_result['name'] = file
            all_peaks = pd.concat([all_peaks, run_result], ignore_index=True)

    analyser.save_analysis_results(peak_data=all_peaks, name="full-peak-summary")

def test_extract_compound_info():
    path = r"C:\Users\obayley\OneDrive - UvA\Desktop\test\racemic\OB_Yoon_Col-IC-3_Racemic_Crude_Aquisition_Chiral_0-6percent_0,1-0,4mlmin_20min.amx_04.dx"
    analyser = Analyser()
    run_result = analyser.run_analysis(sample_filepath=path)
    run_result = analyser.add_assignments(peak_data=run_result)
    analyser.save_analysis_results(peak_data=run_result, name="assignment-test")

if __name__ == "__main__":
    import pytest
    pytest.main(["-s", __file__])