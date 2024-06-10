#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Original code by: HaasCP
Source: https://github.com/HaasCP/mocca
Licensed under the MIT License

Modified code for the LAMA package by: O.Bayley
"""

from LAMA.LCMSLama.peak.models import CorrectedPeak


def correct_offset(integrated_peak, istd_peaks, offset):
    """
    Creates a corrected peak using internal standard peaks to obtain a
    retention time offset.
    """
    return CorrectedPeak(left=integrated_peak.left,
                         right=integrated_peak.right,
                         maximum=integrated_peak.maximum,
                         offset=offset,
                         dataset=integrated_peak.dataset,
                         idx=integrated_peak.idx,
                         saturation=integrated_peak.saturation,
                         pure=integrated_peak.pure,
                         integral=integrated_peak.integral,
                         istd=istd_peaks)
