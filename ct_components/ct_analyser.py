#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import logging
import threading
from ct_components.mocca2 import MoccaDataset

class Analyser:
    def __init__(self, run_log_list):
        self.run_log_list = run_log_list
        logging.info("Analyser Object Initialized Successfully")

    def run_calibration(self):
        return 'done'

    def run_analysis(self):
        return {'yield': 1, "conv": 2}

    # Create the MOCCA2 dataset
    dataset = MoccaDataset()

    chromatogram = Chromatogram(
        sample=PATH_TO_SAMPLE_CHROMATOGRAM,
        blank=PATH_TO_BLANK_CHROMATOGRAM,
    )

    # Specify chromatogram with with internal standard
    tetralin_concentration = 0.06094
    dataset.add_chromatogram(
        chromatograms["istd"],
        reference_for_compound="tetralin",
        istd_reference=True,
        compound_concentration=tetralin_concentration,
        istd_concentration=tetralin_concentration,
    )

    # Add standards for starting material and product
    dataset.add_chromatogram(
        chromatograms["educt_1"],
        reference_for_compound="starting_material",
        compound_concentration=0.0603,
        istd_concentration=tetralin_concentration,
    )
    dataset.add_chromatogram(
        chromatograms["product_1"],
        reference_for_compound="product",
        compound_concentration=0.05955,
        istd_concentration=tetralin_concentration,
    )

    # Add the chromatograms for the reactions
    for chromatogram in chromatograms["reactions"]:
        dataset.add_chromatogram(
            chromatogram, istd_concentration=tetralin_concentration
        )

    # Specify the processing settings
    # Default values are usually fine, but check the results and adjust if necessary
    settings = ProcessingSettings(
        baseline_model="flatfit",
        baseline_smoothness=float(1.0),
        min_rel_prominence=float(0.01),
        min_prominence=float(1),
        border_max_peak_cutoff=float(0.1),
        split_threshold=float(0.05),
        explained_threshold=float(0.995),
        peak_model="Bemg",
        max_peak_comps=int(4),
        max_peak_distance=float(1.0),
        min_spectrum_correl=float(0.99),
        min_elution_time=float(0.5),
        max_elution_time=float(5),
        min_wavelength=float(220),
        max_wavelength=float(280),
        min_rel_integral=float(0.01),
        relaxe_concs=False,
    )

    # Process the dataset
    dataset.process_all(settings, verbose=True, cores=15)

    # Get concentrations relative to the internal standard
    results = dataset.get_relative_concentrations()[0][
        ["Chromatogram", "starting_material", "product"]
    ]

    # If a compound is not detected, the concentration is set to nan
    # Convert nan to 0
    results = results.fillna(0)

    # Calculate conversion and yield
    initial_concentration = 0.06
    results["Conversion [%]"] = (
            100
            * (initial_concentration - results["starting_material"])
            / initial_concentration
    )
    results["Yield [%]"] = 100 * results["product"] / initial_concentration

    # Print the results
    print(
        results[["Chromatogram", "Conversion [%]", "Yield [%]"]]
        .round(0)
        .to_string(index=False)
    )

    def log_info(self, message):
        logging.info(message)
        with threading.Lock():
            self.run_log_list[-1].analysis = message
