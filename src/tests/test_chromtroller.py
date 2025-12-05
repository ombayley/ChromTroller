#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
from ChromTroller import ChromTroller


def test_load_chromatogram():
    """Run test via debugger to allow GUI pop-up box"""
    ct = ChromTroller()
    ct.new_file_path = r"D:\CDSProjects\RoboChem_1\Polymer_Degradation\Results\Polyurethanes\TEST2_20250923_2.rslt\run2_06.dx"
    absorb = ct.get_abs_at_time(elution_time=1.0)
    print(absorb)


def test_set_valve():
    ct = ChromTroller()
    ct.lcms_controller.set_valve_to_pos("A")  # Filling Position
    # ct.lcms_controller.set_valve_to_pos("B")  # Loading Position


def test_acquisition():
    ct = ChromTroller()
    ct.start_hplc_run()


def test_analysis():
    ct = ChromTroller()
    ct.run_data_analysis()
