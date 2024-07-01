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
import copy
from datetime import datetime
from ct_server import Server
from ct_controller import Controller
from ct_analyser import Analyser
from ct_runlog import RunLog
from ct_monitor import Monitor


class ChromTroller:
    def __init__(self):
        # Setup Log
        self._setup_logging()
        # Set path for saving the RunLog data
        self.run_log_file_path = self.set_run_log_save_path()
        # Set path to the results directory. TODO path set by OpenLabs CDS, Find a way to link CT and OL.
        self.results_dir_path = r"C:\Users\obayley\Platform_Data\Dummy_results_dir"

        # List of 'RunLog' objects. Shared by ct programs (and treads)
        self.run_log_list = []
        # Lock for thread safety
        self.lock = threading.Lock()
        # Start thread for monitoring log queue and logging
        threading.Thread(target=self.stream_updates, daemon=True).start()

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
            controller = Controller(port='COM3', run_log_list=self.run_log_list)
        except Exception as err:
            logging.error(f"Failed to connect to controller: {err}")
            return None
        logging.info("Successfully connected to instrument controller")
        return controller

    # --

    def init_monitor(self):
        try:
            monitor = Monitor(run_log_list=self.run_log_list)
        except Exception as err:
            logging.error(f"Failed to connect to monitor: {err}")
            return None
        logging.info("Successfully connected to monitor")
        return monitor

    # --

    def init_analyser(self):
        """Initialise the analyser object"""
        try:
            analyser = Analyser(run_log_list=self.run_log_list)
        except Exception as err:
            logging.error(f"Failed to connect to analyser: {err}")
            return None
        logging.info("Successfully connected to analyser")
        return analyser

    # -----Init Methods END-----
    # -----Management Methods START -----

    def handle_command(self, client_data, client_socket):
        """Handles the CT specific commands sent by the client"""

        # Commands are sent as encoded json dicts in the format: {'command': com, 'data': data}
        received_dict = json.loads(client_data.decode())
        command = received_dict['command']
        data = received_dict['data']
        logging.info(f"Command received: {command} with data: {data}")

        # Process command to trigger the correct method
        match command:
            case "new_run_name":
                self.add_new_run_log(data)
            case "set_run_conc":
                self.set_run_conc(data)
            case "add_reagents":
                self.add_reagents(data)
            case "add_reaction_conditions":
                self.add_reaction_conditions(data)
            case 'start_hplc_run':
                self.start_hplc_run(client_socket)

            # case 'get_status':
            #     run_log_obj = self.run_log_list[-1]
            #     run_log_str = json.dumps(run_log_obj.to_dict())
            #     client_socket.sendall(run_log_str.encode())
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
    def add_new_run_log(self, name):
        with threading.Lock():
            new_log = RunLog(run_name=name)
            self.run_log_list.append(new_log)

    def set_run_conc(self, conc):
        with threading.Lock():
            self.run_log_list[-1].run_conc = conc

    def add_reagents(self, reagent_list):
        with threading.Lock():
            self.run_log_list[-1].reagent_list = reagent_list

    def add_reaction_conditions(self, conditions_dict):
        with threading.Lock():
            self.run_log_list[-1].run_conditions = conditions_dict

    def start_hplc_run(self, client_socket):
        result = self.lcms_controller_obj.run_analysis_cycle()
        client_socket.sendall(result.encode())
        client_socket.sendall("TERMINATE".encode())  # This is needed to close the client connection
        time.sleep(0.7)  # delay for printig/sending time coordination
        self.monitor_obj.set_dir(self.results_dir_path)
        self.monitor_obj.start_monitoring()

    def stream_updates(self):
        last_run_log = None
        last_run_log_length = 0
        while True:
            with self.lock:
                current_run_log_length = len(self.run_log_list)
                if current_run_log_length > last_run_log_length:
                    # A new run has been added
                    last_run_log = None  # Reset last_RunLog to None
                    last_run_log_length = current_run_log_length

                if self.run_log_list:
                    latest_RunLog = self.run_log_list[-1]
                    if latest_RunLog != last_run_log:
                        if last_run_log:
                            new_data_dict = self.get_diff_dict(latest_RunLog.controller, last_run_log.controller)
                        else:
                            new_data_dict = latest_RunLog.controller

                        print(new_data_dict)
                        if self.client_socket:
                            try:
                                self.client_socket.sendall(str(new_data_dict).encode())
                            except OSError as e:
                                logging.error(f"Error sending data: {e}")
                                self.client_socket = None  # Set client_socket to None to avoid repeated attempts
                        last_run_log = copy.deepcopy(latest_RunLog)
                    self.save_run_logs()

            time.sleep(1)  # Check every second

    def get_diff_dict(self, new_dict, old_dict):
        diff_dict = {}
        for key, value in new_dict.items():
            if key not in old_dict:
                diff_dict[key] = value
            elif new_dict[key] != old_dict[key]:
                diff_dict[key] = value
        return diff_dict

    def save_run_logs(self):
        # Convert all RunLog objects to dictionaries
        run_logs_dict = [run_log.to_dict() for run_log in self.run_log_list]

        # Open the file in write mode to clear its contents
        with open(self.run_log_file_path, 'w') as file:
            # Write the list of run logs to the file
            json.dump(run_logs_dict, file, indent=4)

    # -----Action Methods END-----
    # -----Util Methods START -----

    # -----Util Methods END -----


if __name__ == "__main__":
    chrom_troller = ChromTroller()
    try:
        chrom_troller.server.listen_for_new_connections()
    except KeyboardInterrupt:
        logging.info("Shutting down the server.")
