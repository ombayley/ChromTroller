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

    def __init__(self, port='COM3', baud_rate=9600, timeout=1):
        self.controller = LCMSDevice(port, baud_rate, timeout)
        self.sample_filling_position = 'A'  # 0 = Position A
        self.sample_loading_position = 'B'  # 1 = Position B
        self.loop_fill_time = 3
        self.lcms_sample_prep_time = 10
        self.switching_time = 0.5
        self.start_ps_monitor()

    def process_command(self, cmd):
        """
        Triggers the correct methods corresponding to the received inputs. Numerical cases
        (e.g., 1-10) are dedicated to individual method testing, written commands (e.g.,'Analyse')
        are used to perform complex tasks.
        Args:
            cmd (str): Command received from the user/client
        Return:
            response (str): Returns either the requested info or in the case of commands returns
            a simple acknowledgement.
        """
        # TODO. Tidy up the returns and acknowledgements.
        # TODO Add a logger that works with the server and direct execution
        # TODO refine function to be shorter
        prefix, argument = self.split_command(cmd)
        match prefix:
            case '1':
                device_id = self.controller.get_id()
                print(device_id)
                return device_id
            case '2':
                ack = self.controller.set_id(argument)
                response = ("Good Acknowledge" if ack == 'k' else "Bad Acknowledge")
                print(response)
                return response
            case '3':
                self.controller.factory_reset()
                print('k')
                return 'k'
            case '4':
                pos = self.controller.read_valve_pos()
                print(pos)
                return pos
            case '5':
                ack = self.controller.set_valve_pos(argument)
                print(ack)
                response = ("Good Acknowledge" if ack == 'k' else "Bad Acknowledge")
                print(response)
                return response
            case '6':
                ack = self.controller.start_analysis()
                response = ("Good Acknowledge" if ack == 'k' else "Bad Acknowledge")
                print(response)
                return response
            case '7':
                ack = self.controller.stop_analysis()
                response = ("Good Acknowledge" if ack == 'k' else "Bad Acknowledge")
                print(response)
                return response
            case '8':
                self.controller.check_lcms_ready()
                return 'k'
            case '9':
                self.controller.calibrate_phase_sensor()
                return 'k'
            case '10':
                ps_val = self.controller.read_phase_sensor()
                print(ps_val)
                return ps_val
            case 'Analyse':
                try:
                    self.run_analysis_cycle()
                    return 'Success'
                except Exception as e:
                    print(e)

    def start_ps_monitor(self):
        """
        Starts a new thread to monitor the data from the phase sensor using the SensorMonitor object
        """
        sensor_monitor = SensorMonitor(self.controller)
        threading.Thread(target=sensor_monitor.monitor_loop).start()

    @staticmethod
    def split_command(cmd) -> tuple:
        """
        Takes commands from the user and splits the prefix (everything BEFORE the first '-')
        and argument (everything AFTER the first '-'). This allows the user to specify both
        the desire command and provide data for the command.
        Args:
            cmd (string): The command given by the user
        Return:
            prefix (string): The command name/number
            argument (string): Any info to be used in the command
        """
        cmd_parts = cmd.strip().split('-', 1)  # Split at first instance to ensure only 2 parts
        argument = ""
        if len(cmd_parts) > 1:
            prefix, argument = cmd_parts[0].strip(), cmd_parts[1].strip()
        else:
            prefix = cmd_parts[0].strip()
        return prefix, argument

    def run_analysis_cycle(self):
        """
        Runs the routine start an analytical run. This involves external loading and triggering
        """
        # TODO make function clearer
        # TODO include check to see if system is ready. Currently assumes all analyse commands come once ready
        print("Analysis initiated...")
        # TODO add a check here to ensure everything is connected correctly
        # Holds analysis until the phase sensor detects a sample
        self.controller.wait_for_phase_sensor()
        print("SUCCESS - Phase Sensor - Sample Detected")

        # Ensure that the switch is in the filling position and if not, switch and fill.
        if self.controller.read_valve_pos() != self.sample_filling_position:
            self.controller.set_valve_pos(self.sample_filling_position)
            time.sleep(self.switching_time*2)  # give time to change switch positions
            if self.controller.read_valve_pos() != self.sample_filling_position:
                raise Exception("ERROR - Switch Valve - Valve Not Set")
            time.sleep(self.loop_fill_time)
            if not self.controller.get_sample_at_sensor():
                raise Exception("ERROR - Phase Sensor - No Sample Detected After Filling")
        print("SUCCESS - Switch Valve - Filling Loop Filled")

        # Check LCMS is ready to ensure start trigger will start analysis
        # TODO find a way to have the LCMS tate show as ready while waiting

        # Send start analysis and check acknowledgement.
        ack = self.controller.start_analysis()
        if ack != self.controller.standard_acknowledge:
            raise Exception("ERROR - LCMS - Start Signal Not Sent by Arduino")
        print("SUCCESS - LCMS - Start Signal Sent By Arduino")

        # Check acknowledgement from spectrometer (LCMS method must include this!)
        ready_state = '0'
        timeout = 240  # 4min timeout
        start_time = time.time()
        while ready_state != '1':
            ready_state = self.controller.check_lcms_ready()
            time.sleep(0.1)
            if time.time() - start_time > timeout:
                raise Exception("ERROR - LCMS - No Acknowledgement From Spectrometer Within Timeout")

        print("SUCCESS - LCMS - Start Acknowledged By Spectrometer")

        # Wait a set time to allow LCMS sample handling, then load from the switch valve.
        time.sleep(self.lcms_sample_prep_time)
        self.controller.set_valve_pos(self.sample_loading_position)
        print("SUCCESS - Switch Valve - Sample Loaded From Sample Loop")
        time.sleep(self.loop_fill_time * 2)
        self.controller.set_valve_pos(self.sample_filling_position)
        print("SUCCESS - Switch Valve - Returned To Filling Position")

    def close(self):
        """ Closes the serial connection to the Arduino Device """
        self.controller.close()

    def controller_user_loop(self):
        """ Acts as a simple user interface if the script needs to be run directly """
        try:
            while True:
                cmd = input("Enter command to send to Arduino: ")
                self.process_command(cmd)
        except KeyboardInterrupt:
            print("\nTest terminated by user.")
        finally:
            self.controller.close()
            print("Serial connection closed.")


class SensorMonitor:
    """
    Monitors phase sensor data. Gets the current data, checks if the current reading is different to the previous.
    If it differs, it flags the change else updates the last read data and repeats the loop. If a change was
    detected, the second loop checks that the change is stable for a set amount of time.
    """

    def __init__(self, controller):
        self.controller = controller

        # Must be set according to user and platform requirements
        self.polling_frequency = 0.1
        self.stability_time = 1
        self.empty_sensor_val = '1'
        self.full_sensor_vals = ['0', '2']
        # general variables
        self.prev_stable_val = None
        self.last_ps_val = None
        self.stable_change_detected = False
        self.change_time = None
        self.prev_stable_val = self.controller.read_phase_sensor()
        self.last_ps_val = self.prev_stable_val

    def monitor_loop(self):
        """
        Central monitoring loop. Starts by reading data, checks for stable changes, updates previous
        run data and then sleeps.
        """
        while True:
            curr_ps_val = self.controller.read_phase_sensor()

            # check stability first, otherwise the current and previous runs must be different.
            if self.stable_change_detected:
                self.check_change_stability(curr_ps_val)

            self.check_ps_change(curr_ps_val)

            self.last_ps_val = curr_ps_val
            time.sleep(self.polling_frequency)

    def check_ps_change(self, curr_ps_val):
        """Checks whether the new reading differs from the previous reading and the previous stable reading """
        if curr_ps_val != self.last_ps_val and curr_ps_val != self.prev_stable_val:
            self.change_time = time.time()
            self.stable_change_detected = True

    def check_change_stability(self, curr_ps_val):
        """checks that the new value is consistant"""
        if curr_ps_val == self.last_ps_val:
            if (time.time() - self.change_time) >= self.stability_time:
                self.act_on_stable_read(curr_ps_val)
        else:
            self.stable_change_detected = False

    def act_on_stable_read(self, new_stable_value):
        """Actions to perform if the new value is stable"""
        if new_stable_value == self.empty_sensor_val:
            self.controller.set_phase_sensor_value(False)
        elif new_stable_value in self.full_sensor_vals:
            self.controller.set_phase_sensor_value(True)
        self.prev_stable_val = new_stable_value
        self.stable_change_detected = False


if __name__ == "__main__":
    device_controller = Controller(port='COM3')
    device_controller.controller_user_loop()
