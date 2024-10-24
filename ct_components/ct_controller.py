#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: Controls the behavior of the LCMS and switching system, allowing it to read data
and trigger complex behaviors. This script handles hardware communication, sensor monitoring,
and automation of the analysis cycle.
"""

import os
import logging
import time
import json
import serial.tools.list_ports
from typing import Any, Dict, Optional

from utils.get_project_directory import get_project_dir
from ct_components.devices.lcms_device import LCMSDevice
from utils.custom_error_classes import *


class Controller:
    """
    The Controller class manages the LCMS device and associated hardware components.
    It initializes hardware connections, monitors sensors, and orchestrates the analysis cycle.
    """
    def __init__(self, hardware_settings) -> None:
        # Get hardware and timing settings
        self.hardware_settings: Dict[str, Any] = hardware_settings
        # Create LCMSDevice object
        self.lcms_device: LCMSDevice = self._init_device()
        # Report initialization success
        self.log_info("Controller Object Initialized Successfully")

    # ----- Initialization Methods -----
    @staticmethod
    def _get_sensitive_settings() -> Dict[str, Any]:
        """
        Read the hardware settings JSON file and return all hardware settings.

        Returns:
            Dict[str, Any]: A dictionary containing the hardware settings.

        Raises:
            FileNotFoundError: If the settings file is not found.
            json.JSONDecodeError: If there is an error decoding the JSON.
            PermissionError: If there is a permission error accessing the file.
        """
        try:
            settings_path = os.path.join(get_project_dir(), 'settings_files', 'sensitive_settings.json')
            with open(settings_path, 'r', encoding='utf-8') as settings_file:
                sensitive_settings = json.load(settings_file)
                logging.info("Loaded hardware settings successfully")
            return sensitive_settings
        except (FileNotFoundError, json.JSONDecodeError, PermissionError) as err:
            logging.error(f"Error occurred when loading hardware settings: {err}")
            raise

    def _init_device(self) -> LCMSDevice:
        """
        Initialize the LCMSDevice object by finding the correct serial port.

        Returns:
            LCMSDevice: An instance of the LCMSDevice class.

        Raises:
            ValueError: If no serial port is found for the device.
        """
        try:
            sensitive_settings = self._get_sensitive_settings()
            serial_num: str = sensitive_settings["arduino_serial_number"]
            device_port: Optional[str] = None
            ports = serial.tools.list_ports.comports()
            for port in ports:
                if port.serial_number == serial_num:
                    device_port = port.device
                    break

            if device_port is None:
                error_msg = f"No serial port found for the device: {serial_num}"
                logging.error(error_msg)
                raise ValueError(error_msg)

            baud_rate: int = self.hardware_settings.get("serial_baud_rate")
            timeout: float = self.hardware_settings.get("serial_timeout")
            logging.info(f"Initializing LCMSDevice on port {device_port} with baud rate {baud_rate}")
            return LCMSDevice(device_port, baud_rate, timeout)
        except Exception as err:
            logging.error(f"Failed to create LCMS Device due error: {err}")
            raise

    # ----- Analysis Method -----

    def run_analysis_cycle(self) -> str:
        """
        Run the routine to start an analytical run.
        This involves the detection, sample loading, and LCMS method triggering.

        Returns:
            str: 'SUCCESS' if the analysis cycle started successfully, 'FAIL' with an error message otherwise.
        """
        logging.info({'HPLC_analysis': 'INITIATED'})
        try:
            # Check devices are connected and in valid states. Raise error if not
            self._check_device_connectivity()
            self.log_info("Hardware connection check: SUCCESS")

            # Ensure that the switch is in the filling position and if not, switch and fill.
            self._check_filling_state()
            self.log_info("Filling pos_check: SUCCESS")

            # Attempt to send start request and wait for LCMS response
            attempt = 0
            max_attempts = 3
            while attempt < max_attempts:
                attempt += 1  # Increment attempt counter

                # Send start analysis and check acknowledgement
                self._send_start_request()
                self.log_info(f"Send start signal: ATTEMPT {attempt}")

                # Check request acknowledgement from spectrometer
                self.log_info("Start request acknowledged: INITIATED")
                try:
                    self._wait_on_lcms_response()
                except LCMSCommunicationError:
                    self.log_info(f"Attempt {attempt} failed. LCMS did not acknowledge start request.")
                    continue  # Try again

                self.log_info("Start request acknowledged: SUCCESS")
                break  # Exit loop if successful
            else:
                error_msg = f"HPLC not starting after {max_attempts} attempts"
                logging.error(error_msg)
                raise LCMSCommunicationError(error_msg)

            time.sleep(0.3)

            # Wait for start signal/sample prep completion response from spectrometer
            self.log_info("Start signal: WAITING")
            self._wait_on_lcms_start()
            self.log_info("Start signal: SUCCESS")

            # Load from the switch valve
            self.log_info("Valve set to load position: WAITING")
            self.set_valve_to_pos(self.hardware_settings["sample_loading_position"])
            self.log_info("Valve set to load position: SUCCESS")

            # Sleep while emptying sample loop to prevent any accidental switching (Safety precaution)
            self.log_info("Sample loading: WAITING")
            time.sleep(self.hardware_settings["sample_loop_fill_time"])
            self.log_info("Sample loading: SUCCESS")

            # Report triggering success
            self.log_info("Analysis cycle started successfully")

            return 'SUCCESS'

        except ControllerError as error:
            logging.error(f"Analysis cycle FAILED: {error}")
            raise

    # ----- Compound Command Methods -----

    def _check_device_connectivity(self) -> None:
        """
        Check that the Arduino microcontroller, switch valve, phase sensor, and LCMS are connected.

        Raises:
            DeviceConnectionError: If any of the devices are not connected properly.
        """
        # Check the Arduino receives and sends data
        id_ack = self.lcms_device.get_id()
        if not id_ack:
            error_msg = "Arduino connection failed."
            logging.error(error_msg)
            raise DeviceConnectionError(error_msg)

        # Check the switch valve is connected and in a valid state
        valve_pos_ack = self.lcms_device.get_valve_pos()
        if valve_pos_ack not in ['A', 'B']:
            error_msg = "Valve connection failed."
            logging.error(error_msg)
            raise DeviceConnectionError(error_msg)

        # Check LCMS Power state - Default POWER state '1' when the device is on
        lc_ack = self.lcms_device.get_lcms_power()
        if lc_ack != '1':
            error_msg = "LCMS device not detected or powered off."
            logging.error(error_msg)
            raise DeviceConnectionError(error_msg)

    def _check_filling_state(self) -> None:
        """
        Ensure the switch valve is in the filling state.

        Raises:
            ValvePositionError: If the valve was not in the correct filling position.
        """
        desired_position = self.hardware_settings.get("sample_filling_position")
        current_position = self.lcms_device.get_valve_pos()
        if current_position != desired_position:
            error_msg = "WARNING: sample loop was not in filling position when run start was called"
            logging.error(error_msg)
            print(error_msg)
            raise ValvePositionError(error_msg)

    def _send_start_request(self) -> None:
        """
        Send a start request to the Arduino.

        Raises:
            LCMSCommunicationError: If the acknowledgement is not received or invalid.
        """
        ack = self.lcms_device.send_start_request()
        if ack != self.lcms_device.standard_acknowledge:
            error_msg = "No acknowledgement from Arduino when sending start request."
            logging.error(error_msg)
            raise LCMSCommunicationError(error_msg)

    def _wait_on_lcms_response(self) -> None:
        """
        Wait for the spectrometer to send the 'start request' signal in response to the start trigger.

        Raises:
            LCMSCommunicationError: If the acknowledgement is not received within the timeout.
        """
        timeout = self.hardware_settings.get("lcms_response_timeout")
        polling_time = 0.1
        start_time = time.time()

        while time.time() - start_time < timeout:
            initialization_ack = self.lcms_device.get_lcms_start_request()
            if initialization_ack == '0':  # Request line pulled low indicates acknowledgement
                return
            time.sleep(polling_time)

        error_msg = "No sample prep initiation acknowledgement from spectrometer within timeout."
        logging.error(error_msg)
        raise LCMSCommunicationError(error_msg)

    def _wait_on_lcms_start(self) -> None:
        """
        Wait for the spectrometer to send the 'start' signal.

        Raises:
            LCMSCommunicationError: If the start signal is not received within the timeout.
        """
        timeout = self.hardware_settings.get("lcms_sample_prep_timeout")
        polling_time = 0.1
        start_time = time.time()

        while time.time() - start_time < timeout:
            ready_state = self.lcms_device.get_lcms_start()
            if ready_state == '0':  # Start line pulled low indicates start
                return
            time.sleep(polling_time)

        error_msg = "No run start acknowledgement from spectrometer within timeout."
        logging.error(error_msg)
        raise LCMSCommunicationError(error_msg)

    def set_valve_to_pos(self, desired_position: str) -> None:
        """
        Set the valve position and verify it switched.

        Args:
            desired_position (str): The desired valve position ('A' or 'B').

        Raises:
            ValveSwitchError: If the valve fails to switch to the desired position within the timeout.
        """
        timeout = self.hardware_settings.get("valve_switching_timeout")
        polling_time = 0.1

        self.lcms_device.set_valve_pos(desired_position)

        start_time = time.time()
        while time.time() - start_time < timeout:
            pos = self.lcms_device.get_valve_pos()
            if pos == desired_position:
                return
            time.sleep(polling_time)

        error_msg = f"Valve failed to switch to desired position: {desired_position} after timeout:{timeout}"
        logging.error(error_msg)
        raise ValveSwitchError(error_msg)

    # ----- Utility Methods -----

    @staticmethod
    def log_info(message) -> None:
        """
        Helper method to print and log messages
        """
        logging.info(message)
        print(message)


if __name__ == "__main__":
    try:

        controller = Controller()
        controller.run_analysis_cycle()

    except ControllerError as e:
        logging.error(f"Controller encountered an error: {e}")
        print(f"Controller encountered an error: {e}")
    except KeyboardInterrupt:
        logging.info("Shutting down the controller.")
        print("Shutting down the controller.")
