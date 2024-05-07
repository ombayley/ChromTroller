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
from datetime import datetime


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


def setup_logging(script_name=None):
    """Sets up the logging settings"""


    # Default to the logs directory. Assumes logs dir is in same dir as the utils dir.
    current_dir_path = os.path.dirname(os.path.abspath(__file__))
    root_dir_path = os.path.dirname(current_dir_path)
    path = os.path.join(root_dir_path, 'logs')

    # Ensure the logs directory exists
    os.makedirs(path, exist_ok=True)

    if script_name is None:
        script_name = os.path.basename(__file__).split('.')[0]

    # Set the log file name and path
    date_str = datetime.now().strftime("%d-%m-%Y")
    log_file_name = f"ChromTroller_{date_str}_logfile.log"
    log_file_path = os.path.join(path, log_file_name)

    # Set up logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format=f'%(asctime)s - %(levelname)s - {script_name} - %(message)s',
        datefmt='%d-%m-%Y %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file_path, mode='a'),
            logging.StreamHandler()
        ]
    )


def load_ids_file(secure_id_file_path=None):
    try:
        if secure_id_file_path is None:
            secure_id_file_path = os.path.join('utils', 'private_connection_ids.json')
        with open(secure_id_file_path, 'r') as ids_file:
            config = json.load(ids_file)
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
