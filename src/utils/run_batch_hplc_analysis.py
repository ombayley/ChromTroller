#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: M. Vanzella
Description: Offline tool that re-runs HPLC peak analysis over saved spectra in batch, outside a live
    experiment. Useful for re-processing or tuning analysis/assignment settings against archived data.
"""
import asyncio
import os

from src.analysis.ct_analyser import Analyser


async def run_batch_hplc_analysis(path: str) -> None:
    """
    Performs analysis on a specified path

    Args:
        path (str): path of the folder
    """
    analyser = Analyser()

    print(f"Analysing files in directory: {path}\n-------------------------------------------------------\n")

    for file in os.listdir(path=path):
        if file.endswith(".dx") and file.lower() != "gradient.dx":
            print(f"Analysing file: {file}\n")
            run_result = analyser.run_analysis(sample_filepath=os.path.join(path, file))

            if run_result is None or run_result.empty:
                print("No peaks found.")
            else:
                print(f"\nPeaks found:")
                for _, peak in run_result.iterrows():
                    print(f"\t- Peak rt: {peak['peak_rt']} | "
                          f"Integral: {peak['integral']} | "
                          f"Height: {peak['peak_height']}")
            print(f"\nChromatograms images saved at 'ChromTroller/src/results/chromatograms' under today's date")
            print("\n---------------------------------------------------------\n")

if __name__ == "__main__":
    path = r"C:\Users\mvanzel\Downloads\HPLC_analysis_imine_2.rslt"
    asyncio.run(run_batch_hplc_analysis(path))