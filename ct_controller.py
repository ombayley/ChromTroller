#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: Controls the behavior of the LCMS and switching system allowing it to read data
and trigger complex behaviours.
"""
import threading
import time
from devices.lcms_device import LCMSDevice


class Controller:
    """
    Initalise controller object.
    Args:
        port (str): The port to connect to the Arduino device. Defaults to 'COM3'
        baud_rate (float): Baud rate for serial communication. Defaults to '9600'
        timeout (float): max block time (in seconds) for the serial read(). Defaults to '1'
    """

    def __init__(self, port='COM3', baud_rate=9600, timeout=1, log_queue=None):
        # Create LCMSDevice object
        self.lcms_device = LCMSDevice(port, baud_rate, timeout)
        # Get hardware and timing settings
        self.param_config = self.get_instrument_config_parameters()
        # Start phase sensor monitoring (seperate thread)
        self.start_ps_monitor()
        # Threadsafe logging
        self.log_queue = log_queue
        # Report init success
        self.log_info("Controller Object Initialized Successfully")

    # -----Init Methods START-----
    @staticmethod
    def get_instrument_config_parameters() -> dict:
        """
        Function returns a dictionary containing all hardware dependant variable values.
        """
        instrument_params = {
            "sample_filling_position": 'A',
            "sample_loading_position": 'B',
            "sample_loop_fill_time": 3.0,
            "lcms_sample_prep_time": 10.0,
            "valve_switching_time": 0.5,
            "empty_phase_sensor_value": '1',
            "full_phase_sensor_values": ['0', '2'],
            "phase_sensor_stability_time": 0.5,
            "phase_sensor_polling_time": 0.1,
            "lcms_response_timeout": 240
        }
        return instrument_params

    # --
    def start_ps_monitor(self):
        """
        Starts a new thread to monitor the data from the phase sensor using the SensorMonitor object
        """
        sensor_monitor = SensorMonitor(self.lcms_device, self.param_config)
        threading.Thread(target=sensor_monitor.monitor_loop).start()
        self.log_info("Phase sensor monitoring started on separate thread.")

    # -----Init Methods END-----
    # ----- Analysis Method START -----
    def run_analysis_cycle(self) -> str:
        """
        Runs the routine to start an analytical run.
        This involves the detection, sample loading and lcms method triggering
        """
        self.log_info("Analysis Process Initiated...")
        try:
            # Check devices are connected and in valid states. Raise error if not
            self._check_device_connectivity()
            self.log_info("SUCCESS - Hardware Connections Verified")

            # Ensure phase sensor sees sample. Wait if not there
            self.lcms_device.wait_for_phase_sensor()
            self.log_info("SUCCESS - Phase Sensor - Sample Detected")

            # Ensure that the switch is in the filling position and if not, switch and fill.
            self._check_valve_state()
            self.log_info("SUCCESS - Switch Valve - Filling Loop Filled")

            # Send start analysis and check acknowledgement.
            self._send_start_request_wth_error()
            self.log_info("SUCCESS - LCMS - Start Signal Sent By Arduino")

            # Check acknowledgement from spectrometer (LCMS method must include this!)
            self._wait_on_lcms_response()
            self.log_info("SUCCESS - LCMS - Start Acknowledged By Spectrometer")

            # Wait a set time to allow LCMS sample handling, then load from the switch valve.
            time.sleep(self.param_config["lcms_sample_prep_time"])
            self.lcms_device.set_valve_pos(self.param_config["sample_loading_position"])
            self.log_info("SUCCESS - Switch Valve - Sample Loaded From Sample Loop")

            # Wait for the sample loop to be flushed through
            time.sleep(self.param_config["sample_loop_fill_time"] * 4)
            self.lcms_device.set_valve_pos(self.param_config["sample_filling_position"])
            self.log_info("SUCCESS - Switch Valve - Returned To Filling Position")

            # Report triggering success
            self.log_info("SUCCESS - Analysis Cycle Triggering Complete")
            return "SUCCESS - Analysis Cycle Triggering Complete"

        except Exception as error:
            self.log_info(error)
            return f"FAILED - Analysis Cycle Failed due to: {error}"

    # ----- Analysis Method END -----
    # ----- Compound Command Methods START -----
    def _check_device_connectivity(self):
        """ Checks the Arduino microcontroller, switch valve, phase sensor, and LCMS are connected """

        # Check the arduino receives and sends data
        id_ack = self.lcms_device.get_id()
        if id_ack is None:
            self.log_info("Error Communicating with the Arduino")
            raise "Error Communicating with the Arduino"

        # Check the switch valve is connected and in a valid state
        valve_pos_ack = self.lcms_device.read_valve_pos()
        if valve_pos_ack not in ['A', 'B']:
            self.log_info("Error Communicating with the Switch Valve")
            raise "Error Communicating with the Switch Valve"

        # Check the phase sensor reads a valid value
        ps_ack = self.lcms_device.read_phase_sensor()
        if ps_ack not in ['0', '1', '2']:
            self.log_info("Error Communicating with the Phase Sensor")
            raise "Error Communicating with the Phase Sensor"

        # TODO add LCMS Check. Unfortunately the ERI lines are pulled not held

    def _check_valve_state(self):
        """Checks the switch valve is in the filling state"""

        # Check valve in filling pos. If not then switch
        if self.lcms_device.read_valve_pos() != self.param_config["sample_filling_position"]:
            self.lcms_device.set_valve_pos(self.param_config["sample_filling_position"])
            time.sleep(self.param_config["valve_switching_time"] * 2)  # give time to change switch positions

        # Re-check valve in filling pos. If not
        if self.lcms_device.read_valve_pos() != self.param_config["sample_filling_position"]:
            self.log_info("ERROR - Switch Valve - Valve Not Set")
            raise Exception("ERROR - Switch Valve - Valve Not Set")

        # Wait to fill loop
        time.sleep(self.param_config["sample_loop_fill_time"] * 3)

        # Check for sample at sensor
        if not self.lcms_device.get_sample_at_sensor():
            self.log_info("ERROR - Phase Sensor - No Sample Detected After Filling")
            raise Exception("ERROR - Phase Sensor - No Sample Detected After Filling")

    def _send_start_request_wth_error(self):
        ack = self.lcms_device.send_start_request()
        if ack != self.lcms_device.standard_acknowledge:
            self.log_info("ERROR - LCMS - Start Signal Not Sent by Arduino")
            raise Exception("ERROR - LCMS - Start Signal Not Sent by Arduino")

    def _wait_on_lcms_response(self):
        ready_state = '0'
        timeout = self.param_config["lcms_response_timeout"]
        start_time = time.time()
        while ready_state != '1':
            ready_state = self.lcms_device.check_lcms_ready()
            time.sleep(0.1)
            if time.time() - start_time > timeout:
                raise Exception("ERROR - LCMS - No Acknowledgement From Spectrometer Within Timeout")

    # ----- Compound Command Methods START -----
    # ----- Simple Command Methods START -----

    def get_device_id(self):
        return self.lcms_device.get_id()

    def set_device_id(self, new_id):
        ack = self.lcms_device.set_id(new_id)
        return self.get_device_id() if ack == 'k' else None

    def _device_factory_reset(self):
        self.lcms_device.factory_reset()

    def get_valve_pos(self):
        return self.lcms_device.read_valve_pos()

    def set_valve_pos(self, pos):
        ack = self.lcms_device.set_valve_pos(pos)
        return self.get_valve_pos() if ack == 'k' else None

    def send_start_request(self):
        ack = self.lcms_device.send_start_request()
        return "Good Acknowledge" if ack == 'k' else "Bad Acknowledge"

    def send_stop_signal(self):
        ack = self.lcms_device.send_stop_signal()
        return "Good Acknowledge" if ack == 'k' else "Bad Acknowledge"

    def get_ready_signal(self):
        ack = self.lcms_device.check_lcms_ready()
        return ack

    def calibrate_phase_sensor(self):
        self.lcms_device.calibrate_phase_sensor()

    def read_phase_sensor(self):
        return self.lcms_device.read_phase_sensor()

    def stop_analysis(self):
        self.lcms_device.send_stop_signal()
        self.log_info("Analysis Stopped")

    def close(self):
        """ Closes the serial connection to the Arduino Device """
        self.lcms_device.close()

    # ----- Simple Command Methods END -----
    # -----Util Methods START-----
    def log_info(self, message):
        if self.log_queue:
            self.log_queue.put(message)

    @staticmethod
    def split_command(cmd) -> tuple:
        """
        Takes commands from the user and splits the prefix (everything BEFORE the first '-')
        and argument (everything AFTER the first '-'). This allows the user to specify both
        the desire command and provide data for the command. Commands in the form "5-a" will be
        split as prefix="5" and argument="a"
        """
        cmd_parts = cmd.strip().split('-', 1)  # Split at first instance to ensure only 2 parts
        argument = ""
        if len(cmd_parts) > 1:
            prefix, argument = cmd_parts[0].strip(), cmd_parts[1].strip()
        else:
            prefix = cmd_parts[0].strip()
        return prefix, argument

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
