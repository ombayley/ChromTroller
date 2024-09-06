#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import os
import re
import glob
import queue
import logging
import json
from datetime import datetime
from ct_components.ct_server import Server
from ct_components.ct_controller import Controller
from ct_components.ct_analyser import Analyser
from ct_components.ct_runlog import RunLog
from ct_components.ct_monitor import Monitor


class ChromTroller:
    """
    The master class for the ChromTroller package. This class controls the communication
    between the server, hardware controller, file monitoring, logging and data analysis.
    """

    def __init__(self):
        # Setup Log
        self.setup_logging()
        # Load settings
        self.settings = self.load_settings()
        # Set path for saving the RunLog data
        self.runlog_path = self.get_runlog_path()
        # Set path to the directory with the calibration data.
        self.calib_data_dirpath = self.settings.get("calibration_data_path")
        # Connect to the server
        self.server = self.init_server()
        # Connect to the Arduino Controller
        self.lcms_controller_obj = self.init_controller()

        # TODO change to append to .json rather than store as list in memory
        # List of 'RunLog' objects.
        self.runlog_list = []

        print("\nChromTroller Ready For Analysis")
        print("REMINDER - Ensure OpenLab CDS is running and has the correct sequence queued\n")

    # -----Init Methods START-----

    @staticmethod
    def load_settings() -> dict:
        """
        Reads the hardware settings JSON and returns all hardware settings
        :return: dict containing the chromtroller_settings
        """
        try:
            proj_path = os.path.dirname(__file__)
            settings_path = os.path.join(proj_path, 'settings_files', 'chromtroller_settings.json')
            with open(settings_path, 'r', encoding='utf-8') as settings_file:
                hardware_settings = json.load(settings_file)
                logging.info("Loaded chromtroller settings successfully")
            return hardware_settings
        except (FileNotFoundError, json.JSONDecodeError, PermissionError) as err:
            logging.error(f"Error occurred when loading settings {err}")
            raise err

    @staticmethod
    def get_runlog_path() -> str:
        """
        Sets the file saving destination
        :return: path to RunLog file
        """
        # Set path to the 'logs' directory.
        root_dir_path = os.path.dirname(os.path.abspath(__file__))
        log_dir_path = os.path.join(root_dir_path, 'logs')

        # Set the runlog file name
        date_str = datetime.now().strftime("%H-%M-%S_%d-%m-%Y")
        log_file_name = f"RunLog_{date_str}.json"
        log_file_path = os.path.join(log_dir_path, log_file_name)
        logging.info("Set RunLog path successfully")
        return log_file_path

    # ---

    def init_server(self):
        """Initialises the server"""
        message = "Server Initialization:"
        try:
            server = Server(self)
        except Exception as err:
            logging.error(f"{message} FAILURE - {err}")
            print(f"{message} FAILURE")
            raise err
        print(f"{message} SUCCESS ")
        logging.info(f"{message} SUCCESS ")
        return server

    # --
    @staticmethod
    def init_controller():
        """Initialise the hardware controller object"""
        message = "Controller Connection:"
        try:
            controller = Controller()
        except Exception as err:
            logging.error(f"{message} FAILURE - {err}")
            print(f"{message} FAILURE")
            raise err
        print(f"{message} SUCCESS ")
        logging.info(f"{message} SUCCESS ")
        return controller

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
        """Add a new RunLag of given name to the RunLog list"""
        new_log = RunLog(run_name=name)
        self.runlog_list.append(new_log)
        self.save_run_logs()
        self.log_info(f"New RunLog created: {name}")

    def add_run_conc(self, conc):
        """Add given conc to the current RunLog"""
        self.runlog_list[-1].run_conc = conc
        self.save_run_logs()
        self.log_info(f"RunLog updated with conc: {conc}")

    def add_reagents(self, reagent_list):
        """Add given reagents to the current RunLog"""
        self.runlog_list[-1].reagent_list = reagent_list
        self.save_run_logs()
        self.log_info(f"RunLog updated with reagents: {reagent_list}")

    def add_reaction_conditions(self, conditions_dict):
        """Add given conditions to the current RunLog"""
        self.runlog_list[-1].run_conditions = conditions_dict
        self.save_run_logs()
        self.log_info(f"RunLog updated with conditions: {conditions_dict}")

    def start_hplc_run(self):
        """Starts the HPLC analysis procedure which is controlled by ct_controller"""
        self.log_info("HPLC analysis initiated")
        result = self.lcms_controller_obj.run_analysis_cycle()
        self.runlog_list[-1].hplc_start = result
        self.save_run_logs()
        self.log_info(f"HPLC analysis initiation: {result}")
        return result

    def start_file_monitoring(self):
        """Starts the file monitoring process to track the newly generated file"""
        # Set Up Monitor
        results_dirpath = self.get_result_dirpath()
        monitor_queue = queue.Queue()
        monitor = Monitor(monitor_queue=monitor_queue, data_dir=results_dirpath)
        self.log_info("File Monitoring Started.")

        # Monitor dir until new file observed
        monitor.start_monitoring()
        filename = monitor_queue.get()
        monitor.stop_monitoring()

        self.log_info(f"New File Found: {filename}")
        self.runlog_list[-1].file = filename
        self.save_run_logs()

        return filename

    # def calib_analytical_camp(self):
    #     """
    #     Gets the analyser object to prepare the campaign for tracked anlaysis
    #     using the data from the given calib_data_path
    #     """
    #     results_dirpath = self.get_result_dirpath()
    #     self.analyser_obj.set_dirs(
    #         results_data_path=self.results_dirpath,
    #         calib_data_path=self.settings.get("calibration_data_path")
    #     )
    #     self.analyser_obj.reagents_to_calibrate = self.runlog_list[-1].reagent_list
    #     ack = self.analyser_obj.prepare_camp()
    #     self.log_info(f"Campaign analysis calibration: {ack}")

    def run_data_analysis(self):
        """runs the automated data analysis for a given run"""
        results_dirpath = self.get_result_dirpath()
        filename = self.runlog_list[-1].file  # filename = self.get_latest_filename(results_dirpath)
        sample_filepath = os.path.join(results_dirpath, filename)
        analyser = Analyser()
        print("Analysis Initiated")

        analyser.set_peak_search(peak_rt=1.8, rt_tolerance=0.5)

        result_dict = analyser.run_analysis(sample_filepath)

        self.log_info(f"Identified Peak: {result_dict}")
        self.runlog_list[-1].analysis = result_dict
        self.save_run_logs()
        return result_dict

    def save_run_logs(self):
        """Save the RunLog info"""
        # Convert all RunLog objects to dictionaries
        run_logs_dict = [run_log.to_dict() for run_log in self.runlog_list]

        # Open the file in write mode to clear its contents
        with open(self.runlog_path, 'w', encoding='utf-8') as file:
            # Write the list of run logs to the file
            json.dump(run_logs_dict, file, indent=4)

    # -----Util Methods START-----

    @staticmethod
    def setup_logging():
        """
        Sets log format and file destination
        """
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
            format='%(asctime)s - %(levelname)s - %(filename)s - %(message)s',
            datefmt='%H-%M-%S_%d-%m-%Y ',
            filemode='w'  # w=write, a=append
        )

    def get_result_dirpath(self) -> str:
        """
        Finds the most recently created .rslt directory inside the master Result dir
        :return: path to the most recent dir (str)
        """
        master_result_dirpath = self.settings.get("results_master_directory")
        subdirs = next(os.walk(master_result_dirpath))[1]

        dir_suffix = self.settings.get("results_subdir_tag")
        escaped_dir_suffix = re.escape(dir_suffix)  # fix regex operators (i.e deals with '.')
        results_dir_tag = re.compile(rf'{escaped_dir_suffix}$')

        most_recent_dirpath = None
        most_recent_ctime = 0
        for subdir in subdirs:
            if results_dir_tag.search(subdir):
                subdir_path = os.path.join(master_result_dirpath, subdir)
                if os.path.getctime(subdir_path) > most_recent_ctime:
                    most_recent_ctime = os.path.getctime(subdir_path)
                    most_recent_dirpath = subdir_path

        logging.info(f"Current results directory set to: {most_recent_dirpath}")
        return most_recent_dirpath

    def find_latest_sample_path(self):
        data_file_type = self.file_tags["data_file_type"]
        data_files = glob(self.sample_filepath + "/*" + data_file_type)
        name = self.file_tags["sample_tag"].replace(" ", "_").lower()
        sample_files_list = [file for file in data_files if name in file.replace(" ", "_").lower()]
        if sample_files_list:
            sample_files_list = sorted(sample_files_list)
            last_sample = os.path.basename(sample_files_list[-1])
            return last_sample

    @staticmethod
    def log_info(message):
        """log and print info using one function"""
        logging.info(message)
        print(message)

    # -----Util Methods END-----


if __name__ == "__main__":
    try:
        chrom_troller = ChromTroller()
        chrom_troller.server.listen_for_new_connections()
    except KeyboardInterrupt:
        logging.info("Shutting down the server.")
