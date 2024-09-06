#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import logging
import os
import threading
import copy
import json
import pickle
import time
import re
from datetime import datetime
from glob import glob
from ct_components.mocca2 import MoccaDataset, Chromatogram, ProcessingSettings


class Analyser:
    def __init__(self, data_dir_path, run_log_list):
        # Setup logging
        self._setup_logging()
        # Set passed result dir as public var
        self.data_dir_path = self._set_data_dir(data_dir_path)
        # Get the shared run_log list (use thread lock when accessing!)
        self.run_log_list = run_log_list
        # Set default filenames and tags
        self.file_tags = self.set_default_file_tags()
        # Get settings data from settings json
        self.analysis_json_data = self.load_analysis_json()
        # Get current data
        self.data_filenames_list = self.get_data_filenames()
        # Get analysis settings
        self.settings = self.get_settings()
        # Set internal standard conc
        self.istd_conc = 0
        # Create the MOCCA2 dataset for the campaign
        self.campaign = MoccaDataset()
        # fast_bkg skips the background time matching and just returns the first bkg
        self.fast_bkg = False
        # Log init completion
        logging.info("Analyser Object Initialized Successfully")

    # -----Init Methods START-----
    @staticmethod
    def _setup_logging():
        """ Sets log format and file destination """
        # Set path to the 'logs' directory.
        root_dir_path = os.path.dirname(os.path.abspath(__file__))
        log_dir_path = os.path.join(root_dir_path, '../../logs')

        # Ensure the logs directory exists
        os.makedirs(log_dir_path, exist_ok=True)

        # Set the log file name
        date_str = datetime.now().strftime("%d-%m-%Y--%H-%M-%S")
        log_file_name = f"ChromTroller_analyser_{date_str}_logfile.log"
        log_file_path = os.path.join(log_dir_path, log_file_name)

        # Set up logging configuration
        logging.basicConfig(
            filename=log_file_path,
            level=logging.INFO,
            format=f'%(asctime)s - %(levelname)s - %(filename)s - %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S',
            filemode='w'  # w=write, a=append
        )

    def get_settings(self):
        sett_dict = self.analysis_json_data["analysis_settings"]
        logging.info(f"settings read from analysis json")
        sett_obj = ProcessingSettings.from_dict(sett_dict)
        logging.info(f"settings object created")
        return sett_obj

    @staticmethod
    def set_default_file_tags() -> dict:
        """ Set default file naming and type tags used in campaign. """
        return {
            "bkg_tag": "gradient",
            "sample_tag": "sample",
            "data_file_type": ".dx"
        }

    # ---

    @staticmethod
    def _set_data_dir(data_dir_path) -> str:
        if not os.path.exists(data_dir_path):
            e = f"No data directory found at: {data_dir_path}"
            print(e)
            logging.error(e)
            raise FileNotFoundError(e)
        return data_dir_path

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

    # ---

    def get_data_filenames(self) -> list:

        data_file_type = self.file_tags.get("data_file_type")
        data_files = glob(self.data_dir_path + "/*" + data_file_type)
        data_files = sorted(data_files)

        if not data_files:
            message = f"No {data_file_type} file type found in: {self.data_dir_path}"
            print(message)
            logging.info(message)
            return []
        self.data_filenames_list = data_files
        return data_files

    # -----Init Methods END----
    # -----Run Sequence START-----
    def calibrate(self):
        self.campaign = self.add_istd(self.campaign)
        logging.info("istd added to campaign")
        self.campaign = self.add_sm(self.campaign)
        logging.info("sm added to campaign")
        self.campaign = self.add_prod(self.campaign)
        logging.info("prod added to campaign")
        # save
        self.save_calibration(self.campaign)
        logging.info("calibration info saved")
        return 'SUCCESS'

    def analyse(self):
        run_campaign = copy.deepcopy(self.campaign)
        # run_campaign = self.add_reagent(run_campaign, "additive_01")
        run_campaign = self.add_all_samples(run_campaign)
        # Process the dataset
        start_time = time.time()
        run_campaign.process_all(self.settings, verbose=True, cores=8)
        print(f"run complete after {time.time() - start_time} seconds")
        self.save_analysis(run_campaign)
        # Get concentrations relative to the internal standard
        results = run_campaign.get_relative_concentrations()[0][
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

    def add_istd(self, campaign):
        self.istd_conc = self.analysis_json_data["internal_standard"]["conc"]
        istd_name = self.analysis_json_data["internal_standard"]["name"]

        istd_file_path_list = self.find_sample_paths(name=istd_name)

        if not istd_file_path_list:
            message = f"No istd data found in: {self.data_filenames_list}"
            print(message)
            logging.info(message)
            return
        logging.info(f"istd file found {istd_file_path_list[-1]}")

        bkg_file_path = self.find_closest_bkg_path(filename=istd_file_path_list[-1])
        logging.info(f"background file found {bkg_file_path}")

        istd_chrom = Chromatogram(
            sample=istd_file_path_list[-1],
            blank=bkg_file_path,
            name=istd_name
        )
        logging.info('Chromatogram generated')

        campaign.add_chromatogram(
            chromatogram=istd_chrom,
            reference_for_compound=istd_name,
            istd_reference=True,
            compound_concentration=self.istd_conc,
            istd_concentration=self.istd_conc
        )
        logging.info(f'istd chromatogram added to campaign - {istd_file_path_list[-1]}')
        return campaign

    def add_sm(self, campaign):
        sm_name = None
        conc_list = []

        for comp in self.analysis_json_data["calibration_info"]:
            if comp["Role"] == "Starting Material":
                sm_name = comp["Compound"]
                conc_list = comp["Calibration Concs"]
                break

        for conc in conc_list:
            sm_file_path_list = self.find_sample_paths(name=sm_name, conc=conc)
            if sm_file_path_list:
                sm_file_path = sm_file_path_list[-1]  # use last in list in case sample run twice
                bkg_file_path = self.find_closest_bkg_path(filename=sm_file_path)
                sm_chrom = Chromatogram(
                    sample=sm_file_path,
                    blank=bkg_file_path,
                    name=sm_name
                )
                campaign.add_chromatogram(
                    chromatogram=sm_chrom,
                    reference_for_compound="starting_material",
                    compound_concentration=conc,
                    istd_concentration=self.istd_conc
                )
                logging.info(f'sm chromatogram added to campaign - {sm_file_path_list[-1]}')
            else:
                logging.info(f'no data found for sm chromatogram')
        return campaign

    def add_prod(self, campaign):
        prod_name = None
        conc_list = []

        for comp in self.analysis_json_data["calibration_info"]:
            if comp["Role"] == "Product":
                prod_name = comp["Compound"]
                conc_list = comp["Calibration Concs"]
                break

        for conc in conc_list:
            prod_file_path_list = self.find_sample_paths(name=prod_name, conc=conc)
            if prod_file_path_list:
                prod_file_path = prod_file_path_list[-1]
                bkg_file_path = self.find_closest_bkg_path(filename=prod_file_path)
                prod_chrom = Chromatogram(
                    sample=prod_file_path,
                    blank=bkg_file_path,
                    name=prod_name
                )
                campaign.add_chromatogram(
                    chromatogram=prod_chrom,
                    reference_for_compound="product",
                    compound_concentration=conc,
                    istd_concentration=self.istd_conc
                )
                logging.info(f'Prod chromatogram added to campaign - {prod_file_path_list[-1]}')
            else:
                logging.info(f'no data found for prod chromatogram')
        return campaign

    def add_reagent(self, campaign, reagent_name):
        reagent_name = reagent_name.replace(" ", "_").lower()
        conc_list = []

        for comp in self.analysis_json_data["calibration_info"]:
            if reagent_name in comp["Compound"].replace(" ", "_").lower():
                conc_list = comp["Calibration Concs"]
                break

        for conc in conc_list:
            reag_file_path_list = self.find_sample_paths(name=reagent_name, conc=conc)
            if reag_file_path_list:
                reag_file_path = reag_file_path_list[-1]
                bkg_file_path = self.find_closest_bkg_path(filename=reag_file_path)
                reag_chrom = Chromatogram(
                    sample=reag_file_path,
                    blank=bkg_file_path,
                    name=reagent_name
                )
                campaign.add_chromatogram(
                    chromatogram=reag_chrom,
                    reference_for_compound=reagent_name,
                    compound_concentration=conc,
                    istd_concentration=self.istd_conc
                )
                logging.info(f'reagent chromatogram added to campaign - {reag_file_path_list[-1]}')
            else:
                logging.info(f'no data found for reagent chromatogram')
        return campaign

    def add_latest_sample(self, campaign):
        data_files = self.get_data_filenames()
        name = self.file_tags["sample_tag"].replace(" ", "_").lower()
        sample_files_list = [file for file in data_files if name in file.replace(" ", "_").lower()]
        if sample_files_list:
            sample_file_path = sample_files_list[-1]
            bkg_file_path = self.find_closest_bkg_path(filename=sample_file_path)
            reag_chrom = Chromatogram(
                sample=sample_file_path,
                blank=bkg_file_path,
                name='sample'
            )
            campaign.add_chromatogram(
                chromatogram=reag_chrom,
                istd_concentration=self.istd_conc
            )
            logging.info(f'sample chromatogram added to campaign - {sample_files_list[-1]}')
        else:
            logging.info(f'no sample chromatogram data found')
        return campaign

    def add_all_samples(self, campaign):
        data_files = self.get_data_filenames()
        name = self.file_tags["sample_tag"].replace(" ", "_").lower()
        sample_files_list = [file for file in data_files if name in file.replace(" ", "_").lower()]
        smpl_num = 1
        for sample_file_path in sample_files_list:
            # Temp to get sample number from filenames
            pattern = r"RoboChem Sample(\d{2})"
            input_string = os.path.basename(sample_file_path)
            match = re.search(pattern, input_string)
            # Extract the two digits if the pattern is found
            if match:
                smpl_num = match.group(1)

            bkg_file_path = self.find_closest_bkg_path(filename=sample_file_path)
            reag_chrom = Chromatogram(
                sample=sample_file_path,
                blank=bkg_file_path,
                name=f'sample_{smpl_num}'
            )
            campaign.add_chromatogram(
                chromatogram=reag_chrom,
                istd_concentration=self.istd_conc
            )
            logging.info(f'sample chromatogram added to campaign - {sample_file_path}')
            # smpl_num += 1
        if not sample_files_list:
            logging.info(f'no sample chromatogram data found')
        return campaign

    # -----Calibration Methods END-----
    # -----Basic Task Methods START-----

    def find_sample_paths(self, name, conc=None) -> list:
        data_files = self.data_filenames_list  # self.get_data_filenames()
        name = name.replace(" ", "_").lower()
        sample_files_list = [file for file in data_files if name in file.replace(" ", "_").lower()]

        if conc:
            conc = str(conc).replace(" ", "_").lower()
            sample_files_list = [file for file in sample_files_list if conc in file.replace(" ", "_").lower()]

        return sample_files_list

    def find_closest_bkg_path(self, filename) -> str:
        ctime_sample = os.path.getctime(filename)
        data_files = self.data_filenames_list  # self.get_data_filenames()
        bkg = self.file_tags["bkg_tag"].replace(" ", "_").lower()

        # Ability to skip time matching
        if self.fast_bkg:
            for file in data_files:
                if bkg in file.replace(" ", "_").lower():
                    return bkg

        bkg_files_list = [file for file in data_files if bkg in file.replace(" ", "_").lower()]

        if not bkg_files_list:
            e = f"No background traces found in data"
            print(e)
            logging.error(e)
            return ""

        closest_bkg = bkg_files_list[0]
        for bkg in bkg_files_list:
            if abs(ctime_sample - os.path.getctime(bkg)) < abs(ctime_sample - os.path.getctime(closest_bkg)):
                closest_bkg = bkg

        return closest_bkg

    @staticmethod
    def save_calibration(campaign):
        with open("calibration_campaign.pkl", "wb") as file:
            pickle.dump(campaign, file)

    @staticmethod
    def load_calibration():
        with open("calibration_campaign.pkl", "rb") as file:
            return pickle.load(file)

    @staticmethod
    def save_analysis(campaign):
        with open("analysis_campaign.pkl", "wb") as file:
            pickle.dump(campaign, file)

    @staticmethod
    def load_analysis():
        with open("analysis_campaign.pkl", "rb") as file:
            return pickle.load(file)

    # -----Basic Task Methods End-----

    def log_info(self, message):
        logging.info(message)
        with threading.Lock():
            self.run_log_list[-1].analysis = message


if __name__ == "__main__":
    run_log_list = []
    data_dir_path = r"C:\Users\obayley\Platform_Data\FGT\Test"
    analyser = Analyser(data_dir_path, run_log_list)
    analyser.calibrate()
    analyser.analyse()
