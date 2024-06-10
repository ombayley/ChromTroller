#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Original code by: HaasCP
Source: https://github.com/HaasCP/mocca
Licensed under the MIT License

Modified code for the LAMA package by: O.Bayley
"""

def read_custom_data(experiment):
    """
    Returns the given custom data without any preprocessing
    """
    if experiment.custom_data is None:
        raise AttributeError("Custom data has to be given if data should be "
                             "processed with custom hplc_system_tag.")
    custom_data = experiment.custom_data
    return custom_data.data, custom_data.time, custom_data.wavelength
