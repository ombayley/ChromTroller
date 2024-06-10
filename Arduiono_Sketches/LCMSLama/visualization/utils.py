#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Original code by: HaasCP
Source: https://github.com/HaasCP/mocca
Licensed under the MIT License

Modified code for the LAMA package by: O.Bayley
"""


def round_to_n(x, n):
    """
    Returns number in a format suitable for data visualization.
    """
    if 1e-3 < x < 1e3:
        return round(x, n)
    else:
        return "{0:.{1}e}".format(x, n)
