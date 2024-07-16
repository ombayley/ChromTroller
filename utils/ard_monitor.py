#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import datetime
import threading
import time
from ct_components.devices.lcms_device import LCMSDevice


def monitor_ouput_signals(device):
    last_ready_read = '0'
    last_power_read = '0'
    last_start_read = '0'
    last_request_read = '0'
    print(f"starting ready state: {device.get_lcms_ready()}")
    print(f"starting power state: {device.get_lcms_power()}")
    print(f"starting start state: {device.get_lcms_start()}")
    print(f"starting request state: {device.get_lcms_start_request()}")

    while True:
        ready = device.get_lcms_ready()
        power = device.get_lcms_power()
        start = device.get_lcms_start()
        request = device.get_lcms_start_request()

        # if ready == '1' and last_ready_read == '0':
        #     print("READY line Activated")
        #     last_ready_read = '1'
        if power == '1' and last_power_read == '0':
            print("POWER line Activated")
            last_power_read = '1'
        if start == '1' and last_start_read == '0':
            print("START line Activated")
            last_start_read = '1'
        if request == '1' and last_request_read == '0':
            print("REQUEST line Activated")
            last_request_read = '1'

        # if ready == '0' and last_ready_read == '1':
        #     print("READY line De-activated")
        #     last_ready_read = '0'
        if power == '0' and last_power_read == '1':
            print("POWER line De-activated")
            last_power_read = '0'
        if start == '0' and last_start_read == '1':
            print("START line De-activated")
            last_start_read = '0'
        if request == '0' and last_request_read == '1':
            print("REQUEST line De-activated")
            last_request_read = '0'


def send_start_request(device):
    while True:
        user_in = input("Send Start Signal (y/n)?")
        if user_in == 'y':
            print("START REQUEST - Sent")
            device.send_start_request()


def get_current_state(device):
    while True:
        user_in = input("state (1-6) or start_req (b) ?")
        if user_in == '1':
            start_request = device.get_lcms_start()
            print(f"start_request: {start_request}")
        if user_in == '2':
            stop = device.get_lcms_stop()
            print(f"stop: {stop}")
        if user_in == '3':
            ready = device.get_lcms_ready()
            print(f"ready: {ready}")
        if user_in == '4':
            power = device.get_lcms_power()
            print(f"power: {power}")
        if user_in == '5':
            start = device.get_lcms_start()
            print(f"start: {start}")
        if user_in == '6':
            prepare = device.get_lcms_prepare()
            print(f"prepare: {prepare}")

        if user_in == 'a':
            start_request = device.get_lcms_start()
            print(f"start_request: {start_request}")
            stop = device.get_lcms_stop()
            print(f"stop: {stop}")
            # time.sleep(0.01)
            ready = device.get_lcms_ready()
            print(f"ready: {ready}")
            power = device.get_lcms_power()
            print(f"power: {power}")
            start = device.get_lcms_start()
            print(f"start: {start}")
            prepare = device.get_lcms_prepare()
            print(f"prepare: {prepare}")

        if user_in == 'b':
            print("START REQUEST - Sent")
            device.send_start_request()

if __name__ == "__main__":
    device = LCMSDevice(port='COM5')
    # get_current_state(device)
    threading.Thread(target=monitor_ouput_signals, args=(device,)).start()
    send_start_request(device)
