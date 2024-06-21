#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import threading
from queue import Queue
import logging
from ct_server import Server
from ct_controller import Controller
from ct_analyser import Analyser
from ct_tracker import CommTracker


class ChromTroller:
    def __init__(self):
        # Shared log queue with the controller
        self.log_queue = Queue()
        # Connect to the server
        self.server = Server(self)
        # Connect to the Arduino Controller
        self.lcms_controller = self.init_controller()
        # Connect to the Analysis Controller
        self.analyser = self.init_analyser()
        # Connect to the Analysis Controller
        self.tracker = self.init_comm_tracker()

    def init_controller(self):
        """Initialise the controller object"""
        try:
            controller = Controller(port='COM3', log_queue=self.log_queue)
        except Exception as err:
            logging.error(f"Failed to connect to controller: {err}")
            return None
        logging.info("Successfully connected to instrument controller")
        return controller

    def process_log_queue(self):
        while True:
            log_message = self.log_queue.get()
            logging.info(log_message)

    @staticmethod
    def init_analyser():
        """Initialise the analyser object"""
        try:
            analyser = Analyser()
        except Exception as err:
            logging.error(f"Failed to connect to analyser: {err}")
            return None
        logging.info("Successfully connected to analyser")
        return analyser

    @staticmethod
    def init_comm_tracker():
        """Initialise the comm tracker object"""
        try:
            tracker = CommTracker()
        except Exception as err:
            logging.error(f"Failed to connect to comm tracker: {err}")
            return None
        logging.info("Successfully connected to comm tracker")
        return tracker

    def handle_command(self, command):
        logging.info(f"Command received: {command}")
        command, data = self.split_command(command)
        match command:
            case 'run_info':
                self.tracker.add_client_info(data)
                return "Exp data added to run tracker"
            case 'get_exp_run_info':
                status = self.tracker.get_run_info()
                return status
            case 'start_hplc_run':
                self.lcms_controller.start_analysis()
                return "Analysis started"
            case 'get_hplc_run_status':
                status = self.lcms_controller.get_status()
                return status
            case 'start_data_analysis':
                resp = self.analyser.process_command(command)
                return resp
            case 'get_data_analysis_status':
                status = self.analyser.get_status()
                return status

    @staticmethod
    def split_command(cmd) -> tuple:
        cmd_parts = cmd.strip().split('-', 1)
        if len(cmd_parts) > 1:
            command, info = cmd_parts[0].strip(), cmd_parts[1].strip()
        else:
            command = cmd_parts[0].strip()
            info = ""
        return command, info


if __name__ == "__main__":
    chrom_troller = ChromTroller()
    try:
        chrom_troller.server.listen_for_new_connections()
    except KeyboardInterrupt:
        logging.info("Shutting down the server.")
