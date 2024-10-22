#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
from ct_components.devices.lcms_device import LCMSDevice
import logging
import os
import json
from datetime import datetime


class StandaloneController:

    def __init__(self):
        # Setup Logging
        self._setup_logging()
        # Get hardware and timing settings
        self.hardware_settings = self.get_hardware_settings()
        # Create LCMSDevice object
        self.lcms_device = self.init_device()
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

    @staticmethod
    def _setup_logging():
        """ Sets log format and file destination """
        # Set path to the 'log_files' directory.
        root_dir_path = os.path.dirname(os.path.abspath(__file__))
        log_dir_path = os.path.join(root_dir_path, '../log_files')

        # Ensure the log_files directory exists
        os.makedirs(log_dir_path, exist_ok=True)

        # Set the log file name
        date_str = datetime.now().strftime("%d-%m-%Y--%H-%M-%S")
        log_file_name = f"ChromTroller_{date_str}_logfile.log"
        log_file_path = os.path.join(log_dir_path, log_file_name)

        # Set up logging configuration
        logging.basicConfig(
            filename=log_file_path,
            level=logging.INFO,
            format=f'%(asctime)s - %(levelname)s - %(filename)s - %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S',
            filemode='w'  # w=write, a=append
        )

    def init_device(self):
        """
        Create the Device object
        """
        port = self.hardware_settings["serial_port"]
        baud_rate = self.hardware_settings["serial_baud_rate"]
        timeout = self.hardware_settings["serial_timeout"]
        return LCMSDevice(port, baud_rate, timeout)

    # ----- Simple Command Methods START -----
    def get_device_id(self):
        return self.lcms_device.get_id()

    def set_device_id(self, new_id):
        ack = self.lcms_device.set_id(new_id)
        return self.get_device_id() if ack == 'k' else None

    def _device_factory_reset(self):
        self.lcms_device.factory_reset()

    def get_valve_pos(self):
        return self.lcms_device.get_valve_pos()

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

    def close(self):
        """ Closes the serial connection to the Arduino Device """
        self.lcms_device.close()

    # ----- Simple Command Methods END -----


if __name__ == "__main__":
    controller = StandaloneController()
    print(controller.get_device_id())
    controller.set_valve_pos("A")
