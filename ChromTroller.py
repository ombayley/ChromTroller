#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: Main entry point for the ChromTroller package.
This main script controls:
    - communication between a client and the ChromTroller server
    - hardware automation
    - data analysis
    - self.log.

The script logs all operations to a logfile found in the log_files dir but also can optionally log
data passed by the client to a separate RunLog which is stored in the run_logs.
The RunLog is not essential to ChromTroller but is useful for maintaining a record of the
chemical conditions used by the RoboChem platform. This helps ensure the UPLC data can always be matched to a run
"""

import json
import queue
import re
import os
import time
from typing import Any, Dict, List, Optional
import tkinter as tk
from tkinter import filedialog

from src.utils.get_project_path import get_project_path
from src.utils.logger import get_logger, Logger
from src.utils.custom_error_classes import *
from src.ct_components.ct_analyser import Analyser
from src.ct_components.ct_controller import Controller
from src.ct_components.ct_monitor import Monitor
from src.ct_components.ct_runlog import RunLog
from src.ct_components.ct_server import Server

# Constants
SETTINGS_PATH = os.path.join(get_project_path(), 'settings_files', 'settings.json')

class ChromTroller:
    """
    The ChromTroller class is the master class for the ChromTroller package, responsible for orchestrating
    the communication between the server, hardware controller, file monitoring, self.log, and data analysis components.
    """

    def __init__(self) -> None:
        # Setup Log
        self.log: Logger = get_logger("ChromTroller")

        # Initialise Class Vars
        self.settings: Dict[str, Any] = self._load_settings()
        self.set_result_directory()
        self.runlog_path: str = self._get_runlog_path()
        self.runlog_list: List[RunLog] = []
        self.new_file_path: str = ""
        self.rt_target = 0
        self.rt_tolerance = 0.1

        # Start the server
        self.server: Server = self._init_server()

        # Connect to the Arduino Controller
        self.lcms_controller: Controller = self._init_controller()

        self.log.info("\nChromTroller Initialised and Ready For Analysis", print_msg=True)
        print("REMINDERS: - Ensure OpenLab CDS is running and has the correct sequence queued"
              "           - Ensure the monitoring path in the settings.json matches that of the OpenLab project\n")

    # ----- Initialization Methods -----

    def _load_settings(self) -> Dict[str, Any]:
        """Read the hardware settings JSON found in the settings_files ir and return all hardware settings.

        Returns:
            Dict[str, Any]: A dictionary containing the ChromTroller settings.

        Raises:
            FileNotFoundError: If the settings file is not found.
            json.JSONDecodeError: If there is an error decoding the JSON.
            PermissionError: If there is a permission error accessing the file.
        """
        try:
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as settings_file:
                settings = json.load(settings_file)
                self.log.info("Loaded ChromTroller settings successfully")
            return settings
        except (FileNotFoundError, json.JSONDecodeError, PermissionError) as err:
            self.log.error(f"Error occurred when loading settings {err}")
            raise

    def _save_settings(self) -> None:
        """Save the current settings to the settings.json.

        Raises:
            FileNotFoundError: If the settings file is not found.
            json.JSONDecodeError: If there is an error decoding the JSON.
            PermissionError: If there is a permission error accessing the file.
        """
        try:
            with open(SETTINGS_PATH, 'w', encoding='utf-8') as json_file:
                json.dump(self.settings, json_file, indent=4)
                self.log.info(f"ChromTroller settings saved to {SETTINGS_PATH}")
        except (FileNotFoundError, json.JSONDecodeError, PermissionError) as err:
            self.log.error(f"Error occurred when loading settings {err}")
            raise err

    def _get_runlog_path(self) -> str:
        """
        Set the file saving destination for RunLog data.

        Returns:
         str: Path to the RunLog file.
        """
        day = time.strftime("%Y_%m_%d")
        save_dir = os.path.join(get_project_path(), "log_files", "run_logs", day)
        os.makedirs(save_dir, exist_ok=True)
        filename = f"RunLog_{time.strftime('%Y_%m_%d-%H_%M_%S')}.json"
        return os.path.join(save_dir, filename)

    def _init_server(self) -> Server:
        """Initialize the server.

        Returns:
            Server: An instance of a Server class.

        Raises:
            Exception: If server initialization fails.
        """
        message = "Server Initialization:"
        try:
            server = Server(self)
            self.log.info(f"{message} SUCCESS", print_msg=True)
            return server
        except Exception as err:
            self.log.error(f"{message} FAILURE - {err}", print_msg=True)
            raise

    def _init_controller(self) -> Controller:
        """Initialize the hardware controller object.

        Returns:
            Controller: An instance of the Controller class.

        Raises:
            Exception: If controller initialization fails.
        """
        message = "Controller Connection:"
        try:
            controller = Controller(hardware_settings=self.settings['hardware_settings'])
            self.log.info(f"{message} SUCCESS", print_msg=True)
            return controller
        except Exception as err:
            self.log.error(f"{message} FAILURE - {err}", print_msg=True)
            raise

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

        self.log.info(f"Command received: {command} with data: {data}")

        # Process command to trigger the correct method
        match command:
            case "add_run_info":
                return self.add_run_info(run_info=data)
            case 'set_analysis_parameters':
                return self.set_analysis_parameters(parameters=data)
            case 'set_analysis_target':
                return self.set_analysis_target(target=data)
            case 'set_analysis_tolerance':
                return self.set_analysis_tolerance(tolerance=data)
            case 'valve_position':
                return self.set_valve(position=data)
            case 'start_hplc_run':
                return self.start_hplc_run()
            case 'run_data_analysis':
                return self.run_data_analysis()
            case _:
                message = f"Unknown command received: {command}"
                self.log.warning(message)
                return f"ERROR: {message}"

    # ----- Action Methods -----

    def add_run_info(self, run_info: Any) -> str:
        """Add a new RunLog with the given name to the runlog list.

        Args:
            run_info (Any): Information given by RoboChem about the run it has performed

        Returns:
            str: Either 'ACK' upon success or 'ERROR' upon failure
        """
        try:
            new_log = RunLog(run_conditions=run_info)
            self.runlog_list.append(new_log)
            self._save_run_logs()
            self.log.info("New RunLog created")
            return "ACK"
        except Exception as err:
            self.log.error(f"Error Arsose: {err} during method: {__name__}")
            return "ERROR"

    def set_valve(self, position: str) -> str:
        """
        Sets the switch valve to the sample loading position
        Parameters:
            position (str): The position to set the valve to. Either 'fill' or 'inject'
        Returns:
            str: Either 'ACK' upon success or 'ERROR' upon failure
        """
        try:
            # Det know positions from the hardware settings
            fill_position: str = self.settings["hardware_settings"]["valve_filling_position"]
            inj_position: str = self.settings["hardware_settings"]["valve_injection_position"]

            # map the given pos to the known positions
            cmd_position = {"fill": fill_position, "inject": inj_position}.get(position.lower())

            # set the valve to the desired position
            self.lcms_controller.set_valve_to_pos(desired_position=cmd_position)
            self.log.info(f"Set valve to position: {position}")
            return "ACK"
        except ValveSwitchError as err:
            self.log.error(f"Error Arsose: {err} during method: {__name__}")
            return "ERROR"

    def set_analysis_parameters(self, parameters: Dict[str, Any]) -> str:
        """
        Sets the parameters for the analysis

        Returns:
            str: Either 'ACK' upon success or 'ERROR' upon failure
        """
        try:
            self.log.info(f"All Current Settings: {self.settings['analysis_settings']}")
            for parameter_key, parameter_value in parameters.items():
                if parameter_key in self.settings['analysis_settings'].keys():
                    self.log.info(f"Updated setting {parameter_key} to {parameter_value}")
                    self.settings['analysis_settings'][parameter_key] = parameter_value
            self._save_settings()
            self.log.info("Analysis parameters updated")
            return "ACK"
        except Exception as err:
            print(err)
            self.log.error(f"Error Arsose: {err} during method: {__name__}")
            return "ERROR"

    def set_analysis_target(self, target: float) -> str:
        """
        Set the target retention time for the data analysis peak picking
         Returns:
            str: Either 'ACK' upon success or 'ERROR' upon failure
        """
        try:
            self.settings["targets"]["peak_rt"]: float = target
            self._save_settings()
            self.log.info(f"Updated the rt_target to {target} min")
            return "ACK"
        except Exception as err:
            self.log.error(f"Error Arsose: {err} during method: {__name__}")
            return "ERROR"

    def set_analysis_tolerance(self, tolerance: float) -> str:
        """
        Set the tolerance for peak assignment during the data analysis
         Returns:
            str: Either 'ACK' upon success or 'ERROR' upon failure
        """
        try:
            self.settings["targets"]["tolerance"]: float = tolerance
            self._save_settings()
            self.log.info(f"Updated the rt tolerance for peak picking to {tolerance} min")
            return "ACK"
        except Exception as err:
            self.log.error(f"Error Arsose: {err} during method: {__name__}")
            return "ERROR"

    def start_hplc_run(self) -> str:
        """Start the HPLC analysis procedure controlled by the hardware controller.

        Returns:
            str: status of run start.
        """
        self.log.info("HPLC analysis initiated", print_msg=True)
        acq_outcome = self.lcms_controller.run_sample_acquisition()

        if self.runlog_list:
            self.runlog_list[-1].hplc_start = acq_outcome
            self._save_run_logs()

        self.log.info(f"HPLC analysis initiation: {acq_outcome}", print_msg=True)

        # Start file monitoring to ensure the run completes, and the desired output file can be found
        new_file_path = self.start_file_monitoring()

        return f"HPLC analysis initiation {acq_outcome} with results saved at {new_file_path}"

    def start_file_monitoring(self) -> Optional[str]:
        """Start the file monitoring process to track the newly generated file.

        Returns:
            Optional[str]: The filename of the new file detected, or None if not found.
        """
        self.log.info("Starting file monitoring system...")
        # Get the directory to monitor
        results_dirpath: str = self._get_latest_result_dirpath()
        if not results_dirpath:
            self.log.error("Results directory path is invalid.", print_msg=True)
            return None

        # Set Up Monitor
        monitor_queue = queue.Queue()
        monitor = Monitor(monitor_queue=monitor_queue, data_dir=results_dirpath)

        # Monitor dir until new file observed
        monitor.start_monitoring()
        self.log.info("File Monitoring Started", print_msg=True)
        file_path = monitor_queue.get()
        monitor.stop_monitoring()

        # Log info
        self.log.info(f"New File Found At: {file_path}", print_msg=True)
        if self.runlog_list:
            self.runlog_list[-1].file = file_path
            self._save_run_logs()

        # Save path to class variable
        self.new_file_path: str = file_path

        return file_path

    def run_data_analysis(self) -> Dict[str, Any]:
        """Run the automated data analysis for a given run.

        Returns:
            Dict[str, Any]: The result dictionary from the analysis.
            Dict looks like:
            {
                data: {
                    peak_rt: [...r.t. list...],
                    integral: [...integral list...],
                    peak_height: [...height list...],
                    *name of reference spectra file*: [...spectral correlations....]
                },
                file_name: str,
                settings: {...},
                given_info: any
            }

        """
        self.log.info("run_data_analysis called", print_msg=True)
        # Check the self.new_file_path and the latest file by ct time match
        if self.new_file_path != self._find_latest_sample_name_by_ct():
            self.log.warning("Mismatch between the identified file and the most recent file based on creation time"
                             f" {self.new_file_path} != {self._find_latest_sample_name_by_ct()}")

        # Create the necessary analyser object
        analyser = Analyser()
        self.log.info("Analysis Initiated", print_msg=True)

        result_dict: Dict[str, Any] = analyser.run_analysis(sample_filepath=self.new_file_path)
        self.log.info(result_dict)

        if self.runlog_list:
            self.runlog_list[-1].analysis = result_dict
            self._save_run_logs()

        if self.runlog_list:
            given_info = self.runlog_list[-1].run_conditions
        else:
            given_info = None

        response = {"data": result_dict,
                    "file_name": self.new_file_path,
                    "settings": self.settings,
                    "given_info": given_info}

        return response
        # return result_dict if result_dict is not None else {"peak_rt": None, "integral": None}

    # ----- Utility Methods -----


    def _save_run_logs(self) -> None:
        """Save the RunLog information to the runlog file."""
        # Convert all RunLog objects to dictionaries
        run_logs_dict = [run_log.to_dict() for run_log in self.runlog_list]

        # Write the list of run logs to the file
        with open(self.runlog_path, 'w', encoding='utf-8') as file:
            json.dump(run_logs_dict, file, indent=4)

    def _get_latest_result_dirpath(self) -> Optional[str]:
        """Find the most recently created results directory inside the master result directory.

        Returns:
            Optional[str]: Path to the most recent directory, or None if not found.
        """
        # OpenLab CDS stores all new results within the projects 'Results' directoy:
        # "D:\\CDSProjects\\Project\\Results"
        # project_all_results_dir: str = os.path.join("D:", "CDSProjects", project, "Results")

        project_results_path: str = self.settings["paths"]["project_results_path"]
        if not os.path.exists(project_results_path):
            raise OSError(f"path does not exist: {project_results_path}")
        self.log.info(f"Searching directory: {project_results_path} for subdirectories")
        subdir_names: List[str] = next(os.walk(project_results_path))[1]
        self.log.info(f"Found subdirectorie: {subdir_names}")

        # Create the searchable run result tag
        dir_suffix: str = self.settings["tags"]["result_dir_tag"]
        escaped_dir_suffix = re.escape(dir_suffix)  # fix regex operators (i.e deals with '.')
        run_result_subdir_tag = re.compile(rf'{escaped_dir_suffix}$')
        self.log.info(f"filtering for tag: {run_result_subdir_tag}")

        # Of all the run result subdirs with the given file tag, find the most recent
        most_recent_dirpath = None
        most_recent_ctime = 0
        for subdir in subdir_names:
            if run_result_subdir_tag.search(subdir):
                subdir_path = os.path.join(project_results_path, subdir)
                if os.path.getctime(subdir_path) > most_recent_ctime:
                    most_recent_ctime = os.path.getctime(subdir_path)
                    most_recent_dirpath = subdir_path

        self.log.info(f"Current results directory set to: {most_recent_dirpath}")
        return most_recent_dirpath

    def _find_latest_sample_name_by_ct(self) -> Optional[str]:
        """
        Find the most recently created result file.

        Returns:
            Optional[str]: Path to the most recent result file, or None if not found.
        """
        result_dir_path = self._get_latest_result_dirpath()
        data_file_type = self.settings["tags"]["data_file_tag"]

        # Check if the directory exists
        if not os.path.exists(result_dir_path):
            self.log.error(f"Result directory does not exist: {result_dir_path}")
            return None

        # Get all files ending with the specified data file type
        matching_files = [filename for filename in os.listdir(result_dir_path) if filename.endswith(data_file_type)]

        if not matching_files:
            self.log.info("No matching files found.")
            return None

        # Find the most recent file using max()
        most_recent_filename = max(
            matching_files,
            key=lambda f: os.path.getctime(os.path.join(result_dir_path, f))
        )

        self.log.info(f"Most recent file found: {most_recent_filename}")
        return most_recent_filename

    @staticmethod
    def print_info(message: str) -> None:
        """
        Shortened method to both log info and print to console.
        Allows logging.info to be used without always printing to console
        """
        logging.info(message)
        print(message)

    def set_result_directory(self):
        """Uses tkinter to select the directory for monitoring and saves to the settings.json"""
        folder = self._select_folder()
        self.settings["paths"]["project_results_path"] = folder
        print(f"Folder set to: {folder}")
        self._save_settings()

    @staticmethod
    def _select_folder():
        """Uses tkinter to select a directory and return the path"""
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        folder_path = filedialog.askdirectory(title="Select The Folder Used For HPLC Data Output")
        if folder_path is None:
            raise Exception("No Directory Specified, Now Shutting off server...")
        root.destroy()
        return folder_path


if __name__ == "__main__":
    try:
        chromtroller = ChromTroller()
        chromtroller.server.listen_for_new_connections()
    except KeyboardInterrupt:
        print("Shutting down the server.")


