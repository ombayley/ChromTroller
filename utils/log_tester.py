#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import logging
from datetime import datetime

class TestLogger:
    def __init__(self):
        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - TEST - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[logging.FileHandler(f"testlog_{datetime.now().strftime('%Y%m%d')}.log", mode='a'),
                      logging.StreamHandler()]
        )

    def log_something(self):
        logging.info("This is a test message.")

if __name__ == "__main__":
    tl = TestLogger()
    tl.log_something()
