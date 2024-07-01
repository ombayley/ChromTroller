#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import logging
import threading


class Analyser:
    def __init__(self, run_log_list):
        self.run_log_list = run_log_list
        logging.info("Analyser Object Initialized Successfully")

    def log_info(self, message):
        logging.info(message)
        with threading.Lock():
            self.run_log_list[-1].analysis = message
