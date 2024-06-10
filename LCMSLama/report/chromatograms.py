#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Original code by: HaasCP
Source: https://github.com/HaasCP/mocca
Licensed under the MIT License

Modified code for the LAMA package by: O.Bayley

This script will take the chromatograms stored in the campaign object (passed to this script during report_chroms) and
report them as a datapane page (.html file). This gives the user a view of each chromatogram showing the peak integration
area and the UV-Vis Spectrum for each component/peak in the chromatogram. This report is not used for feeding back into
the machine learning algorithm.
"""

import os
import pandas as pd
import datapane as dp
from PIL import Image

from LAMA.LCMSLama.peak.models import ProcessedPeak
from LAMA.LCMSLama.visualization.basic_plots import plot_1D_data
from LAMA.LCMSLama.visualization.results_plot import plot_chrom_with_peaks
from LAMA.LCMSLama.report.utils import settings_to_df
from LAMA.LCMSLama.report.hplc_input import exps_to_df
from LAMA.LCMSLama.peak.utils import average_peak_spectrum


def report_chroms(chroms, settings, report_path):
    """
    Main Chromatogram report function. This funtion will make the title page then call the required processes.
    """
    if not chroms or all([chrom.bad_data for chrom in chroms]):
        print("No chromatograms given or all chromatograms are bad data!")
        return


# ---- logo resizing works well but when the LAMA program is called from another program, it is ruin from ProgramData
    # which requires admin rights to make or change files. this will cause a crash if LAMA is not run directly ------

    # Find and prepare the program logo for the title page. scale allows the logo size to be changed.
    # this_dir, _ = os.path.split(__file__)
    # program_logo_path = os.path.join(this_dir, "LCMSLama_logo.png")
    # program_logo = Image.open(program_logo_path)
    # width, height = program_logo.size
    # scale = 0.2  # LOGO SIZE CONTROLLED HERE
    # resized_logo = program_logo.resize((int(width * scale), int(height * scale)))
    # resized_logo_path = os.path.join(this_dir, "resized_logo.png")
    # resized_logo.save(resized_logo_path)

    # Prepare the front report page
    chrom_df = chroms_to_df(chroms)
    summary_page = dp.Page(
        title="Start page",
        blocks=[
            dp.Group(
                dp.Text("# Results by chromatogram report"),
                # dp.Media(file=resized_logo_path),
                columns=2
            ),
            dp.Text("### Table: Settings and thresholds used to process "
                    "chromatograms."),
            dp.Table(settings_to_df(settings), label="settings_table"),
            dp.Text("### Table: Chromatograms processed during the campaign."),
            dp.DataTable(chrom_df, label="chrom_table")
        ],
    )
    chrom_pages = []
    for i, chrom in enumerate(chroms):
        if chrom.peaks and all(type(peak) == ProcessedPeak for peak in chrom.peaks):
            page = create_chrom_page(chrom, i + 1)
            chrom_pages.append(page)
    r = dp.Report(
        summary_page,
        *chrom_pages
    )
    r.save(path=os.path.join(report_path, "chromatograms.html"), open=False)


def chroms_to_df(chroms):
    """
    Transfers relevant information from chromatograms in a pandas df.
    """
    chrom_dict = {'index': [],
                  'file': [],
                  'bad_data': [],
                  'compound_run': [],
                  'istd_added': [],
                  'num_peaks': []}

    for i, chrom in enumerate(chroms):
        chrom_dict['index'].append(i + 1)
        chrom_dict['file'].append(os.path.basename(chrom.experiment.path))
        chrom_dict['bad_data'].append(chrom.bad_data)
        chrom_dict['compound_run'].append(chrom.experiment.compound is not None)
        chrom_dict['istd_added'].append(chrom.experiment.istd is not None)
        chrom_dict['num_peaks'].append(len(chrom.peaks))
    chrom_df = pd.DataFrame(chrom_dict)
    return chrom_df


def peaks_to_result_df(peaks):
    """
    Transfers relevant information from Peak objects in a pandas df.
    """
    total_peak_sum = 0
    for peak in peaks:
        if peak.idx > 0:
            total_peak_sum += peak.integral
    peaks_dict = {'peak_id': [],
                  'retention_time': [],
                  'compound_id': [],
                  'concentration': [],
                  'integral': [],
                  'area_percent': [],
                  'is_pure': [],
                  'is_saturated': [],
                  'is_compound': []}
    for peak in peaks:
        times = peak.dataset.time
        peaks_dict['peak_id'].append(peak.idx)
        peaks_dict['retention_time'].append(times[peak.maximum])
        peaks_dict['compound_id'].append(peak.compound_id)
        peaks_dict['concentration'].append(peak.concentration)
        peaks_dict['integral'].append(peak.integral)
        peaks_dict['area_percent'].append(round(peak.integral /
                                                total_peak_sum * 100, 1))
        peaks_dict['is_pure'].append(peak.pure)
        peaks_dict['is_saturated'].append(peak.saturation)
        peaks_dict['is_compound'].append(peak.is_compound)
    return pd.DataFrame(peaks_dict)


def create_chrom_page(chrom, index):
    """
    Creates a report page with details to a chromatogram. It contains a list of
    processed peaks, a chromatogram plot with picked peaks etc.
    """
    exp_df = exps_to_df([chrom.experiment])

    chrom_plot = plot_chrom_with_peaks(chrom)

    spectrum_plots = []
    for peak in chrom:
        spectrum = average_peak_spectrum(peak)
        wls = peak.dataset.wavelength

        df = pd.DataFrame({'x': wls,
                           'y': spectrum})
        title_base = "UV-Vis spectrum of peak at {} min".\
            format(round(peak.dataset.time[peak.maximum], 3))
        if peak.compound_id:
            title = title_base + f' ({peak.compound_id})'
        elif not peak.pure:
            title = title_base + ' (impure)'
        else:
            title = title_base
        plot = plot_1D_data(df, xlabel='Wavelength (nm)',
                            ylabel='Absorbance (mAU)',
                            title=title)
        spectrum_plots.append(plot)

    peaks_df = peaks_to_result_df(chrom.peaks)
    if peaks_df.empty:
        peaks_df.append(pd.Series([None] * len(peaks_df.columns),
                                  index=peaks_df.columns), ignore_index=True)

    return dp.Page(
        title=str(index),
        blocks=[
            dp.Group(
                dp.Text(f"## Details to chromatogram {index}"),
                dp.Text("## L.A.M.S (LAMA Analysis for LC/MS)"),
                columns=2
            ),
            dp.Text("### Table: Experiment as given by the user."),
            dp.Table(exp_df, label="experiment_table"),
            dp.Text("### Figure: Chromatogram with highlighted peaks."),
            dp.Plot(chrom_plot),
            dp.Text("### Table: Peaks found in the chromatogram."),
            dp.DataTable(peaks_df),
            dp.Text("### Figures: Averaged UV-Vis spectra over the picked peak."),
            dp.Group(
                *spectrum_plots,
                columns=2
                )
        ],
    )

