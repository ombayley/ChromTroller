#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: Main entry point for the ChromTroller package.
This main script controls:
    - communication between a client and the ChromTroller server
    - hardware automation
    - data analysis
    - logging.

The script logs all operations to a logfile found in the log_files dir but also can optionally log
data passed by the client to a separate RunLog which is stored in the run_logs.
The RunLog is not essential to ChromTroller but is useful for maintaining a record of the
chemical conditions used by the RoboChem platform. This helps ensure the UPLC data can always be matched to a run
"""

import logging
import json
import queue
import re
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from ct_components.ct_analyser import Analyser
from ct_components.ct_controller import Controller
from ct_components.ct_monitor import Monitor
from ct_components.ct_runlog import RunLog
from ct_components.ct_server import Server


class ChromTroller:
    """
    The ChromTroller class is the master class for the ChromTroller package, responsible for orchestrating
    the communication between the server, hardware controller, file monitoring, logging, and data analysis components.
    """

    def __init__(self) -> None:
        # Setup Log
        self.setup_logging()
        # Load settings
        self.settings: Dict[str, Any] = self.load_settings()
        # Set path for saving the RunLog data
        self.runlog_path: str = self.get_runlog_path()
        # Set path to the directory with the calibration data.
        self.calib_data_dirpath: str = self.settings.get("calibration_data_path")
        # Connect to the server
        self.server: Server = self.init_server()
        # Connect to the Arduino Controller
        self.lcms_controller_obj: Controller = self.init_controller()
        # List of 'RunLog' objects.
        self.runlog_list: List[RunLog] = []
        self.new_file_path: str = ""

        print("\nChromTroller Ready For Analysis")
        print("REMINDER - Ensure OpenLab CDS is running and has the correct sequence queued\n")

    # ----- Initialization Methods -----

    @staticmethod
    def load_settings() -> Dict[str, Any]:
        """Read the hardware settings JSON found in the settings_files ir and return all hardware settings.

        Returns:
            Dict[str, Any]: A dictionary containing the ChromTroller settings.

        Raises:
            FileNotFoundError: If the settings file is not found.
            json.JSONDecodeError: If there is an error decoding the JSON.
            PermissionError: If there is a permission error accessing the file.
        """
        try:
            proj_path = os.path.dirname(__file__)
            settings_path = os.path.join(proj_path, 'settings_files', 'chromtroller_settings.json')
            with open(settings_path, 'r', encoding='utf-8') as settings_file:
                hardware_settings = json.load(settings_file)
                logging.info("Loaded ChromTroller settings successfully")
            return hardware_settings
        except (FileNotFoundError, json.JSONDecodeError, PermissionError) as err:
            logging.error(f"Error occurred when loading settings {err}")
            raise err

    @staticmethod
    def get_runlog_path() -> str:
        """Set the file saving destination for RunLog data.

        Returns:
         str: Path to the RunLog file.
        """
        # Set path to the 'log_files' directory.
        root_dir_path = os.path.dirname(os.path.abspath(__file__))
        log_dir_path = os.path.join(root_dir_path, 'run_logs')

        # Set the runlog file name
        date_str = datetime.now().strftime("%H-%M-%S_%d-%m-%Y")
        log_file_name = f"RunLog_{date_str}.json"
        log_file_path = os.path.join(log_dir_path, log_file_name)
        logging.info("Set RunLog path successfully")
        return log_file_path

    def init_server(self) -> Server:
        """Initialize the server.

        Returns:
            Server: An instance of a Server class.

        Raises:
            Exception: If server initialization fails.
        """
        message = "Server Initialization:"
        try:
            server = Server(self)
        except Exception as err:
            logging.error(f"{message} FAILURE - {err}")
            print(f"{message} FAILURE")
            raise
        print(f"{message} SUCCESS")
        logging.info(f"{message} SUCCESS")
        return server

    @staticmethod
    def init_controller() -> Controller:
        """Initialize the hardware controller object.

        Returns:
            Controller: An instance of the Controller class.

        Raises:
            Exception: If controller initialization fails.
        """
        message = "Controller Connection:"
        try:
            controller = Controller()
        except Exception as err:
            logging.error(f"{message} FAILURE - {err}")
            print(f"{message} FAILURE")
            raise
        print(f"{message} SUCCESS")
        logging.info(f"{message} SUCCESS")
        return controller

    # ----- Management Methods -----

    def handle_command(self, received_dict: Dict[str, Any]) -> Optional[Any]:
        """Handle the ChromTroller specific commands sent by the client.

        Args:
            received_dict (Dict[str, Any]): The command dictionary received from the client.

        Returns:
            Optional[Any]: The result of the command execution, if any.
        """
        # Commands are sent as encoded json dicts in the format: {'command': com, 'data': data}
        command = received_dict.get('command')
        data = received_dict.get('data')

        logging.info(f"Command received: {command} with data: {data}")

        # Process command to trigger the correct method
        match command:
            case "new_run_name":
                self.add_new_run_log(name=data)
            case "add_run_conc":
                self.add_run_conc(conc=data)
            case "add_reagents":
                self.add_reagents(reagent_list=data)
            case "add_reaction_conditions":
                self.add_reaction_conditions(conditions_dict=data)
            case 'start_hplc_run':
                result = self.start_hplc_run()
                logging.info(f"HPLC run initiation result returned to client: {result}")
                return result
            case 'start_file_monitoring':
                result = self.start_file_monitoring()
                logging.info(f"Identified file returned to the client: {result}")
                return result
            case 'run_data_analysis':
                target_rt: float = 0
                tolerance: float = 0
                if 'target_rt' in data:
                    target_rt: float = data.get('target_rt')
                if 'tolerance' in data:
                    tolerance: float = data.get('tolerance')
                result = self.run_data_analysis(target_rt=target_rt, rt_tolerance=tolerance)
                logging.info(f"Data analysis returned {result} back to client")
                return result
            case _:
                logging.warning(f"Unknown command received: {command}")

    # ----- Action Methods -----

    def add_new_run_log(self, name: str) -> None:
        """Add a new RunLog with the given name to the runlog list.

        Args:
            name (str): The name of the new run.
        """
        new_log = RunLog(run_name=name)
        self.runlog_list.append(new_log)
        self.save_run_logs()

        message = f"New RunLog created: {name}"
        logging.info(message)
        print(message)

    def add_run_conc(self, conc: float) -> None:
        """Add the given concentration to the current RunLog.

        Args:
            conc (float): The concentration to add.
        """
        if not self.runlog_list:
            logging.error("'add_run_conc' called but no RunLog available to add concentration.")
            return
        self.runlog_list[-1].run_conc = conc
        self.save_run_logs()

        message = f"RunLog updated with conc: {conc}"
        logging.info(message)
        print(message)

    def add_reagents(self, reagent_list: List[str]) -> None:
        """Add the given reagents to the current RunLog.

        Args:
            reagent_list (List[str]): The list of reagents to add.
        """
        if not self.runlog_list:
            logging.error("'add_reagents' called but no RunLog available to add reagents.")
            return
        self.runlog_list[-1].reagent_list = reagent_list
        self.save_run_logs()

        message = f"RunLog updated with reagents: {reagent_list}"
        logging.info(message)
        print(message)

    def add_reaction_conditions(self, conditions_dict):
        """Add the given reaction conditions to the current RunLog.

        Args:
            conditions_dict (Dict[str, Any]): The reaction conditions to add.
        """
        if not self.runlog_list:
            logging.error("No RunLog available to add reaction conditions.")
            return
        self.runlog_list[-1].run_conditions = conditions_dict
        self.save_run_logs()

        message = f"RunLog updated with conditions: {conditions_dict}"
        logging.info(message)
        print(message)

    def start_hplc_run(self) -> str:
        """Start the HPLC analysis procedure controlled by the hardware controller.

        Returns:
            str: The result of the HPLC start command - "SUCCESS" or "FAIL".
        """
        message = "HPLC analysis initiated"
        logging.info(message)
        print(message)
        result = self.lcms_controller_obj.run_analysis_cycle()

        if self.runlog_list:
            self.runlog_list[-1].hplc_start = result
            self.save_run_logs()

        message = f"HPLC analysis initiation: {result}"
        logging.info(message)
        print(message)

        return result

    def start_file_monitoring(self) -> Optional[str]:
        """Start the file monitoring process to track the newly generated file.

        Returns:
            Optional[str]: The filename of the new file detected, or None if not found.
        """
        # Get the directory to monitor
        results_dirpath: str = self.get_latest_result_dirpath()
        if not results_dirpath:
            logging.error("Results directory path is invalid.")
            return None

        # Set Up Monitor
        monitor_queue = queue.Queue()
        monitor = Monitor(monitor_queue=monitor_queue, data_dir=results_dirpath)

        # Monitor dir until new file observed
        monitor.start_monitoring()
        message = "File Monitoring Started"
        logging.info(message)
        print(message)
        file_path = monitor_queue.get()
        monitor.stop_monitoring()

        # Log info
        message = f"New File Found At: {file_path}"
        logging.info(message)
        print(message)
        if self.runlog_list:
            self.runlog_list[-1].file = file_path
            self.save_run_logs()

        # Save path to class variable
        self.new_file_path: str = file_path

        return file_path

    def run_data_analysis(self, target_rt: float, rt_tolerance: float = 0.1) -> Dict[str, Any]:
        """Run the automated data analysis for a given run.

        Args:
            target_rt (float): The target retention time (RT) for peak search.
            rt_tolerance (float): The maximum tolerance for identifying the peak

        Returns:
            Dict[str, Any]: The result dictionary from the analysis.
        """

        # Check the self.new_file_path and the latest file by ct time match
        if self.new_file_path != self.find_latest_sample_name_by_ct():
            logging.warning("mismatch between the identified file and the most recent file based on creation time")

        # Create the necessary analyser object
        analyser = Analyser()
        message = "Analysis Initiated"
        logging.info(message)
        print(message)

        # Set the parameters for the peak search
        analyser.set_peak_search(peak_rt=target_rt, rt_tolerance=rt_tolerance)
        message = f"Target peak set to {target_rt} min with a tolerance of {rt_tolerance}"
        logging.info(message)
        print(message)

        # Run the analysis
        result_dict: Dict[str, Any] = analyser.run_analysis(self.new_file_path)
        message = f"Identified Peak: {result_dict}"
        logging.info(message)
        print(message)

        if self.runlog_list:
            self.runlog_list[-1].analysis = result_dict
            self.save_run_logs()

        return result_dict if result_dict is not None else {"peak_rt": None, "integral": None}

    # ----- Utility Methods -----

    @staticmethod
    def setup_logging() -> None:
        """
        Sets log format and file destination
        """
        # Set path to the 'log_files' directory.
        root_dir_path = os.path.dirname(os.path.abspath(__file__))
        log_dir_path = os.path.join(root_dir_path, 'log_files')

        # Ensure the log_files directory exists
        os.makedirs(log_dir_path, exist_ok=True)

        # Set the log file name
        date_str = datetime.now().strftime("%d-%m-%Y--%H-%M-%S")
        log_file_name = f"ChromTroller_{date_str}.log"
        log_file_path = os.path.join(log_dir_path, log_file_name)

        # Set up logging configuration
        logging.basicConfig(
            filename=str(log_file_path),
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(filename)s - %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S',
            filemode='w'  # w=write, a=append
        )

    def save_run_logs(self) -> None:
        """Save the RunLog information to the runlog file."""
        # Convert all RunLog objects to dictionaries
        run_logs_dict = [run_log.to_dict() for run_log in self.runlog_list]

        # Write the list of run logs to the file
        with open(self.runlog_path, 'w', encoding='utf-8') as file:
            json.dump(run_logs_dict, file, indent=4)

    def get_latest_result_dirpath(self) -> Optional[str]:
        """Find the most recently created results directory inside the master result directory.

        Returns:
            Optional[str]: Path to the most recent directory, or None if not found.
        """
        # OpenLab CDS stores all new results within the projects 'Results' directoy:
        # "D:\\CDSProjects\\Project\\Results",
        project: str = self.settings.get("project_name")
        project_all_results_dir: str = os.path.join("D:", "CDSProjects", project, "Results")
        subdir_names: List[str] = next(os.walk(project_all_results_dir))[1]

        # Create the searchable run result tag
        dir_suffix: str = self.settings.get("run_result_dir_tag")
        escaped_dir_suffix = re.escape(dir_suffix)  # fix regex operators (i.e deals with '.')
        run_result_subdir_tag = re.compile(rf'{escaped_dir_suffix}$')

        # Of all the run result subdirs with the given file tag, find the most recent
        most_recent_dirpath = None
        most_recent_ctime = 0
        for subdir in subdir_names:
            if run_result_subdir_tag.search(subdir):
                subdir_path = os.path.join(project_all_results_dir, subdir)
                if os.path.getctime(subdir_path) > most_recent_ctime:
                    most_recent_ctime = os.path.getctime(subdir_path)
                    most_recent_dirpath = subdir_path

        logging.info(f"Current results directory set to: {most_recent_dirpath}")
        return most_recent_dirpath

    def find_latest_sample_name_by_ct(self) -> Optional[str]:
        """
        Find the most recently created result file.

        Returns:
            Optional[str]: Path to the most recent result file, or None if not found.
        """
        result_dir_path = self.get_latest_result_dirpath()
        data_file_type = self.settings.get("data_file_type")

        # Check if the directory exists
        if not os.path.exists(result_dir_path):
            logging.error(f"Result directory does not exist: {result_dir_path}")
            return None

        # Get all files ending with the specified data file type
        matching_files = [filename for filename in os.listdir(result_dir_path) if filename.endswith(data_file_type)]

        if not matching_files:
            logging.info("No matching files found.")
            return None

        # Find the most recent file using max()
        most_recent_filename = max(
            matching_files,
            key=lambda f: os.path.getctime(os.path.join(result_dir_path, f))
        )

        logging.info(f"Most recent file found: {most_recent_filename}")
        return most_recent_filename


if __name__ == "__main__":
    try:
        chrom_troller = ChromTroller()
        chrom_troller.server.listen_for_new_connections()
    except KeyboardInterrupt:
        logging.info("Shutting down the server.")
