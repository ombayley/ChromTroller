#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: Controls the behavior of the LCMS and switching system allowing it to read data
and trigger complex behaviours.
"""
import os
import logging
from datetime import datetime
import threading
import time
import json
from ct_components.devices.lcms_device_dummy import LCMSDevice


class Controller:
    """
    Initalise controller object.
    Args:
        log_queue (Queue): a shared Queue object for relaying information between CT and ct_controller
    """

    def __init__(self, log_queue):
        # Shared queue with CT control program
        self.log_queue = log_queue
        # Get hardware and timing settings
        self.hardware_settings = self.get_hardware_settings()
        # Create LCMSDevice object
        self.lcms_device = self.init_device()
        # Start phase sensor monitoring (seperate thread)
        self.start_ps_monitor()
        # Report init success
        logging.info("Controller Object Initialized Successfully")

    # -----Init Methods START-----
    @staticmethod
    def get_hardware_settings() -> dict:
        """
        Reads the hardware settings JSON and returns all hardware settings
        """
        try:
            project_path = os.path.dirname(os.path.dirname(__file__))
            settings_path = os.path.join(project_path, 'settings_files', 'hardware_settings.json')
            with open(settings_path, 'r') as settings_file:
                hardware_settings = json.load(settings_file)
                logging.info("Loaded hardware settings successfully")
            return hardware_settings
        except (FileNotFoundError, json.JSONDecodeError, PermissionError) as err:
            logging.error(err)

    def init_device(self):
        """
        Create the Device object
        """
        port = self.hardware_settings["serial_port"]
        baud_rate = self.hardware_settings["serial_baud_rate"]
        timeout = self.hardware_settings["serial_timeout"]
        return LCMSDevice(port, baud_rate, timeout)

    def start_ps_monitor(self):
        """
        Starts a new thread to monitor the data from the phase sensor using the SensorMonitor object
        """
        sensor_monitor = SensorMonitor(self.lcms_device, self.hardware_settings)
        threading.Thread(target=sensor_monitor.monitor_loop).start()
        logging.info("Phase sensor monitoring started on separate thread.")

    # -----Init Methods END-----
    # ----- Analysis Method START -----
    def run_analysis_cycle(self):
        """
        Runs the routine to start an analytical run.
        This involves the detection, sample loading and lcms method triggering
        """
        self.log_info({'HPLC_analysis': 'INITIATED'})
        try:
            # Check devices are connected and in valid states. Raise error if not
            ack = self._check_device_connectivity()
            self.log_info({'hardware_connection_check': ack})
            self.check_ack(ack)

            # Ensure that the switch is in the filling position and if not, switch and fill.
            ack = self.check_filling_state()
            self.log_info({'filling_pos_check': ack})
            self.check_ack(ack)

            # Ensure phase sensor sees sample. Wait if not there
            self.log_info({'ps_sample_detection': 'WAITING'})
            ack = self.wait_for_sample()
            self.log_info({'ps_sample_detection': ack})
            self.check_ack(ack)

            attempt = 0
            start_ack = "FAIL"
            while attempt < 3:
                # Send start analysis and check acknowledgement.
                send_ack = self._send_start_request()
                self.log_info({'send_start_signal': send_ack})

                # Check request acknowledgement from spectrometer (LCMS method must include this!)
                self.log_info({'start_request_acknowledged': 'WAITING'})
                recc_ack = self._wait_on_lcms_response()
                self.log_info({'start_request_acknowledged': recc_ack})

                if send_ack == "SUCCESS" and recc_ack == "SUCCESS":
                    start_ack = "SUCCESS"
                    break
                attempt += 1
            self.check_ack(start_ack)

            # Wait for start signal/sample prep completion from spectrometer (LCMS method must include this!)
            self.log_info({'start_signal': 'WAITING'})
            ack = self._wait_on_lcms_start()
            self.log_info({'start_request_acknowledged': ack})
            self.check_ack(ack)

            # Load from the switch valve.
            ack = self.switch_valve_to(self.hardware_settings["sample_loading_position"])
            self.log_info({'valve_switched_to_load': ack})
            self.check_ack(ack)

            # Wait for the sample loop to be flushed through
            self.log_info({'sample_loading': 'WAITING'})
            time.sleep(self.hardware_settings["sample_loop_fill_time"])
            self.log_info({'sample_loading': 'SUCCESS'})

            # Return to initial filling position
            ack = self.switch_valve_to(self.hardware_settings["sample_filling_position"])
            self.log_info({'valve_returned_to_bypass': ack})

            # Report triggering success
            self.log_info({'analysis_cycle_started': 'SUCCESS'})
            return 'SUCCESS'

        except Exception as error:
            self.log_info({'analysis_cycle_started': 'FAIL', 'cause': error})
            return f'FAILED - {error}'

    # ----- Analysis Method END -----
    # ----- Compound Command Methods START -----
    def _check_device_connectivity(self):
        """ Checks the Arduino microcontroller, switch valve, phase sensor, and LCMS are connected """

        # Check the arduino receives and sends data
        id_ack = self.lcms_device.get_id()
        if id_ack is None:
            return "FAIL - Error Communicating with the Arduino"

        # Check the switch valve is connected and in a valid state
        valve_pos_ack = self.lcms_device.get_valve_pos()
        if valve_pos_ack not in ['A', 'B']:
            return "FAIL - Error Communicating with the Switch Valve"

        # Check the phase sensor reads a valid value
        ps_ack = self.lcms_device.read_phase_sensor()
        if ps_ack not in ['0', '1', '2']:
            return "FAIL - Error Communicating with the Phase Sensor"

        # Check LCMS Power state  # TODO make the LCMS communicate the Power status. Bypass this until ready
        lc_ack = self.lcms_device.get_power_sate()
        if lc_ack != '1':
            return "SUCCESS"
            # return "FAIL - Error Communicating with the UPLC-MS"

        return "SUCCESS"

    def check_filling_state(self):
        """Checks the switch valve is in the filling state"""
        if self.lcms_device.get_valve_pos() == self.hardware_settings["sample_filling_position"]:
            return "SUCCESS"

        ack = self.switch_valve_to(self.hardware_settings["sample_filling_position"])
        if ack == "SUCCESS":
            return ack

        return "FAIL - Switch valve not in filling poistion"

    def wait_for_sample(self):
        start_time = time.time()
        timeout = self.hardware_settings["sample_detection_timeout"]
        while time.time() - start_time >= timeout:
            self.lcms_device.wait_for_phase_sensor()
            return "SUCCESS"
        return "FAIL - No sample detected at phase sensor before timeout"

    def _send_start_request(self):
        """ Send start request to Arduino. Will return 'k' as an acknowledgement """
        ack = self.lcms_device.send_start_request()
        if ack == self.lcms_device.standard_acknowledge:
            return "SUCCESS"
        if not ack:
            return "FAIL - No acknowledge from Arduino"
        return "FAIL - Bad acknowledge from Arduino"

    def _wait_on_lcms_response(self):
        """
        Waits for the spectrometer to send the 'acknowledge' signal.
        This signal should be a change in the 'ready' line directly after the LC gets the start request
        """
        timeout = self.hardware_settings["lcms_response_timeout"]
        polling_time = 0.05
        start_time = time.time()
        while time.time() - start_time > timeout:
            ready_state = self.lcms_device.check_lcms_ready()
            if ready_state == '1':
                return "SUCCESS"
            time.sleep(polling_time)
        # TODO make the LCMS communicate the acknowledge. Bypass this until ready
        return "SUCCESS"
        # return "FAIL - No acknowledgement from spectrometer within timeout"

    def _wait_on_lcms_start(self):
        """
        Waits for the spectrometer to send the 'start' signal.
        This signal should be at the time of sample injection
        """
        timeout = self.hardware_settings["lcms_sample_prep_time"]
        polling_time = 0.05
        start_time = time.time()
        while time.time() - start_time > timeout:
            ready_state = self.lcms_device.get_start_signal()
            if ready_state == '1':
                return "SUCCESS"
            time.sleep(polling_time)
        # TODO make the LCMS communicate the start. Bypass this until ready
        return "SUCCESS"
        # return "FAIL - No Start Signal Sent From Spectrometer Within Expected Sample Prep time"

    def switch_valve_to(self, desired_position):
        """Set valve position and verify it switched"""
        self.lcms_device.set_valve_pos(desired_position)
        time.sleep(self.hardware_settings["valve_switching_time"])
        pos = self.lcms_device.get_valve_pos()

        if pos == desired_position:
            return "SUCCESS"

        # try the read valve position 2 more times to ensure it truely wasnt set
        retest_count = 0
        while retest_count < 2:
            time.sleep(self.hardware_settings["valve_switching_time"])
            pos = self.lcms_device.get_valve_pos()
            if pos == desired_position:
                return "SUCCESS"

        return 'FAIL - Valve failed to switch to desired position'

    # ----- Compound Command Methods START -----
    # -----Util Methods START-----
    def log_info(self, message):
        logging.info(message)
        print(message)
        self.log_queue.put(message)

    @staticmethod
    def check_ack(ack):
        if 'Fail' in ack:
            raise ack

    # -----Util Methods END-----


class SensorMonitor:
    """
    Monitors phase sensor data. Gets the current data, checks if the current reading is different to the previous.
    If it differs, it flags the change else updates the last read data and repeats the loop. If a change was
    detected, the second loop checks that the change is stable for a set amount of time.
    """

    def __init__(self, lcms_device, param_config):
        self.lcms_device = lcms_device
        self.param_config = param_config
        self.previous_stable_value = self.lcms_device.read_phase_sensor()
        self.previous_ps_value = self.previous_stable_value
        self.change_detected_flag = False
        self.change_stable_flag = False
        self.time_of_ps_change = time.time()

    def monitor_loop(self):
        """
        Central monitoring loop. Starts by reading data, checks for stable changes, updates previous
        run data and then sleeps.
        """
        while True:
            # Get current sensor value
            current_ps_value = self.lcms_device.read_phase_sensor()

            # If the change is stable, then perform the action
            if self.change_stable_flag:
                self.act_on_stable_read(current_ps_value)
                self.change_detected_flag = False
                # Reset detection variables
                self.change_stable_flag = False
                self.previous_stable_value = current_ps_value

            # If a change is detected, check the stability of the change
            if self.change_detected_flag:
                self.check_change_stability(current_ps_value)

            # Check for a change in the phase sensor output
            self.check_ps_change(current_ps_value)

            # Update the previous_ps_value the loop again
            self.previous_ps_value = current_ps_value
            time.sleep(self.param_config["phase_sensor_polling_time"])

    def check_ps_change(self, curr_ps_val):
        """
        Checks whether the new reading differs from the previous reading and the previous stable reading
        """
        if curr_ps_val != self.previous_ps_value and curr_ps_val != self.previous_stable_value:
            self.time_of_ps_change = time.time()
            self.change_detected_flag = True

    def check_change_stability(self, curr_ps_val):
        """
        Checks that the new value is consistent
        """
        # vars for readability
        stabl_time_req = self.param_config["phase_sensor_stability_time"]

        # Checks values match, if not set change_flag as false, if matching for >stabl_time_req then act
        if curr_ps_val == self.previous_ps_value:
            if (time.time() - self.time_of_ps_change) >= stabl_time_req:
                self.change_stable_flag = True
        else:
            self.change_detected_flag = False

    def act_on_stable_read(self, new_stable_value):
        """
        Actions to perform if the new value is stable
        """
        # vars for readability
        empty_val = self.param_config["empty_phase_sensor_value"]
        full_vals = self.param_config["full_phase_sensor_values"]

        # Actions to perform
        if new_stable_value == empty_val:
            self.lcms_device.set_phase_sensor_value(False)
        elif new_stable_value in full_vals:
            self.lcms_device.set_phase_sensor_value(True)
