#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import logging
import os
import copy
import json
import pickle
import time
from glob import glob
from ct_components.mocca2 import MoccaDataset, Chromatogram, ProcessingSettings


class Analyser:
    def __init__(self, queue):
        self.queue = queue

        # Set default filenames and tags
        self.file_tags = self.set_default_file_tags()
        # Get settings data from settings json
        self.analysis_json_data = self.load_analysis_json()
        # Get current data
        self.data_filenames_list = None
        self.update_data_filenames_list()
        # Get analysis settings
        self.settings_obj = self.get_settings_obj()

        self.calib_data_dirpath = None
        self.results_data_dirpath = None
        self.expected_filename = None
        self.reagents_to_calibrate = None
        self.istd_conc = self.analysis_json_data["internal_standard"]["conc"]

        # Create the MOCCA2 dataset for the campaign
        self.campaign = MoccaDataset()

        # fast_bkg skips the background time matching and just returns the first bkg
        self.fast_bkg = False

        # Log init completion
        logging.info("Analyser Object Initialized Successfully")

    # -----Init Methods START-----
    @staticmethod
    def set_default_file_tags() -> dict:
        """ Set default file naming and type tags used in campaign. """
        return {
            "bkg_tag": "gradient",
            "sample_tag": "sample",
            "data_file_type": ".dx"
        }

    @staticmethod
    def load_analysis_json() -> dict:
        """Load all analysis info from JSON file."""
        try:

            project_dir = os.path.dirname(os.path.dirname(__file__))
            settings_json_path = os.path.join(project_dir, 'settings_files', 'analysis_settings.json')
            with open(settings_json_path, mode='r', encoding='utf-8') as infile:
                logging.info("loaded analysis settings from json")
                return json.load(infile)

        except (FileNotFoundError, PermissionError, json.JSONDecodeError) as error:
            logging.error(f"Error: {error}")

    def get_settings_obj(self):
        sett_dict = self.analysis_json_data["analysis_settings"]
        logging.info(f"settings read from analysis json")
        sett_obj = ProcessingSettings.from_dict(sett_dict)
        logging.info(f"settings object created")
        return sett_obj

    def update_data_filenames_list(self):
        data_file_type = self.file_tags.get("data_file_type")
        data_files = glob(self.results_data_dirpath + "/*" + data_file_type)
        data_files = sorted(data_files)
        self.data_filenames_list = data_files
        if not data_files:
            self.log_info(f"No {data_file_type} file type found in: {self.results_data_dirpath}")

    def set_dirs(self, results_data_path, calib_data_path=None):
        self.results_data_dirpath = results_data_path
        if calib_data_path:
            self.calib_data_dirpath = calib_data_path

    def set_expected_filename(self, filename):
        self.expected_filename = filename

    # -----Init Methods END----
    # -----Run Sequence START-----
    def prepare_camp(self):
        self.add_istd()
        self.add_sm()
        self.add_prod()
        for reagent in self.reagents_to_calibrate:
            self.add_reagent(reagent)
        self.save_campaign()
        return 'SUCCESS'

    def analyse(self):
        self.add_latest_sample()
        start_time = time.time()
        self.campaign.process_all(self.settings_obj, verbose=True, cores=12)
        self.log_info(f"run complete after {time.time() - start_time} seconds")
        self.save_campaign()

        # Get concentrations relative to the internal standard
        results = self.campaign.get_relative_concentrations()[0][
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

        sample_row = results[results["Chromatogram"] == "sample"]

        # Extract the Conversion and Yield values
        if not sample_row.empty:
            conv_value = sample_row["Conversion [%]"].values[0]
            yield_value = sample_row["Yield [%]"].values[0]

            # Create the dictionary
            sample_dict = {"conv": conv_value, "yield": yield_value}
            return sample_dict

    # -----Run Sequence END-----
    # -----Calibration Methods START-----

    def add_istd(self):
        """Add the data for the internal standard to the campaign. Must be present"""
        istd_name = self.analysis_json_data["internal_standard"]["name"]
        istd_chrom = self.get_chromatogram_from_name(name=istd_name)

        self.campaign.add_chromatogram(
            chromatogram=istd_chrom,
            reference_for_compound=istd_name,
            istd_reference=True,
            compound_concentration=self.istd_conc,
            istd_concentration=self.istd_conc
        )
        logging.info(f'istd chromatogram added to campaign - {istd_chrom.sample_path}')

    def add_sm(self):
        """Add the data for the starting material to the campaign"""
        sm_name = None
        conc_list = []

        for comp in self.analysis_json_data["calibration_info"]:
            if comp["Role"] == "Starting Material":
                sm_name = comp["Compound"]
                conc_list = comp["Calibration Concs"]
                break

        for conc in conc_list:
            sm_chrom = self.get_chromatogram_from_name(name=sm_name, conc=conc)
            self.campaign.add_chromatogram(
                chromatogram=sm_chrom,
                reference_for_compound="starting_material",
                compound_concentration=conc,
                istd_concentration=self.istd_conc
            )
            logging.info(f'sm chromatogram added to campaign - {sm_chrom.sample_path}')

    def add_prod(self):
        """Add the data for the product to the campaign"""
        prod_name = None
        conc_list = []

        for comp in self.analysis_json_data["calibration_info"]:
            if comp["Role"] == "Product":
                prod_name = comp["Compound"]
                conc_list = comp["Calibration Concs"]
                break

        for conc in conc_list:
            prod_chrom = self.get_chromatogram_from_name(name=prod_name, conc=conc)
            self.campaign.add_chromatogram(
                chromatogram=prod_chrom,
                reference_for_compound="product",
                compound_concentration=conc,
                istd_concentration=self.istd_conc
            )
            logging.info(f'Prod chromatogram added to campaign - {prod_chrom.sample_path}')

    def add_reagent(self, reagent_name):
        """Add the data for the specific reagent to the campaign. the reagent must have
         the raw data as well as an entry in the analysis calibration JSON"""
        reagent_name = reagent_name.replace(" ", "_").lower()
        conc_list = []

        for comp in self.analysis_json_data["calibration_info"]:
            if reagent_name in comp["Compound"].replace(" ", "_").lower():
                conc_list = comp["Calibration Concs"]
                break

        for conc in conc_list:
            reagent_chrom = self.get_chromatogram_from_name(name=reagent_name, conc=conc)
            self.campaign.add_chromatogram(
                chromatogram=reagent_chrom,
                reference_for_compound=reagent_name,
                compound_concentration=conc,
                istd_concentration=self.istd_conc
            )
            logging.info(f'reagent chromatogram added to campaign - {reagent_chrom.sample_path}')

    # -----Calibration Methods END-----
    # -----Run Methods START-----

    def add_latest_sample(self):
        """Adds the most recent sample file to the campaign for analysis"""
        latest_file = self.find_latest_sample()
        if latest_file != self.expected_filename:
            m = "WARNING - final sample file does no match the file identified by the file monitor"
            logging.warning(m)
            print(m)

        if self.expected_filename:
            sample_chrom = self.get_chromatogram_from_name(self.expected_filename)
            self.log_info("chromatogram generated from monitor detected file")
        else:
            sample_chrom = self.get_chromatogram_from_name(latest_file)
            self.log_info("chromatogram generated from latest_file")

        self.campaign.add_chromatogram(
            chromatogram=sample_chrom,
            istd_concentration=self.istd_conc
        )
        self.log_info(f'reagent chromatogram added to campaign - {sample_chrom.sample_path}')

    def add_all_samples(self):
        """Adds the most recent sample file to the campaign for analysis"""
        self.update_data_filenames_list()
        name = self.file_tags["sample_tag"].replace(" ", "_").lower()
        sample_files_list = [file for file in self.data_filenames_list if name in file.replace(" ", "_").lower()]
        for sample in sample_files_list:
            sample_chrom = self.get_chromatogram_from_name(sample)
            self.campaign.add_chromatogram(
                chromatogram=sample_chrom,
                istd_concentration=self.istd_conc
            )
            self.log_info(f'reagent chromatogram added to campaign - {sample}')

    # -----Run Methods END-----
    # -----Basic Task Methods START-----
    def get_chromatogram_from_name(self, name, conc=None):
        """Returns a chromatogram object coressponding to the given name"""

        sample_filepath = self.find_sample_path(name=name, conc=conc)
        if not sample_filepath:
            self.log_info(f"No data found in directory: {self.results_data_dirpath} for compound: {name}")
            return
        logging.info(f"file: {sample_filepath} found for compound: {name}")

        bkg_file_path = self.get_bkg_path(filename=sample_filepath)
        if not bkg_file_path:
            self.log_info(f"No istd data found in directory: {self.results_data_dirpath}")
            return
        logging.info(f"background file found {bkg_file_path}")

        chrom = Chromatogram(
            sample=sample_filepath,
            blank=bkg_file_path,
            name=name
        )
        logging.info('Chromatogram generated')

        return chrom

    def find_sample_path(self, name, conc=None) -> str:
        """
        Finds the filepath for the sample matching the given name and concentration.
        If multiple files are found that match the given name and conc, returns the most recent file.
        """
        data_files = self.data_filenames_list  # self.get_data_filenames()
        name = name.replace(" ", "_").lower()
        sample_files_list = [file for file in data_files if name in file.replace(" ", "_").lower()]

        if conc:
            conc = str(conc).replace(" ", "_").lower()
            sample_files_list = [file for file in sample_files_list if conc in file.replace(" ", "_").lower()]

        return sample_files_list[-1]

    def get_bkg_path(self, filename) -> str:
        """
        Finds the file path to the relevant background file.
        If fast_bkg is ON then it returns the first background file.
        If fast_bkg is OFF it returns the bkg file reccorded closest in time to the sample of intrest
        """
        bkg_tag = self.file_tags["bkg_tag"].replace(" ", "_").lower()

        # SHORTER - returns the first background file in the file list
        if self.fast_bkg:
            for file in self.data_filenames_list:
                if bkg_tag in file.replace(" ", "_").lower():
                    self.log_info(f"gradient file: {file} used for chromatogram background")
                    return file

        # LONGER - returns the background file for the bkg closest in time to the sample of intrest
        ctime_sample = os.path.getctime(filename)
        self.update_data_filenames_list()
        bkg_files_list = [file for file in self.data_filenames_list if bkg_tag in file.replace(" ", "_").lower()]

        if not bkg_files_list:
            self.log_info("No background traces found in data")
            return ""

        closest_bkg = min(bkg_files_list, key=lambda file: abs(ctime_sample - os.path.getctime(file)))

        return closest_bkg

    def find_latest_sample(self):
        self.update_data_filenames_list()
        name = self.file_tags["sample_tag"].replace(" ", "_").lower()
        sample_files_list = [file for file in self.data_filenames_list if name in file.replace(" ", "_").lower()]
        if sample_files_list:
            return sample_files_list[-1]

    # -----Basic Task Methods START-----
    # -----Util Methods START-----

    @staticmethod
    def save_campaign(campaign):
        with open("campaign.pkl", "wb") as file:
            pickle.dump(campaign, file)

    @staticmethod
    def load_campaign():
        with open("campaign.pkl", "rb") as file:
            return pickle.load(file)

    @staticmethod
    def log_info(self, message):
        logging.info(message)
        print(message)
        # self.queue.put(message)

    # -----Util Methods END-----


if __name__ == "__main__":
    run_log_list = []
    data_dir_path = r"C:\Users\obayley\Platform_Data\Dummy_results_dir"
    analyser = Analyser(data_dir_path, run_log_list)
    analyser.prepare_camp()
    analyser.analyse()
