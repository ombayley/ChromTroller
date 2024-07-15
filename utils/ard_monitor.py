#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import time
from ct_components.devices.lcms_device import LCMSDevice


def monitor_ouput_signals(device):
    last_ready_read = '0'
    last_power_read = '0'
    last_start_read = '0'
    while True:
        ready = device.check_lcms_ready()
        power = device.check_lcms_power()
        start = device.check_lcms_start()

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
            last_ready_read = '1'
        if power == '0' and last_power_read == '1':
            print("POWER line De-activated")
            last_power_read = '1'
        if start == '0' and last_start_read == '1':
            print("START line De-activated")
            last_start_read = '1'


if __name__ == "__main__":
    device = LCMSDevice(port='COM5')
    monitor_ouput_signals(device)
