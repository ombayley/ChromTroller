#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: Dummy Class to mimic the Ardunio without the need for hardware

"""
from threading import Lock, Event


class LCMSDevice:
    """Class defining the specific tasks the LCMS control unit/Arduino is capable of"""
    def __init__(self, port='COM3', baud_rate=9600, timeout=1):
        self.lock = Lock()
        self.load_detection_event = Event()
        self._phase_sensor_detects = True
        self.standard_acknowledge = 'k'
        self.dummy_valve_position = 'A'

    def get_id(self) -> str:
        """Requests the device ID from the Arduino and returns the output"""
        with self.lock:
            return 'dummy id'

    def set_id(self, name) -> str:
        """Sets a new device ID for the Arduino and returns the standard acknowledge"""
        with self.lock:
            return f'call to set dummy id to: {name}'

    def factory_reset(self) -> str:
        """Reset the Arduino and return the standard acknowledge"""
        with self.lock:
            return 'factory reset called'

    def get_valve_pos(self) -> str:
        """Requests the vale position from the Arduino and returns the current position"""
        with self.lock:
            return self.dummy_valve_position

    def set_valve_pos(self, position) -> str:
        """
        Sets new valve position and returns the acknowledgement from the Arduino.
        Accepts 0/1, a/b and A/B as valid arguments improve user-friendliness.
        """
        with self.lock:
            position_map = {0: "0", 'a': "0", 'A': "0", 1: "1", 'b': "1", 'B': "1"}
            cmd_position = position_map.get(position)
            if cmd_position is None:
                return "Invalid position"
            self.dummy_valve_position = position
            return 'k'

    def send_start_request(self) -> str:
        """
        Ask Arduino to send 'START REQUEST' to the LCMS insrument. Returns Arduino
        acknowledgement !NOT! LCMS acknowledgement.
        """
        with self.lock:
            return 'k'

    def send_stop_signal(self) -> str:
        """
        Ask Arduino to send 'STOP' to the LCMS instrument. Returns Arduino
        acknowledgement !NOT! LCMS acknowledgement.
        """
        with self.lock:
            return 'k'

    def check_lcms_ready(self) -> str:
        """Requests the LCMS 'READY' signal state from the Arduino"""
        with self.lock:
            return '1'

    def calibrate_phase_sensor(self) -> str:
        """Requests the phase sensor to be calibrated. Returns the standard acknowledge"""
        with self.lock:
            return 'k'

    def get_power_sate(self) -> str:
        """Requests the LCMS 'POWER' signal state from the Arduino"""
        with self.lock:
            return '1'

    def get_start_signal(self) -> str:
        """Requests the LCMS 'POWER' signal state from the Arduino"""
        with self.lock:
            return '1'

    def read_phase_sensor(self) -> str:
        """Requests the phase sensor signal from the Arduino"""
        with self.lock:
            return '0'

    def set_phase_sensor_value(self, status: bool):
        """sets the phase sensor reading in a threadsafe manner"""
        with self.lock:
            self._phase_sensor_detects = status
            if status:
                self.load_detection_event.set()
            else:
                self.load_detection_event.clear()

    def get_sample_at_sensor(self) -> bool:
        """reads the phase sensor reading in a threadsafe manner"""
        with self.lock:
            return self._phase_sensor_detects

    def wait_for_phase_sensor(self):
        """Block until the loaded property is True."""
        # self.load_detection_event.wait()
