#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import datetime
import threading
from ct_components.devices.lcms_device import LCMSDevice


def monitor_ouput_signals(device):
    last_ready_read = '0'
    last_power_read = '0'
    last_start_read = '0'
    state = device.get_lcms_ready()
    print(f"starting ready state: {state}")
    print(f"starting power state: {device.get_lcms_power()}")
    print(f"starting start state: {device.get_lcms_start()}")

    while True:
        ready = device.get_lcms_ready()
        power = device.get_lcms_power()
        start = device.get_lcms_start()

        if ready == '1' and last_ready_read == '0':
            print("READY line Activated")
            last_ready_read = '1'
        if power == '1' and last_power_read == '0':
            print("POWER line Activated")
            last_power_read = '1'
        if start == '1' and last_start_read == '0':
            print("START line Activated")
            last_start_read = '1'

        if ready == '0' and last_ready_read == '1':
            print("READY line De-activated")
            last_ready_read = '0'
        if power == '0' and last_power_read == '1':
            print("POWER line De-activated")
            last_power_read = '0'
        if start == '0' and last_start_read == '1':
            print("START line De-activated")
            last_start_read = '0'


def send_start_request(device):
    while True:
        user_in = input("Send Start Signal (y/n)?")
        if user_in == 'y':
            print("START REQUEST - Sent")
            device.send_start_request()


def get_current_state(device):
    while True:
        user_in = input("state (a) or start_req (b) ?")
        if user_in == 'a':
            start_request = device.get_lcms_start()
            stop = device.get_lcms_stop()
            ready = device.get_lcms_ready()
            power = device.get_lcms_power()
            start = device.get_lcms_start()
            prepare = device.get_lcms_prepare()

            print(f"start_request: {start_request}")
            print(f"stop: {stop}")
            print(f"ready: {ready}")
            print(f"power: {power}")
            print(f"start: {start}")
            print(f"prepare: {prepare}")
        if user_in == 'b':
            print("START REQUEST - Sent")
            device.send_start_request()

if __name__ == "__main__":
    device = LCMSDevice(port='COM5')
    get_current_state(device)
    # threading.Thread(target=monitor_ouput_signals, args=(device,)).start()
    # send_start_request(device)
