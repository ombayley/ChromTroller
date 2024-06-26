#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: Object containing run_information on the analysis of a single experiment run
"""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class RunLog:
    run_name: str
    robochem: Optional[List] = field(default_factory=list)
    controller: Optional[List] = field(default_factory=list)
    monitor: Optional[List] = field(default_factory=list)
    analyser: Optional[List] = field(default_factory=list)

    def add_info(self, program, info):
        if program == 'controller':
            self.controller.append(info)
        elif program == 'monitor':
            self.monitor.append(info)
        elif program == 'analyser':
            self.analyser.append(info)
        elif program == 'robochem':
            self.robochem.append(info)


    def to_dict(self) -> dict:
        run_log_dict = {
            'run': self.run_name,
            'robochem': self.robochem,
            'controller': self.controller,
            'monitor': self.monitor,
            'analyser': self.analyser
        }
        return run_log_dict
