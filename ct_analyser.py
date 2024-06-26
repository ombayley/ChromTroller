#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import logging


class Analyser:
    def __init__(self, log_queue):
        self.log_queue = log_queue
        self.log_info("Analyser Object Initialized Successfully")

    def log_info(self, message):
        if self.log_queue:
            logging.info(message)
            log_info = {'program': 'analyser', 'message': message}
            self.log_queue.put(log_info)
