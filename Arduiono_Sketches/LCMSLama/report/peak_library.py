#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Original code by: HaasCP
Source: https://github.com/HaasCP/mocca
Licensed under the MIT License

Modified code for the LAMA package by: O.Bayley
"""
import os
import pandas as pd


def report_peak_library(peak_db, report_path):
    """
    Main report function for the peak database.
    """
    if not peak_db.peaks:
        print("No peaks in the peak database!")
        return

    peaks = peak_db.peaks
    peak_df = peaks_to_df(peaks)
    csv_path = os.path.join(report_path, "Peak_Report.csv")
    peak_df.to_csv(csv_path, index=False)


def peaks_to_df(peaks):
    """
    Transfers relevant information from Peak objects in a pandas df.
    """
    peaks_dict = {'file': [],
                  'retention_time': [],
                  'offset': [],
                  'compound_id': [],
                  'integral': [],
                  'concentration': [],
                  'peak_id': [],
                  'is_saturated': [],
                  'is_pure': [],
                  'istd_keys': [],
                  'istd_concs': [],
                  'is_compound': []}
    for peak in peaks:
        times = peak.dataset.time
        offset_factor = times[1] - times[0]
        peaks_dict['file'].append(os.path.basename(peak.dataset.path))
        peaks_dict['retention_time'].append(times[peak.maximum])
        peaks_dict['offset'].append(peak.offset * offset_factor)
        peaks_dict['peak_id'].append(peak.idx)
        peaks_dict['is_saturated'].append(peak.saturation)
        peaks_dict['is_pure'].append(peak.pure)
        peaks_dict['integral'].append(peak.integral)
        if peak.istd:
            istd_keys = [istd.compound_id for istd in peak.istd]
            istd_concs = [istd.concentration for istd in peak.istd]
            peaks_dict['istd_keys'].append(istd_keys)
            peaks_dict['istd_concs'].append(istd_concs)
        else:
            peaks_dict['istd_keys'].append(None)
            peaks_dict['istd_concs'].append(None)
        peaks_dict['compound_id'].append(peak.compound_id)
        peaks_dict['concentration'].append(peak.concentration)
        peaks_dict['is_compound'].append(peak.is_compound)
    return pd.DataFrame(peaks_dict)