#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Original code by: HaasCP
Source: https://github.com/HaasCP/mocca
Licensed under the MIT License

Modified code for the LAMA package by: O.Bayley

This code generates a .csv file containing the details of the HPLC inputs. Currently, not calling the report making
here but the chromatograms script which we do use calls the exps_to_df function.
"""

import os
import pandas as pd


def report_hplc_input(exps, report_path):
    """
    Main HPLC input report function.
    """
    if not exps:
        print("No HPLC input was given!")
        return

    exp_df = exps_to_df(exps)
    csv_path = os.path.join(report_path, 'HPLC_input.csv')
    exp_df.to_csv(csv_path, index=False)
    print("written to csv")


def exps_to_df(exps):
    """
    Transfers relevant information of HplcInput objects into a pandas df.
    """
    exp_dict = {'index': [],
                'file': [],
                'compound_key': [],
                'compound_conc': [],
                'compound_is_solvent': [],
                'compound_is_istd': [],
                'istd_keys': [],
                'istd_concs': [],
                'gradient_file': [],
                'processed': []}
    for i, exp in enumerate(exps):
        exp_dict['index'].append(i + 1)
        exp_dict['file'].append(os.path.basename(exp.path))
        if exp.compound:
            exp_dict['compound_key'].append(exp.compound.key)
            exp_dict['compound_conc'].append(exp.compound.conc)
            exp_dict['compound_is_solvent'].append(exp.compound.is_solvent)
            exp_dict['compound_is_istd'].append(exp.compound.is_istd)
        else:
            exp_dict['compound_key'].append(None)
            exp_dict['compound_conc'].append(None)
            exp_dict['compound_is_solvent'].append(None)
            exp_dict['compound_is_istd'].append(None)
        if exp.istd:
            istd_keys = [istd.key for istd in exp.istd]
            istd_concs = [istd.conc for istd in exp.istd]
            exp_dict['istd_keys'].append(istd_keys)
            exp_dict['istd_concs'].append(istd_concs)
        else:
            exp_dict['istd_keys'].append(None)
            exp_dict['istd_concs'].append(None)
        if exp.gradient:
            exp_dict['gradient_file'].append(os.path.basename(exp.gradient.path))
        else:
            exp_dict['gradient_file'].append(None)
        exp_dict['processed'].append(exp.processed)
    return pd.DataFrame(exp_dict)
