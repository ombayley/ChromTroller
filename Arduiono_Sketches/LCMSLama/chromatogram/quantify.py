#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Original code by: HaasCP
Source: https://github.com/HaasCP/mocca
Licensed under the MIT License

Modified code for the LAMA package by: O.Bayley
"""

from LAMA.LCMSLama.peak.quantify import quantify_peak


def quantify_peaks(chrom, quant_comp_db, quali_comp_db):
    """
    Quantifies all peaks in the chromatogram.
    """
    new_peaks = []
    for peak in chrom:
        new_peak = quantify_peak(peak, quant_comp_db, quali_comp_db)
        new_peaks.append(new_peak)
    chrom.peaks = new_peaks
    return chrom
