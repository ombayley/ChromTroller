#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: Controls the behavior of the LCMS and switching system allowing it to read data
and trigger complex behaviours.
"""
import os
import threading
import time
import logging
import json
from devices.lcms_device import LCMSDevice


def get_instrument_config_parameters() -> dict:
    """
    Function returns a dictionary containing all hardware dependant variable values.
    TODO move PS to before valve, make stability time longer and add timer to ensure loading
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


class Controller:
    """
    Initalise controller object.
    Args:
        port (str): The port to connect to the Arduino device. Defaults to 'COM3'
        baud_rate (float): Baud rate for serial communication. Defaults to '9600'
        timeout (float): max block time (in seconds) for the serial read(). Defaults to '1'
    """

    def __init__(self, port='COM3', baud_rate=9600, timeout=1):
        self.lcms_device = LCMSDevice(port, baud_rate, timeout)
        self.param_config = get_instrument_config_parameters()
        self.start_ps_monitor()
        self.completed_analysis_cycle = 0
        logging.info("Controller Object Initialized Successfully")

    def process_command(self, cmd):
        """
        Triggers the correct methods corresponding to the received inputs. Numerical cases
        (e.g., 1-10) are dedicated to individual method testing, written commands (e.g.,'Analyse')
        are designed for interaction tasks with the RoboChem systems.
        """
        prefix, argument = self.split_command(cmd)
        match prefix:
            case '1':
                return self.lcms_device.get_id()
            case '2':
                ack = self.lcms_device.set_id(argument)
                return "Good Acknowledge" if ack == 'k' else "Bad Acknowledge"
            case '3':
                self.lcms_device.factory_reset()
                return 'k'
            case '4':
                return self.lcms_device.read_valve_pos()
            case '5':
                ack = self.lcms_device.set_valve_pos(argument)
                return "Good Acknowledge" if ack == 'k' else "Bad Acknowledge"
            case '6':
                ack = self.lcms_device.start_analysis()
                return "Good Acknowledge" if ack == 'k' else "Bad Acknowledge"
            case '7':
                ack = self.lcms_device.stop_analysis()
                return "Good Acknowledge" if ack == 'k' else "Bad Acknowledge"
            case '8':
                ack = self.lcms_device.check_lcms_ready()
                return ack
            case '9':
                self.lcms_device.calibrate_phase_sensor()
                return 'k'  # TODO check this dosen't return anything
            case '10':
                return self.lcms_device.read_phase_sensor()
            # --- Text-based commands ---
            case 'Reset_Sample_Counter':
                self.completed_analysis_cycle = 0
                return 'Sample counter returned to 0'
            case 'Reset_run_log':
                self.clear_run_log()
                return 'Sample counter returned to 0'
            case 'Analyse':
                try:
                    analysis_outcome = self.run_analysis_cycle()
                    return analysis_outcome
                except Exception as e:
                    logging.error(e)
            case 'Data':
                self.add_to_run_log(argument)
                return 'Data Logged'
            case 'Stop':
                self.stop_analysis()
                return 'Analysis Completed'

    def start_ps_monitor(self):
        """
        Starts a new thread to monitor the data from the phase sensor using the SensorMonitor object
        """
        sensor_monitor = SensorMonitor(self.lcms_device, self.param_config)
        threading.Thread(target=sensor_monitor.monitor_loop).start()
        logging.info("Phase sensor monitoring started on separate thread.")

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

    def stop_analysis(self):
        self.lcms_device.stop_analysis()
        logging.info("Analysis Stopped")

    def add_to_run_log(self, argument, path=None):

        if path is None:
            # Sets the default path to the 'logs' directory.
            current_dir_path = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(current_dir_path, 'logs', 'run_data_log')
            logging.info(f"add to log called with {argument}")

        # Check if the file exists
        if os.path.exists(path):
            # Load existing JSON data from file
            with open(path, 'r') as file:
                existing_data = json.load(file)
        else:
            # If the file doesn't exist, create an empty dictionary
            existing_data = []

        new_data = {'Analysis cycle': self.completed_analysis_cycle,
                    'RoboChem Run Info': argument
                    }

        # Append new data to existing data
        existing_data.append(new_data)
        logging.info(f"adding data: {existing_data}")
        # Write the updated data back to the JSON file
        with open(path, 'w') as file:
            json.dump(existing_data, file, indent=4)

    @staticmethod
    def clear_run_log(path=None):
        if path is None:
            # Sets the default path to the 'logs' directory.
            current_dir_path = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(current_dir_path, 'logs', 'run_data_log')
            logging.info(f"run log cleared")

            if os.path.exists(path):
                # Load existing JSON data from file
                with open(path, 'w') as file:
                    existing_data = []
                    json.dump(existing_data, file, indent=4)

    # ---------- Analysis Run START ----------
    def run_analysis_cycle(self) -> str:
        """
        Runs the routine to start an analytical run.
        This involves the detection, sample loading and lcms method triggering
        """
        logging.info("Analysis Process Initiated...")
        try:
            # Check devices are connected and in valid states. Raise error if not
            self.check_device_connectivity()
            logging.info("SUCCESS - Hardware Connections Verified")

            # Ensure phase sensor sees sample. Wait if not there
            self.lcms_device.wait_for_phase_sensor()
            logging.info("SUCCESS - Phase Sensor - Sample Detected")

            # Ensure that the switch is in the filling position and if not, switch and fill.
            self.check_valve_state()
            logging.info("SUCCESS - Switch Valve - Filling Loop Filled")

            # Send start analysis and check acknowledgement.
            self.start_lcms_method()
            logging.info("SUCCESS - LCMS - Start Signal Sent By Arduino")

            # Check acknowledgement from spectrometer (LCMS method must include this!)
            self.wait_on_lcms_response()
            logging.info("SUCCESS - LCMS - Start Acknowledged By Spectrometer")

            # Wait a set time to allow LCMS sample handling, then load from the switch valve.
            time.sleep(self.param_config["lcms_sample_prep_time"])
            self.lcms_device.set_valve_pos(self.param_config["sample_loading_position"])
            logging.info("SUCCESS - Switch Valve - Sample Loaded From Sample Loop")

            # Wait for the sample loop to be flushed through
            time.sleep(self.param_config["sample_loop_fill_time"] * 4)
            self.lcms_device.set_valve_pos(self.param_config["sample_filling_position"])
            logging.info("SUCCESS - Switch Valve - Returned To Filling Position")

            # Report success and the analysis cycle number
            self.completed_analysis_cycle += 1
            logging.info("SUCCESS - Analysis Cycle: %s Complete", self.completed_analysis_cycle)

            return f"SUCCESS - Analysis Cycle: {self.completed_analysis_cycle} Complete"

        except Exception as error:
            logging.error(error)
            return f"FAILED - Analysis Cycle Failed due to: {error}"

    # ---------- Analysis Run END ----------

    def check_device_connectivity(self):
        """ Checks the Arduino microcontroller, switch valve, phase sensor, and LCMS are connected """

        # Check the arduino receives and sends data
        id_ack = self.lcms_device.get_id()
        if id_ack is None:
            logging.error("Error Communicating with the Arduino")
            raise "Error Communicating with the Arduino"
        # Check the switch valve is connected and in a valid state
        valve_pos_ack = self.lcms_device.read_valve_pos()
        if valve_pos_ack not in ['A', 'B']:
            logging.error("Error Communicating with the Switch Valve")
            raise "Error Communicating with the Switch Valve"
        # Check the phase sensor reads a valid value
        ps_ack = self.lcms_device.read_phase_sensor()
        if ps_ack not in ['0', '1', '2']:
            logging.error("Error Communicating with the Phase Sensor")
            raise "Error Communicating with the Phase Sensor"

        # TODO find a way to have the LCMS tate show as ready while waiting - Can use a Wait time for now

    def check_valve_state(self):
        """Checks the switch valve is in the filling state"""
        if self.lcms_device.read_valve_pos() != self.param_config["sample_filling_position"]:
            self.lcms_device.set_valve_pos(self.param_config["sample_filling_position"])
            time.sleep(self.param_config["valve_switching_time"] * 2)  # give time to change switch positions
            if self.lcms_device.read_valve_pos() != self.param_config["sample_filling_position"]:
                logging.error("ERROR - Switch Valve - Valve Not Set")
                raise Exception("ERROR - Switch Valve - Valve Not Set")
            time.sleep(self.param_config["sample_loop_fill_time"])
            if not self.lcms_device.get_sample_at_sensor():
                logging.error("ERROR - Phase Sensor - No Sample Detected After Filling")
                raise Exception("ERROR - Phase Sensor - No Sample Detected After Filling")

    def start_lcms_method(self):
        ack = self.lcms_device.start_analysis()
        if ack != self.lcms_device.standard_acknowledge:
            logging.error("ERROR - LCMS - Start Signal Not Sent by Arduino")
            raise Exception("ERROR - LCMS - Start Signal Not Sent by Arduino")

    def wait_on_lcms_response(self):
        ready_state = '0'
        timeout = self.param_config["lcms_response_timeout"]
        start_time = time.time()
        while ready_state != '1':
            ready_state = self.lcms_device.check_lcms_ready()
            time.sleep(0.1)
            if time.time() - start_time > timeout:
                raise Exception("ERROR - LCMS - No Acknowledgement From Spectrometer Within Timeout")

    # ---------- Analysis Run END ----------

    def close(self):
        """ Closes the serial connection to the Arduino Device """
        self.lcms_device.close()

    def controller_user_loop(self):
        """ Acts as a simple user interface if the script needs to be run directly for debugging"""
        try:
            while True:
                cmd = input("Enter command to send to Arduino: ")
                self.process_command(cmd)
        except KeyboardInterrupt:
            print("\nTest terminated by user.")
        finally:
            self.lcms_device.close()
            print("Serial connection closed.")


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
        logging.info("SensorMonitor Initialized Successfully")

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


if __name__ == "__main__":
    device_controller = Controller(port='COM3')
    device_controller.controller_user_loop()
