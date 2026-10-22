#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: M. Vanzella
Description: Offline tool that re-runs HPLC peak analysis over saved spectra in batch, outside a live
    experiment. Useful for re-processing or tuning analysis/assignment settings against archived data.
"""
import asyncio
import os
from datetime import datetime

from src.analysis.ct_analyser import Analyser


async def run_batch_hplc_analysis(path: str) -> None:
    """
    Performs analysis on a specified path

    Args:
        path (str): path of the folder
    """
    analyser = Analyser()

    if not os.path.isdir(path):
        raise NotADirectoryError(f"Directory does not exist: {path}")

    output_path = os.path.join(path, "Analysis_results_summary.txt")
    date = {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    files = sorted(file for file in os.listdir(path) if file.lower().endswith(".dx") and file.lower() != "gradient.dx")

    print(f"Analysing {len(files)} file(s) in directory: {path}\n{'-' * 90}\n")

    with open(output_path, "w", encoding="utf-8") as report:
        report.write("HPLC Analysis results\n")
        report.write(f"Input directory: {os.path.abspath(path)}\n")
        report.write(f"Analysis date: {date}\n")
        report.write(f"Number of files: {len(files)}\n")
        report.write("=" * 90 + "\n\n")

        for index, file in enumerate(files, start=1):
            sample_filepath = os.path.join(path, file)

            heading = f"[{index}/{len(files)}] Analysing file: {file}"
            print(f"{heading}\n")
            report.write(f"{heading}\n")

            try:
                run_result = analyser.run_analysis(sample_filepath=sample_filepath)

                if run_result is None or run_result.empty:
                    message = "No peaks found."
                    print(message)
                    report.write(f"{message}\n")

                else:
                    print("\nPeaks found:")
                    report.write("Peaks found:\n")
                    header = f"{'Peak':<8}{'Retention time (min)':<25}{'Integral':<20}{'Height':<20}"

                    print(header)
                    print("-" * 90)
                    report.write(header + "\n")
                    report.write("-" * 90 + "\n")

                    # Table rows
                    for peak_index, (_, peak) in enumerate(run_result.iterrows(), start=1):
                        row = f"{peak_index:<12}{peak['peak_rt']:<18.4f}{peak['integral']:<20.4f}{peak['peak_height']:<20.4f}"
                        print(row)
                        report.write(row + "\n")

                message = f"Chromatogram images saved at 'ChromTroller/src/results/chromatograms' under today's date ({date})"
                print(f"\n{message}")
                report.write(f"\n{message}\n")

            except Exception as exc:
                error_message = f"ERROR analysing {file}: {type(exc).__name__}: {exc}"
                print(error_message)
                report.write(error_message + "\n")

            print("\n" + "-" * 90 + "\n")
            report.write("\n" + "=" * 90 + "\n\n")

    print(f"Batch analysis report saved to: {output_path}")

if __name__ == "__main__":
    path = r"C:\Users\mvanzel\Downloads\campaign1_pyrrolidine_pyrrole_crude_sample"
    asyncio.run(run_batch_hplc_analysis(path))