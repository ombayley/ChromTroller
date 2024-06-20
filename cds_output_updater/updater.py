#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import os
import logging
import json


def add_to_run_log(argument, path=None):
    if path is None:
        # Sets the default path to the 'logs' directory.
        current_dir_path = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(current_dir_path, 'logs', 'run_data_log')
        logging.info(f"add to log called with {argument}")

    # Check if the file exists
    if os.path.exists(path):
        # Load existing JSON data from file
        with open(path, 'r') as file:
            existing_data = json.load(file)
    else:
        # If the file doesn't exist, create an empty dictionary
        existing_data = []

    new_data = {'Analysis cycle': self.completed_analysis_cycle,
                'RoboChem Run Info': argument
                }

    # Append new data to existing data
    existing_data.append(new_data)
    logging.info(f"adding data: {existing_data}")
    # Write the updated data back to the JSON file
    with open(path, 'w') as file:
        json.dump(existing_data, file, indent=4)
