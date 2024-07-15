#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from ct_components.devices.lcms_device import LCMSDevice


async def monitor_ouput_signals(device, executor):
    last_ready_read = '0'
    last_power_read = '0'
    last_start_read = '0'
    loop = asyncio.get_event_loop()
    while True:
        ready = await loop.run_in_executor(executor, device.get_lcms_ready)
        power = await loop.run_in_executor(executor, device.get_lcms_power)
        start = await loop.run_in_executor(executor, device.get_lcms_start)

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

        await asyncio.sleep(0.01)


if __name__ == "__main__":
    device = LCMSDevice(port='COM5')
    executor = ThreadPoolExecutor(max_workers=3)
    asyncio.run(monitor_ouput_signals(device, executor))
