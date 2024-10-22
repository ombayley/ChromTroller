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
import threading
import time
import json
import serial.tools.list_ports
from typing import Any, Dict, Optional

from ct_components.devices.lcms_device import LCMSDevice
from utils.custom_error_classes import *


class Controller:
    """
    The Controller class manages the LCMS device and associated hardware components.
    It initializes hardware connections, monitors sensors, and orchestrates the analysis cycle.
    """
    def __init__(self) -> None:
        # Get hardware and timing settings
        self.hardware_settings: Dict[str, Any] = self._get_hardware_settings()
        # Create LCMSDevice object
        self.lcms_device: LCMSDevice = self._init_device()
        # Start phase sensor monitoring (separate thread)
        self.sensor_monitor_instance: Optional[SensorMonitor] = None
        self.sensor_monitor_thread: Optional[threading.Thread] = None
        self._start_ps_monitor()
        # Report initialization success
        logging.info("Controller Object Initialized Successfully")

    # ----- Initialization Methods -----
    @staticmethod
    def _get_hardware_settings() -> Dict[str, Any]:
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
            project_path = os.path.dirname(os.path.dirname(__file__))
            settings_path = os.path.join(project_path, 'settings_files', 'hardware_settings.json')
            with open(settings_path, 'r', encoding='utf-8') as settings_file:
                hardware_settings = json.load(settings_file)
                logging.info("Loaded hardware settings successfully")
            return hardware_settings
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
        serial_num: str = self.hardware_settings.get("serial_number")
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

    def _start_ps_monitor(self) -> None:
        """
        Start a new thread to monitor the data from the phase sensor using the SensorMonitor object.
        """
        self.sensor_monitor_instance = SensorMonitor(self.lcms_device, self.hardware_settings)
        self.sensor_monitor_thread = threading.Thread(target=self.sensor_monitor_instance.monitor_loop)
        self.sensor_monitor_thread.daemon = True  # Allows the thread to exit when the main program exits
        self.sensor_monitor_thread.start()
        logging.info("Phase sensor monitoring started on a separate thread.")

    def stop_ps_monitor(self) -> None:
        """
        Stop the phase sensor monitoring thread.
        """
        if self.sensor_monitor_instance:
            self.sensor_monitor_instance.stop()
            logging.info("Stopping phase sensor monitoring.")
        if self.sensor_monitor_thread:
            self.sensor_monitor_thread.join()
            logging.info("Phase sensor monitoring stopped.")

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

            # Ensure phase sensor sees sample. Wait if not there
            self.log_info("ps_sample_detection: BYPASSED")
            # self.wait_for_sample()

            # Attempt to send start request and wait for LCMS response
            attempt = 0
            max_attempts = 3
            while attempt < max_attempts:
                # Send start analysis and check acknowledgement
                self._send_start_request()
                logging.info("Send start signal: SUCCESS")

                # Check request acknowledgement from spectrometer
                logging.info("Start request acknowledged: INITIATED")
                self._wait_on_lcms_response()
                logging.info("Start request acknowledged: SUCCESS")

                break  # Exit loop if successful
            else:
                error_msg = f"HPLC not starting after {max_attempts} attempts"
                logging.error(error_msg)
                raise LCMSCommunicationError(error_msg)

            time.sleep(0.5)

            # Wait for start signal/sample prep completion response from spectrometer
            logging.info("Start signal: WAITING")
            self._wait_on_lcms_start()
            logging.info("Start signal: SUCCESS")

            # Load from the switch valve
            logging.info("Valve set to load position: WAITING")
            self._set_valve_to_pos(self.hardware_settings["sample_loading_position"])
            logging.info("Valve set to load position: SUCCESS")

            # Wait for the sample loop to be flushed through
            logging.info("Sample loading: WAITING")
            time.sleep(self.hardware_settings["sample_loop_fill_time"] * 5)
            logging.info("Sample loading: SUCCESS")

            # Return to initial filling position
            self._set_valve_to_pos(self.hardware_settings["sample_filling_position"])
            logging.info("Valve returned to filling position: SUCCESS")

            # Report triggering success
            logging.info("Analysis cycle started successfully")

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

        # Check the phase sensor reads a valid value
        ps_ack = self.lcms_device.read_phase_sensor()
        if ps_ack not in ['0', '1', '2']:
            error_msg = "Phase sensor connection failed."
            logging.error(error_msg)
            raise DeviceConnectionError(error_msg)

        # Check LCMS Power state - Default POWER state '1' when device is on
        lc_ack = self.lcms_device.get_lcms_power()
        if lc_ack != '1':
            error_msg = "LCMS device not detected or powered off."
            logging.error(error_msg)
            raise DeviceConnectionError(error_msg)

    def _check_filling_state(self) -> None:
        """
        Ensure the switch valve is in the filling state.

        Raises:
            ValveSwitchError: If the valve cannot be switched to the filling position.
        """
        desired_position = self.hardware_settings.get("sample_filling_position")
        current_position = self.lcms_device.get_valve_pos()
        if current_position != desired_position:
            self._set_valve_to_pos(desired_position)
            logging.info(f"Valve switched called to set to filling position: {desired_position}")
            time.sleep(0.1)

        current_position = self.lcms_device.get_valve_pos()
        if current_position != desired_position:
            error_msg = "Valve not setting to desired position"
            logging.error(error_msg)
            raise ValveSwitchError(error_msg)

    def _wait_for_sample(self) -> None:
        """
        Wait for the sample to be detected by the phase sensor within a timeout period.

        Raises:
            SampleDetectionError: If the sample is not detected within the timeout.
        """
        start_time = time.time()
        timeout = self.hardware_settings.get("sample_detection_timeout")
        polling_time = self.hardware_settings.get("phase_sensor_polling_time")
        full_vals = self.hardware_settings.get("full_phase_sensor_values")

        while time.time() - start_time <= timeout:
            ps_value = self.lcms_device.read_phase_sensor()
            if ps_value in full_vals:
                return
            time.sleep(polling_time)

        error_msg = "No sample detected at phase sensor before timeout."
        logging.error(error_msg)
        raise SampleDetectionError(error_msg)

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

    def _set_valve_to_pos(self, desired_position: str) -> None:
        """
        Set valve position and verify it switched.

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
        logging.info(message)
        print(f"    {message}")


# ----- SensorMonitor Class -----

class SensorMonitor:
    """
    Monitors phase sensor data in a separate thread.
    Detects stable changes in the phase sensor readings and acts upon them.
    """

    def __init__(self, lcms_device: LCMSDevice, param_config: Dict[str, Any]) -> None:
        self.lcms_device: LCMSDevice = lcms_device
        self.param_config: Dict[str, Any] = param_config
        self.previous_stable_value: str = self.lcms_device.read_phase_sensor()
        self.previous_ps_value: str = self.previous_stable_value
        self.change_detected_flag: bool = False
        self.change_stable_flag: bool = False
        self.time_of_ps_change: float = time.time()
        self.is_running: bool = True

    def monitor_loop(self) -> None:
        """
        Central monitoring loop.
        Reads data, checks for stable changes, updates previous readings, and acts accordingly.
        """
        logging.info("Phase sensor monitor loop started.")
        while self.is_running:
            # Get current sensor value
            current_ps_value = self.lcms_device.read_phase_sensor()

            # If the change is stable, then perform the action
            if self.change_stable_flag:
                self._act_on_stable_read(current_ps_value)
                self.change_detected_flag = False
                # Reset detection variables
                self.change_stable_flag = False
                self.previous_stable_value = current_ps_value

            # If a change is detected, check the stability of the change
            if self.change_detected_flag:
                self._check_change_stability(current_ps_value)

            # Check for a change in the phase sensor output
            self._check_ps_change(current_ps_value)

            # Update the previous_ps_value for the next loop
            self.previous_ps_value = current_ps_value
            time.sleep(self.param_config["phase_sensor_polling_time"])

        logging.info("Phase sensor monitor loop stopped.")

    def stop(self) -> None:
        """Stop the monitoring loop."""
        self.is_running = False

    def _check_ps_change(self, curr_ps_val: str) -> None:
        """
        Check whether the new reading differs from the previous reading and the previous stable reading.

        Args:
            curr_ps_val (str): The current phase sensor value.
        """
        if curr_ps_val != self.previous_ps_value and curr_ps_val != self.previous_stable_value:
            self.time_of_ps_change = time.time()
            self.change_detected_flag = True
            logging.debug(f"Phase sensor change detected: {curr_ps_val}")

    def _check_change_stability(self, curr_ps_val: str) -> None:
        """
        Check that the new value is consistent over a stability time.

        Args:
            curr_ps_val (str): The current phase sensor value.
        """
        stabl_time_req = self.param_config["phase_sensor_stability_time"]

        # Check if the value remains the same for the required stability time
        if curr_ps_val == self.previous_ps_value:
            if (time.time() - self.time_of_ps_change) >= stabl_time_req:
                self.change_stable_flag = True
                logging.debug(f"Phase sensor change is stable: {curr_ps_val}")
        else:
            self.change_detected_flag = False
            logging.debug("Phase sensor change is not stable.")

    def _act_on_stable_read(self, new_stable_value: str) -> None:
        """
        Perform actions when a stable change in the phase sensor is detected.

        Args:
            new_stable_value (str): The new stable phase sensor value.
        """
        empty_val = self.param_config["empty_phase_sensor_value"]
        full_vals = self.param_config["full_phase_sensor_values"]

        if new_stable_value == empty_val:
            self.lcms_device.set_phase_sensor_value(False)
            logging.info("Phase sensor indicates empty state.")
        elif new_stable_value in full_vals:
            self.lcms_device.set_phase_sensor_value(True)
            logging.info("Phase sensor indicates full state.")
        else:
            logging.warning(f"Unknown phase sensor value: {new_stable_value}")


# ----- Main Execution Block -----

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
