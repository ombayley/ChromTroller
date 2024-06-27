#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: Object containing run_information on the analysis of a single experiment run
"""
from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class RunLog:
    run_name: str
    robochem: Optional[str] = field(default_factory=str)
    controller: Optional[Dict] = field(default_factory=dict)
    monitor: Optional[str] = field(default_factory=str)
    analyser: Optional[Dict] = field(default_factory=dict)

    def add_info(self, program, info):
        if program == 'controller':
            self.controller.update(info)
        elif program == 'monitor':
            self.monitor = info
        elif program == 'analyser':
            self.analyser = info
        elif program == 'robochem':
            self.robochem = info

    def to_dict(self) -> dict:
        run_log_dict = {
            'run': self.run_name,
            'robochem': self.robochem,
            'controller': self.controller,
            'file': self.monitor,
            'analyser': self.analyser
        }
        return run_log_dict
