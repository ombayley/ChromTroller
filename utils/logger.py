#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import time
import os
import logging
import datetime
from utils.get_project_directory import get_project_dir

def get_logger(name: str, lowest_level: int = logging.DEBUG) -> logging.Logger:
    """Function to set up Logger objects sharing the same configuration.
    Logs are saved in: Platform/Activity_logs

    Args:
        name(str): Name of the Logger object
        lowest_level(int): lowest logging level to be registered in the log (Default: logging.DEBUG)
    Returns:
        logging.Logger: Logger object for the corresponding file
    """
    # Remove existing handlers for the logger to avoid duplicating logs
    logger: logging.Logger = logging.getLogger(name)
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create filename and corresponding file handler
    curr_time = time.strftime("%H-%M-%S", time.localtime())
    timestamp = f"D{datetime.date.today()}_T{curr_time}"
    filename = os.path.join(get_project_dir(), "log_files", f"{timestamp}_{name}.log")
    handler = logging.FileHandler(filename)

    # Set the logging parameters and details for the log entries
    handler.setLevel(lowest_level)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s --  %(message)s  -- [File:%(filename)s, Funct:%(funcName)s, Line:%(lineno)d]",
        datefmt="%H:%M:%S")
    handler.setFormatter(formatter)

    # Add the filehandler to the logger object
    logger.addHandler(handler)
    logger.setLevel(lowest_level)

    return logger

