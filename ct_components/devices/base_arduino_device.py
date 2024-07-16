#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: An agnostic base class for communication with an Arduino Device, containing the essentials
of serial communication. No task-specific methods are included. i.e. it contains generic open, send,
close, etc.. methods but no 'switch valve', 'start analysis', 'check sensor', etc... methods.
"""
import time
import copy
from threading import Lock
import serial


class ArduinoDevice:
    """Class defining the basic operations required for serial communication with the Arduino."""

    def __init__(self, port='COM3', baud_rate=9600, timeout=1):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.connection = None
        self.lock = Lock()

    def open_connection(self):
        """Open a serial connection on the port specified during init"""
        try:
            self.connection = (serial.Serial(self.port, self.baud_rate, timeout=self.timeout))
        except Exception as serrial_error:
            raise Exception(f"Failed to open serial connection: {serrial_error}")

    #serial.SerialException
    def is_connected(self) -> bool:
        """Check whether the connection is open. Thread lock included to allow multi-threading"""
        # with self.lock:
        return self.connection.is_open

    def send_command(self, cmd):
        """Send a command to the Arduino. Thread lock included to allow multi-threading"""
        # with self.lock:
        self.connection.reset_input_buffer()
        self.connection.write(f"{cmd}\n".encode())

    def read_response(self) -> str:
        """Read response from Arduino. Thread lock included to allow multi-threading"""
        # with self.lock:
        timeout = copy.deepcopy(self.timeout)
        reply = ""
        while reply == "" and timeout > 0.0:
            time.sleep(0.01)
            timeout -= 0.01
            reply = self.connection.readline().decode().strip()
        if timeout < 0.0:
            print("serial response timeout reached")

        return reply

    def close(self):
        """Close the serial connection."""
        self.connection.close()
