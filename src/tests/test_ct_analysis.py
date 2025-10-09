#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description:
"""
from ChromTroller import ChromTroller


def test_analysis_return():
    ct = ChromTroller()
    ct.new_file_path = r"D:\CDSProjects\eRoboChem\Results\ZORBAXC18-SM-Proid-Crude_2025-08-14 12-09-12+02-00.rslt\Crude_2025-08-14 12-21-49+02-00.dx"
    result = ct.run_data_analysis()
    print(result)


if __name__ == "__main__":
    test_analysis_return()
