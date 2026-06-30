#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: **Add Desc**.
"""
import os
os.environ["OMP_NUM_THREADS"] = "1"

from concurrent.futures import ProcessPoolExecutor

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from src.analysis import Chromatogram
from src.analysis.classes import Component
from src.analysis.dataset.settings import ProcessingSettings

sett = ProcessingSettings(
    min_elution_time=4.5,
    max_elution_time=6.5,
    min_wavelength=250.0,
    max_wavelength=320.0,
    min_rel_prominence=0.05,
    min_rel_integral=0.05,
    split_threshold=0.95,
    max_peak_comps=1
)


def process(chrom: Chromatogram) -> Chromatogram:
    """
    Process the chromatogram based on the analysis settings.

    Args:
        chrom (Chromatogram): Raw chromatogram object.

    Returns:
        Chromatogram: Processed chromatogram.
    """
    # Trim the chromatogram based on wavelength limits
    trimmed_data2d = chrom.extract_wavelength(
        min_wavelength=sett.min_wavelength,
        max_wavelength=sett.max_wavelength,
    )
    proc_chrom = Chromatogram(trimmed_data2d, name=chrom.name)

    proc_chrom = proc_chrom.correct_baseline(
        method=sett.baseline_model,
        smoothness=sett.baseline_smoothness,
    )

    proc_chrom = proc_chrom.find_peaks(
        contraction="max",
        min_rel_height=sett.min_rel_prominence,
        min_height=sett.min_prominence,
        width_at=sett.border_max_peak_cutoff,
        split_threshold=sett.split_threshold,
        expand_borders=True,
        merge_overlapping=True,
        min_elution_time=sett.min_elution_time,
        max_elution_time=sett.max_elution_time,
    )

    proc_chrom = proc_chrom.deconvolve_peaks(
        model=sett.peak_model,
        min_r2=sett.explained_threshold,
        relaxe_concs=sett.relaxe_concs,
        max_comps=sett.max_peak_comps,
    )

    return proc_chrom

def get_peaks(chrom: Chromatogram):
    components: list[Component] = chrom.all_components()
    if not components:
        peaks_dict = {"peak_rt": [], "integral": [], "peak_height": []}
    else:
        peaks_dict = {
            "peak_rt": [chrom.time[comp.elution_time] for comp in components],
            "integral": [round(comp.integral, 2) for comp in components],
            "peak_height": [round(max(comp.concentration), 2) for comp in components],
        }
    return pd.DataFrame(peaks_dict)

def _process_one_file(file_path: Path, dirpath: Path, bkg_filepath: Path) -> pd.DataFrame:
    """Worker: process a single .dx file and return its peaks dataframe."""
    # Build background + sample chromatograms *inside the worker*
    bkg_chrom = Chromatogram(sample=str(bkg_filepath), name="background")
    chrom = Chromatogram(sample=str(file_path), blank=bkg_chrom, name="sample")
    chrom = process(chrom=chrom)

    # Save plot
    plots_dir = dirpath / "plots"
    plots_dir.mkdir(exist_ok=True)
    ax = chrom.plot()
    fig = ax.get_figure()
    fig.savefig(plots_dir / f"{file_path.stem}.png")
    plt.close(fig)

    # Peaks dataframe
    peaks_df = get_peaks(chrom)
    peaks_df["id"] = file_path.name.split("-")[-1].split(".")[0].split("r")[-1]
    peaks_df["file"] = file_path.name

    print(f"Processed {file_path.name}")

    return peaks_df

def main():
    dirpath: Path = Path(r"Z:\personal_file_transfer\olly_file_transfer\RbC_eChem\oxidative_extracted")
    csv_path = dirpath / "peaks.csv"
    bkg_filepath: Path = dirpath / "gradient.dx"

    if csv_path.exists():
        existing_df = pd.read_csv(csv_path)
        processed_files = set(existing_df["file"])
        write_header = False
    else:
        processed_files = set()
        write_header = True

    # Get all .dx files sorted by creation time
    files = sorted(
        (p for p in dirpath.glob("*.dx") if p.name != "gradient.dx"),
        key=lambda p: p.stat().st_ctime,
    )

    files_to_do = [p for p in files if p.name not in processed_files]
    if not files_to_do:
        print("No new files to process.")
        return


    results: list[pd.DataFrame] = []

    # Serial processing
    # for file_path in files_to_do:
    #     peaks_df = _process_one_file(file_path, dirpath, bkg_filepath)
    #     results.append(peaks_df)

    # Parallel processing
    with ProcessPoolExecutor() as ex:
        for peaks_df in ex.map(
                _process_one_file,
                files_to_do,
                [dirpath] * len(files_to_do),
                [bkg_filepath] * len(files_to_do),
        ):
            results.append(peaks_df)

    # Combine and append to CSV once
    combined = pd.concat(results, ignore_index=True)
    combined.to_csv(
        csv_path,
        mode="a" if not write_header else "w",
        index=False,
        header=write_header,
    )

if __name__ == "__main__":
    main()
