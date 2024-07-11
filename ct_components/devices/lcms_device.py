#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: Adds functionality to the inherited ArduinoDevice class to give the task specific
capabilities required to operate the LCMS Platform. Functions are thread locked to allow
multi-threading. Note: the functions here may be specific but are still 'dumb'.
e.g., set valve does not then read the position to compare success (this should be handled
by the program using this object).

TODO implement a command table to match the arduino commands with the commands here!
"""
from threading import Lock, Event
from ct_components.devices.base_arduino_device import ArduinoDevice


class LCMSDevice(ArduinoDevice):
    """Class defining the specific tasks the LCMS control unit/Arduino is capable of"""
    def __init__(self, port='COM3', baud_rate=9600, timeout=1):
        super().__init__(port, baud_rate, timeout)
        self.open_connection()
        self.lock = Lock()
        self.load_detection_event = Event()
        self._phase_sensor_detects = False
        self.standard_acknowledge = 'k'

    def get_id(self) -> str:
        """Requests the device ID from the Arduino and returns the output"""
        with self.lock:
            self.send_command("r1")
            res = self.read_response()
            return res

    def set_id(self, name) -> str:
        """Sets a new device ID for the Arduino and returns the standard acknowledge"""
        with self.lock:
            self.send_command("s1=" + name)
            res = self.read_response()
            return res

    def factory_reset(self) -> str:
        """Reset the Arduino and return the standard acknowledge"""
        with self.lock:
            self.send_command("s4")
            return self.read_response()

    def get_valve_pos(self) -> str:
        """Requests the vale position from the Arduino and returns the current position"""
        with self.lock:
            self.send_command("r5")
            pos = self.read_response()
            if pos not in ['0', '1']:
                return "Valve Position Error"
            return "A" if pos == '0' else "B"

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
            self.send_command(f"s5={cmd_position}")
            response = self.read_response()
            return response

    def send_start_request(self) -> str:
        """
        Ask Arduino to send 'START REQUEST' to the LCMS insrument. Returns Arduino
        acknowledgement !NOT! LCMS acknowledgement.
        """
        with self.lock:
            self.send_command("s6")
            return self.read_response()

    def send_stop_signal(self) -> str:
        """
        Ask Arduino to send 'STOP' to the LCMS instrument. Returns Arduino
        acknowledgement !NOT! LCMS acknowledgement.
        """
        with self.lock:
            self.send_command("s7")
            return self.read_response()

    def check_lcms_ready(self) -> str:
        """Requests the LCMS 'READY' signal state from the Arduino"""
        with self.lock:
            self.send_command("r8")
            return self.read_response()

    def calibrate_phase_sensor(self) -> str:
        """Requests the phase sensor to be calibrated. Returns the standard acknowledge"""
        with self.lock:
            self.send_command("s9")
            return self.read_response()

    def read_phase_sensor(self) -> str:
        """Requests the phase sensor signal from the Arduino"""
        with self.lock:
            self.send_command("r10")
            return self.read_response()

    def get_power_sate(self) -> str:
        """Requests the LCMS 'POWER' signal state from the Arduino"""
        with self.lock:
            self.send_command("r11")
            return self.read_response()

    def get_start_signal(self) -> str:
        with self.lock:
            self.send_command("r12")
            return self.read_response()

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
        self.load_detection_event.wait()
