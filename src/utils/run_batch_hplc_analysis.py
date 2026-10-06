#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: M. Vanzella
Description: Offline tool that re-runs HPLC peak analysis over saved spectra in batch, outside a live
    experiment. Useful for re-processing or tuning analysis/assignment settings against archived data.
"""
from typing import Dict
import asyncio
import os
import pandas as pd

from src.analysis.ct_analyser import Analyser


async def run_batch_hplc_analysis(path: str) -> None:
    """
    Performs analysis on a specified path

    Args:
        path (str): path of the folder

    Returns:
        Dict[str, list]: Peak summary information
        Given in the format:
        {
            "peak_shift": [float] - ppm shift values of each peak,
            "intensity": [float] - intensity value at each peak,
            "width": [float] - width of each peak in ppm,
            "integral": [float] - integral of each peak
        }
    """
    analyser = Analyser()

    print(f"Analysing files in directory: {path}\n-------------------------------------------------------\n")

    for file in os.listdir(path=path):
        if file.endswith(".dx") and file.lower() != "gradient.dx":
            print(f"File : {file}\n")
            run_result = analyser.run_analysis(sample_filepath=os.path.join(path, file))

            if run_result is None or run_result.empty:
                print("No peaks found.")
            else:
                for _, peak in run_result.iterrows():
                    print(f"\nPeaks found:")
                    print(f"\t- Peak rt: {peak['peak_rt']} | "
                          f"Integral: {peak['integral']} | "
                          f"Height: {peak['peak_height']} | ")
            print(f"\nChromatograms images saved at 'ChromTroller/src/results/chromatograms'")
            print("\n---------------------------------------------------------\n")

if __name__ == "__main__":
    path = r"C:\Users\mvanzel\Downloads\HPLC_analysis_imine_2.rslt"
    asyncio.run(run_batch_hplc_analysis(path))