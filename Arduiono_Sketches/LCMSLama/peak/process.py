#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Original code by: HaasCP
Source: https://github.com/HaasCP/mocca
Licensed under the MIT License

Modified code for the LAMA package by: O.Bayley
"""
from LAMA.LCMSLama.peak.models import (ProcessedPeak)


def process_peak(peak, compound, is_compound=False):
    """
    Creates a processed peak by addding compound information to it.
    """
    return ProcessedPeak(left=peak.left,
                         right=peak.right,
                         maximum=peak.maximum,
                         offset=peak.offset,
                         dataset=peak.dataset,
                         idx=peak.idx,
                         saturation=peak.saturation,
                         pure=peak.pure,
                         integral=peak.integral,
                         istd=peak.istd,
                         compound_id=compound.key,
                         concentration=compound.conc,
                         is_compound=is_compound)
