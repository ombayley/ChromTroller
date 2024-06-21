#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""


class CommTracker:
    def __init__(self):
        self.given_client_info = None
        self.controller_info = None
        self.result_info = None
        self.logs = []

    def add_client_info(self, data):
        self.given_client_info = data

    def add_controller_info(self, data):
        self.controller_info = data

    def add_result_info(self, data):
        self.result_info = data

    def add_current_info_to_log(self):
        single_run_info_dict = {
            "Client": self.given_client_info,
            "Controller": self.controller_info,
            "Analyser": self.result_info
        }
        self.logs.append(single_run_info_dict)

    def get_current_run_info(self):
        single_run_info_dict = {
            "Client": self.given_client_info,
            "Controller": self.controller_info,
            "Analyser": self.result_info
        }
        return single_run_info_dict

    def get_prev_run_info(self):
        return self.logs[-1]

    def get_all_run_info(self):
        return self.logs

