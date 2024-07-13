#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import os
import queue
import threading
import logging
import json
import time
from datetime import datetime
from ct_components.ct_server import Server
from ct_components.ct_controller import Controller
from ct_components.ct_analyser import Analyser
from ct_components.ct_runlog import RunLog
from ct_components.ct_monitor import Monitor


class ChromTroller:
    def __init__(self):
        # Set path for saving the RunLog data
        self.run_log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        # Set path to the results directory. TODO path set by OpenLabs CDS, Find a way to link CT and OL.
        self.results_data_dir_path = r"C:\Users\obayley\Platform_Data\Dummy_results_dir"
        # Set path to the directory with the calibration data.
        self.calib_data_dir_path = r"C:\Users\obayley\Platform_Data\Dummy_results_dir"
        # Setup Log
        self._setup_logging()

        # List of 'RunLog' objects.
        self.run_log_list = []

        # Queues
        self.controller_queue = queue.Queue()
        self.file_monitor_queue = queue.Queue()
        self.analyser_queue = queue.Queue()

        # Lock for thread safety
        self.lock = threading.Lock()
        # Start thread for monitoring log queue and logging
        # threading.Thread(target=self.stream_updates, daemon=True).start()

        # Connect to the server
        self.server = Server(self)
        # Connect to the Arduino Controller
        self.lcms_controller_obj = self.init_controller()
        # Start the directory monitor to identify data files
        self.monitor_obj = self.init_monitor()
        # Create the Analysis object
        self.analyser_obj = self.init_analyser()

        # Client Socket
        self.client_socket = None

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
        date_str = datetime.now().strftime("%H-%M-%S_%d-%m-%Y")
        log_file_name = f"ChromTroller_{date_str}_logfile.log"
        log_file_path = os.path.join(log_dir_path, log_file_name)

        # Set up logging configuration
        logging.basicConfig(
            filename=log_file_path,
            level=logging.INFO,
            format=f'%(asctime)s - %(levelname)s - %(filename)s - %(message)s',
            datefmt='%H-%M-%S_%d-%m-%Y ',
            filemode='w'  # w=write, a=append
        )

        # Set pat for the Run Log Object Tracking
        log_file_name = f"RunLog_{date_str}.json"

    # --

    def init_controller(self):
        """Initialise the controller object"""
        try:
            controller = Controller(self.controller_queue)
        except Exception as err:
            logging.error(f"Failed to connect to controller: {err}")
            raise err
        logging.info("Successfully connected to instrument controller")
        return controller

    # --

    def init_monitor(self):
        try:
            monitor = Monitor(self.file_monitor_queue)
        except Exception as err:
            logging.error(f"Failed to connect to monitor: {err}")
            raise err
        logging.info("Successfully connected to monitor")
        return monitor

    # --

    def init_analyser(self):
        """Initialise the analyser object"""
        try:
            analyser = Analyser(self.analyser_queue)
        except Exception as err:
            logging.error(f"Failed to connect to analyser: {err}")
            raise err
        logging.info("Successfully connected to analyser")
        return analyser

    # -----Init Methods END-----
    # -----Management Methods START -----

    def handle_command(self, received_dict):
        """Handles the CT specific commands sent by the client"""

        # Commands are sent as encoded json dicts in the format: {'command': com, 'data': data}
        command = received_dict['command']
        data = received_dict['data']
        logging.info(f"Command received: {command} with data: {data}")

        # Process command to trigger the correct method
        match command:
            case "new_run_name":
                self.add_new_run_log(data)
            case "add_run_conc":
                self.add_run_conc(data)
            case "add_reagents":
                self.add_reagents(data)
            case "add_reaction_conditions":
                self.add_reaction_conditions(data)
            case 'start_hplc_run':
                return self.start_hplc_run()
            case 'start_file_monitoring':
                return self.start_file_monitoring()
            case 'run_data_analysis':
                return self.run_data_analysis()

    # -----Management Methods END-----
    # -----Action Methods START-----
    def add_new_run_log(self, name):
        new_log = RunLog(run_name=name)
        self.run_log_list.append(new_log)
        self.save_run_logs()
        self.log_info(f"new run info object made with name: {name}")

    def add_run_conc(self, conc):
        self.run_log_list[-1].run_conc = conc
        self.save_run_logs()
        self.log_info(f"conc: {conc} added to to run info")

    def add_reagents(self, reagent_list):
        self.run_log_list[-1].reagent_list = reagent_list
        self.save_run_logs()
        self.log_info(f"reagents: {reagent_list} added to to run info")

    def add_reaction_conditions(self, conditions_dict):
        self.run_log_list[-1].run_conditions = conditions_dict
        self.save_run_logs()
        self.log_info(f"conditions: {conditions_dict} added to to run info")

    def start_hplc_run(self):
        result = self.lcms_controller_obj.run_analysis_cycle()
        self.run_log_list[-1].hplc_start = result
        self.save_run_logs()
        self.log_info(f"HPLC initiation: {result}")
        return result

    def start_file_monitoring(self):
        self.monitor_obj.set_dir(self.results_data_dir_path)
        self.monitor_obj.start_monitoring()
        filename = self.file_monitor_queue.get()
        self.log_info(f"file found: {filename}")
        self.monitor_obj.stop_monitoring()
        self.run_log_list[-1].file = filename
        self.save_run_logs()
        self.log_info(f"new file found: {filename}")
        return filename

    def calib_analytical_camp(self):
        self.analyser_obj.set_dirs(
            results_data_path=self.results_data_dir_path,
            calib_data_path=self.calib_data_dir_path
        )
        self.analyser_obj.reagents_to_calibrate = self.run_log_list[-1].reagent_list
        ack = self.analyser_obj.prepare_camp()
        self.log_info(f"Campaign analysis calibration: {ack}")

    def run_data_analysis(self):
        self.analyser_obj.set_expected_filename(self.run_log_list[-1].file)
        result_dict = self.analyser_obj.analyse()
        self.log_info(f"Analysis result: {result_dict}")
        self.run_log_list[-1].analysis = result_dict
        self.save_run_logs()
        return result_dict

    def save_run_logs(self):
        # Convert all RunLog objects to dictionaries
        run_logs_dict = [run_log.to_dict() for run_log in self.run_log_list]

        # Open the file in write mode to clear its contents
        with open(self.run_log_file_path, 'w') as file:
            # Write the list of run logs to the file
            json.dump(run_logs_dict, file, indent=4)

    # -----Output streaming Methods START-----
    # TODO implement client method to reccieve 'info' stream before using this
    def stream_updates(self):
        while True:
            if not self.controller_queue.empty():
                self.server.send_to_client(
                    client_socket=self.client_socket,
                    data=self.controller_queue.get(),
                    data_type='info')
            if not self.analyser_queue.empty():
                self.server.send_to_client(
                    client_socket=self.client_socket,
                    data=self.analyser_queue.get(),
                    data_type='info')
            time.sleep(1)  # Check every second

    # -----Output streaming Methods END-----
    # -----Util Methods START-----

    def log_info(self, message):
        logging.info(message)
        print(message)

    # -----Util Methods END-----


if __name__ == "__main__":
    chrom_troller = ChromTroller()
    try:
        chrom_troller.server.listen_for_new_connections()
    except KeyboardInterrupt:
        logging.info("Shutting down the server.")
