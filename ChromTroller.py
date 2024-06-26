#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import os
import threading
import logging
import json
import time
from datetime import datetime
from queue import Queue
from ct_server import Server
from ct_controller import Controller
from ct_analyser import Analyser
from ct_runlog import RunLog
from ct_monitor import Monitor


class ChromTroller:
    def __init__(self):
        # Setup Log
        self._setup_logging()
        # Public var - list of RunLog objects
        self.run_log_list = []
        # Public var - Shared queue for logging
        self.log_queue = Queue()
        # Public var - list of RunLog objects
        self.run_log_file_path = self.set_run_log_save_path()
        # Start thread for monitoring log queue and logging
        threading.Thread(target=self.process_log_queue, daemon=True).start()

        # Connect to the server
        self.server = Server(self)
        # Connect to the Arduino Controller
        self.lcms_controller_obj = self.init_controller()
        # Start the directory monitor to identify data files
        self.monitor_obj = self.init_monitor()
        # Create the Analysis object
        self.analyser_obj = self.init_analyser()

        # TODO path is set by OpenLabs CDS. Investigate ways to make this
        # Set path to the results directory
        self.results_dir_path = r"C:\Users\obayley\Platform_Data\Dummy_results_dir"

    # -----Init Methods START-----
    @staticmethod
    def _setup_logging():
        """ Sets log format and file destination """
        # Set path to the 'logs' directory.
        root_dir_path = os.path.dirname(os.path.abspath(__file__))
        log_dir_path = os.path.join(root_dir_path, 'logs')

        # Ensure the logs directory exists
        os.makedirs(log_dir_path, exist_ok=True)

        # Set the log file name
        date_str = datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
        log_file_name = f"ChromTroller_{date_str}_logfile.log"
        log_file_path = os.path.join(log_dir_path, log_file_name)

        # Set up logging configuration
        logging.basicConfig(
            filename=log_file_path,
            level=logging.INFO,
            format=f'%(asctime)s - %(levelname)s - %(filename)s - %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S',
            filemode='w'  # w=write, a=append
        )
        # --

    @staticmethod
    def set_run_log_save_path():
        # Get dir path to general 'logs'
        root_dir_path = os.path.dirname(os.path.abspath(__file__))
        log_dir_path = os.path.join(root_dir_path, 'logs')
        # Set the log file name
        date_str = datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
        log_file_name = f"RunLog_{date_str}.json"
        # Set public var
        return os.path.join(log_dir_path, log_file_name)

    # --

    def init_controller(self):
        """Initialise the controller object"""
        try:
            controller = Controller(port='COM3', log_queue=self.log_queue)
        except Exception as err:
            logging.error(f"Failed to connect to controller: {err}")
            return None
        logging.info("Successfully connected to instrument controller")
        return controller

    def init_analyser(self):
        """Initialise the analyser object"""
        try:
            analyser = Analyser(log_queue=self.log_queue)
        except Exception as err:
            logging.error(f"Failed to connect to analyser: {err}")
            return None
        logging.info("Successfully connected to analyser")
        return analyser

    def init_monitor(self):
        try:
            monitor = Monitor(log_queue=self.log_queue)
        except Exception as err:
            logging.error(f"Failed to connect to monitor: {err}")
            return None
        logging.info("Successfully connected to monitor")
        return monitor

    # -----Init Methods END-----
    # -----Management Methods START -----

    def handle_command(self, command):
        logging.info(f"Command received: {command}")
        command, data = self.split_command(command)
        match command:
            case 'run_name':
                self.add_new_run_log(data)
            case 'exp_info':
                self.log_rbc_info(data)
            case 'start_hplc_run':
                self.lcms_controller_obj.run_analysis_cycle()
                time.sleep(0.1)
                self.monitor_obj.set_dir(self.results_dir_path)
                self.monitor_obj.start_monitoring()

            # case 'get_exp_run_info':
            #     status = self.run_log_obj.get_current_run_info()
            #     return status
            # case 'get_hplc_run_status':
            #     status = self.run_log_obj.get_controller_status()
            #     return status
            # case 'start_data_analysis':
            #     resp = self.analyser_obj.process_command(command)
            #     return resp
            # case 'get_data_analysis_status':
            #     status = self.analyser_obj.get_status()
            #     return status

    # -----Management Methods END-----
    # -----Action Methods START-----
    def add_new_run_log(self, data):
        new_log = RunLog(run_name=data)
        self.run_log_list.append(new_log)

    def log_rbc_info(self, message):
        if self.log_queue:
            logging.info(message)
            log_info = {'program': 'robochem', 'message': message}
            self.log_queue.put(log_info)

    def process_log_queue(self):
        while True:
            log_info = self.log_queue.get()
            program = log_info['program']
            message = log_info['message']
            if self.run_log_list:
                # Always adds data to the most recent RunLog object
                self.run_log_list[-1].add_info(program, message)

            print(f'{program}:{message}\n')

            # Add to CT log as well
            logging.info(log_info)
            self.save_run_logs()

    def save_run_logs(self):
        # Convert all RunLog objects to dictionaries
        run_logs_dict = [run_log.to_dict() for run_log in self.run_log_list]

        # Open the file in write mode to clear its contents
        with open(self.run_log_file_path, 'w') as file:
            # Write the list of run logs to the file
            json.dump(run_logs_dict, file, indent=4)

    # -----Action Methods END-----
    # -----Util Methods START -----

    @staticmethod
    def split_command(cmd) -> tuple:
        cmd_parts = cmd.strip().split('-', 1)
        if len(cmd_parts) > 1:
            command, info = cmd_parts[0].strip(), cmd_parts[1].strip()
        else:
            command = cmd_parts[0].strip()
            info = ""
        return command, info

    # -----Util Methods END -----


if __name__ == "__main__":
    chrom_troller = ChromTroller()
    try:
        chrom_troller.server.listen_for_new_connections()
    except KeyboardInterrupt:
        logging.info("Shutting down the server.")
