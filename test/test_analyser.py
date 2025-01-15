#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import pandas as pd
from scipy.signal import find_peaks, peak_widths
from ct_components.ct_analyser import Analyser
from typing import List, Any


def get_peak_widths(smpl_chromatogram) -> List[float]:
    """
    Get the width of the peak
    Args:
        smpl_chromatogram (Chromatogram): PROCESSED Chromatogram object

    Returns:
        List[float]: Width of the peak
    """
    components: List[Any] = smpl_chromatogram.all_components()

    for component in components:
        peak_idx, peak_properties = find_peaks(component.concentration)
        peak_width = peak_widths(component.concentration, peak_idx)
        print(component.concentration[peak_idx])
        print(peak_width)

def main():
    dirpath = r"\\fnwi-s0.science.uva.nl\hims-nrg-robochem\lcms_data\FGT\FGT_12_11_2024.rslt\Sample_003_06.dx"
    analyser = Analyser()
    spectrum = analyser.get_processed_spectrum(file_path=dirpath)
    components = spectrum.all_components()

    peaks_dict = {
        "peak_rt": [spectrum.time[component.elution_time] for component in components],
        "integral": [component.integral for component in components],
        "peak_height": [max(component.concentration) for component in components]
    }
    df = pd.DataFrame(peaks_dict)
    print(df)

if __name__ == "__main__":
    main()
