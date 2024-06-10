#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Original code by: HaasCP
Source: https://github.com/HaasCP/mocca
Licensed under the MIT License

Modified code for the LAMA package by: O.Bayley
"""

import numpy as np

from LAMA.LCMSLama.peak.models import IntegratedPeak
from LAMA.LCMSLama.peak.utils import get_peak_data


def integrate_peak(checked_peak):
    """
    Integrates the peak. Returns an integrated peak with the integral attribute
    set.
    """
    peak_data = get_peak_data(checked_peak)
    # correct baseline
    peak_data = peak_data - peak_data.min()

    integral = np.sum(peak_data).tolist()
    return IntegratedPeak(left=checked_peak.left,
                          right=checked_peak.right,
                          maximum=checked_peak.maximum,
                          offset=checked_peak.offset,
                          dataset=checked_peak.dataset,
                          idx=checked_peak.idx,
                          saturation=checked_peak.saturation,
                          pure=checked_peak.pure,
                          integral=integral)
