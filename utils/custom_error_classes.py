#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: Custom error classes to provide more detailed info upon failures
"""


class ControllerError(Exception):
    """Base class for controller exceptions."""
    pass


class DeviceConnectionError(ControllerError):
    """Exception raised for device connection failures."""
    pass


class ValveSwitchError(ControllerError):
    """Exception raised when the valve fails to switch."""
    pass


class LCMSCommunicationError(ControllerError):
    """Exception raised for LCMS communication failures."""
    pass


class SampleDetectionError(ControllerError):
    """Exception raised when sample detection fails."""
    pass
