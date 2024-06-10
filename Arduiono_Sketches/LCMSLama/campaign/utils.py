#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Original code by: HaasCP
Source: https://github.com/HaasCP/mocca
Licensed under the MIT License

Modified code for the LAMA package by: O.Bayley
"""


def check_istd(exp, chrom):
    """
    Checks internal standard condition, ie, if the user gives an istd information
    in the experiment, a corresponding peak has to be found in the chromatogram.
    """
    if exp.istd:
        for istd in exp.istd:
            if not any([peak.compound_id == istd.key for peak in chrom]):
                chrom.bad_data = True
    return chrom
