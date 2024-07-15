#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import json


def print_json():
    path = r"C:\Users\obayley\Documents\GitHub_Repositries\ChromTroller\ct_components\campaign.json"
    with open(path, "r") as file:
        my_dict = json.load(file)

    print(my_dict.keys())
    # print(my_dict['chromatograms'])
    print(my_dict['compounds'])
    print(my_dict['compound_references'])
    print(my_dict['istd_chromatogram'])

if __name__ == "__main__":
    print_json()
