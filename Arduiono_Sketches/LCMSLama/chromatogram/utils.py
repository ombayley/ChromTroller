#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Original code by: HaasCP
Source: https://github.com/HaasCP/mocca
Licensed under the MIT License

Modified code for the LAMA package by: O.Bayley
"""


def check_same_dataset(peak, other):
    """
    Raises Exception if the two peaks are not from the same dataset.
    """
    if peak.dataset != other.dataset:
        raise Exception("Peaks are not from the same dataset, \
                        when comparing peak {} and {}!".format(peak.idx,
                        other.idx))


def check_overlap(peak, other):
    """
    Returns True if peak overlaps with the peak 'other', and False otherwise.
    """
    return peak.left <= other.left <= peak.right \
        or other.left <= peak.left <= other.right


def get_distance_between(peak, other):
    """
    Returns the distance from the maxima of peak and the other peak.
    """
    return abs(peak.maximum - other.maximum)
