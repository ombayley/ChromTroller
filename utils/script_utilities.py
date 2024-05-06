#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Utility script containing functions for logging, timing method execution, and error handling.
"""
import os
import time
import logging
import inspect
import json


def time_method(method):
    """
    This method can be used as a decorator to time method run times.
    Useage: import this script (import script_utilities as util) and add the @ decorator (@util.time_method)
    before any method you wish to monitor.
    """

    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = method(*args, **kwargs)
        end_time = time.time()
        logging.info(f"method {method.__name__} successfully ran in {round(end_time - start_time, 3)} seconds")
        return result

    return wrapper


def setup_logging(path=None, script_name=None):
    """Sets up the logging settings"""
    if path is None:
        # Default to the directory of the script that calls this function if no path given
        path = os.path.dirname(os.path.abspath(__file__))
    if script_name is None:
        # Default to the name of the script that calls this function if none given
        script_name = os.path.basename(__file__).split('.')[0]
    # Set the log file name and path
    log_file_name = f"ChromTroller_{script_name}_logfile.log"
    log_file_path = os.path.join(path, log_file_name)

    # Set up logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%d-%m-%Y %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file_path, mode='w'),
            logging.StreamHandler()
        ]
    )


def load_config_file(config_path=None):
    try:
        if config_path is None:
            config_path = os.path.join('utils', 'utils/config.json')
        with open(config_path, 'r') as config_file:
            config = json.load(config_file)
        return config
    except FileNotFoundError as fnf_e:
        print(fnf_e)
    except json.JSONDecodeError as dec_e:
        print(dec_e)


def handle_error(error_discr, original_error=None):
    """
    Basic function to Log a given error and raise a general exception.
    """
    # Inspect the stack to find the caller of this function index 1 (index 0 is the 'handle_error' itself)
    stack = inspect.stack()
    caller_method = stack[1].function

    logging.error(f"An error arose during the execution of function {caller_method}: {error_discr}")

    if original_error is not None:
        raise RuntimeError("An error occurred during script execution.") from original_error
    else:
        raise RuntimeError("An error occurred during script execution.")
