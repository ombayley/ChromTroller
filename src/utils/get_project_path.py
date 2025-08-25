#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: Centrally located script that can always be used to give the absolute path of the project.
"""
import os


def get_project_path() -> str:
    """
    Function to find the absolute path of the project.
    :return: Str
        Absolute path of the project root.
    """
    return os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

