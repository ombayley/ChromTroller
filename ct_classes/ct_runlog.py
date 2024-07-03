#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: Object containing run_information on the analysis of a single experiment run
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class RunLog:
    run_name: str
    run_conc: Optional[float] = field(default_factory=float)
    reagent_list: Optional[List] = field(default_factory=list)
    run_conditions: Optional[Dict] = field(default_factory=dict)
    controller: Optional[Dict] = field(default_factory=dict)
    file: Optional[str] = field(default_factory=str)
    analysis: Optional[Dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        run_log_dict = {
            'run_name': self.run_name,
            'run_conc': self.run_conc,
            'reagent_list': self.reagent_list,
            'run_conditions': self.run_conditions,
            'controller': self.controller,
            'file': self.file,
            'analysis': self.analysis
        }
        return run_log_dict

    def __eq__(self, other):
        if not isinstance(other, RunLog):
            return False
        return (self.run_name == other.run_name and
                self.run_conc == other.run_conc and
                self.reagent_list == other.reagent_list and
                self.run_conditions == other.run_conditions and
                self.controller == other.controller and
                self.file == other.file and
                self.analysis == other.analysis)
