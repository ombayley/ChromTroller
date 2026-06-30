#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: Object containing run_information on the analysis of a single experiment run
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class RunLog:
    run_conditions: Optional[Any] = field(default_factory=dict)
    hplc_start: Optional[str] = field(default_factory=str)
    file: Optional[str] = field(default_factory=str)
    analysis: Optional[Dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        run_log_dict = {
            'run_conditions': self.run_conditions,
            'hplc_start': self.hplc_start,
            'file': self.file,
            'analysis': self.analysis
        }
        return run_log_dict

    def __eq__(self, other):
        if not isinstance(other, RunLog):
            return False
        return (self.run_conditions == other.run_conditions and
                self.hplc_start == other.hplc_start and
                self.file == other.file and
                self.analysis == other.analysis)
