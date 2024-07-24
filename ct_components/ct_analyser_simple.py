#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import logging
import os
import json
import pickle
from matplotlib import pyplot as plt
import time
from glob import glob
from ct_components.mocca2 import MoccaDataset, Chromatogram, ProcessingSettings


class Analyser:
    def __init__(self, results_dirpath):

        self.analysis_json_data = self.load_analysis_json()
        self.settings_obj = self.get_settings_obj()
        self.file_tags = self.analysis_json_data["file_tags"]

        # Changing this to just be the sample_path
        self.results_data_dirpath = results_dirpath

        self.fast_bkg = False
        self.campaign = MoccaDataset()
        self.log_info("Analyser Object Initialized Successfully")

    # -----Init Methods START-----

    def load_analysis_json(self) -> dict:
        """Load all analysis info from JSON file."""
        try:

            project_dir = os.path.dirname(os.path.dirname(__file__))
            settings_json_path = os.path.join(project_dir, 'settings_files', 'analysis_settings.json')
            with open(settings_json_path, mode='r', encoding='utf-8') as infile:
                self.log_info("loaded analysis settings from json")
                return json.load(infile)

        except (FileNotFoundError, PermissionError, json.JSONDecodeError) as error:
            logging.error(f"Error: {error}")
            raise error

    def get_settings_obj(self):
        try:
            sett_dict = self.analysis_json_data["analysis_settings"]
            self.log_info(f"settings read from analysis json")
            sett_obj = ProcessingSettings.from_dict(sett_dict)
            self.log_info(f"settings object created")
            return sett_obj
        except Exception as error:
            logging.error(f"Error: {error}")
            raise error

    # -----Init Methods END----
    # -----Analysis Methods START-----
    def main(self):
        """
        Central run method.
        """
        latest_file_path = self.find_latest_sample_path()
        file_name = self.expected_filename
        given_file_path = self.find_given_sample_path(file_name)

        # if latest_file != self.expected_filename:
        #     m = "WARNING - latest sample file does no match the file identified by the file monitor"
        #     logging.warning(m)
        #     print(m)
        # if self.expected_filename:
        #     file_name = self.expected_filename
        #     self.log_info("chromatogram generated from monitor file")
        # else:
        #     file_name = latest_file
        #     self.log_info("chromatogram generated from last file in directory")

        # sample_filepath = os.path.join(self.results_data_dirpath, file_name + self.file_tags["data_file_type"])

        bkg_filepath = self.get_bkg_filepath(latest_file_path)
        smpl_chrom = Chromatogram(sample=latest_file_path, blank=bkg_filepath, name='sample')
        self.process_chrom(smpl_chrom)
        integrals = smpl_chrom.get_integrals()
        smpl_chrom.plot()
        plt.show()

    def find_latest_sample_path(self):
        data_file_type = self.file_tags["data_file_type"]
        data_files = glob(self.results_data_dirpath + "/*" + data_file_type)
        name = self.file_tags["sample_tag"].replace(" ", "_").lower()
        sample_files_list = [file for file in data_files if name in file.replace(" ", "_").lower()]
        if sample_files_list:
            sample_files_list = sorted(sample_files_list)
            last_sample = os.path.basename(sample_files_list[-1])
            return last_sample

    def process_chrom(self, chrom):
        chrom.correct_baseline(
            method=self.settings_obj.baseline_model,
            smoothness=self.settings_obj.baseline_smoothness
        )

        chrom.extract_wavelength(
            min_wavelength=self.settings_obj.min_wavelength,
            max_wavelength=self.settings_obj.max_wavelength,
            inplace=True)

        chrom.extract_time(
            min_time=self.settings_obj.min_elution_time,
            max_time=self.settings_obj.max_elution_time,
            inplace=True
            )

        chrom.find_peaks(
            min_rel_height=self.settings_obj.min_rel_prominence,
            min_height=self.settings_obj.min_prominence,
            width_at=self.settings_obj.border_max_peak_cutoff,
            split_threshold=self.settings_obj.split_threshold,
            min_elution_time=self.settings_obj.min_elution_time,
            max_time=self.settings_obj.max_elution_time
        )

        chrom.deconvolve_peaks(
            model=self.settings_obj.peak_model,
            min_r2=self.settings_obj.explained_threshold,
            relaxe_concs=self.settings_obj.relaxe_concs,
            max_comps=self.settings_obj.max_peak_comps
        )

    def calulations_placeholder(self):
        return 1

    # -----Analysis Methods END-----
    # -----Basic Task Methods START-----

    def get_data_filepath_list(self, smpl_name, dirpath) -> list:
        """
        Finds the all files in the given dir that match the given sample name.
        NOTE: returns all data runs whether they be file duplicates or different conditions.
        """
        data_file_type = self.file_tags["data_file_type"]
        data_files = glob(dirpath + "/*" + data_file_type)
        if not data_files:
            self.log_error(f"No {data_file_type} files found in: {dirpath}")

        smpl_name = smpl_name.replace(" ", "_").lower()
        sample_files_list = [file for file in data_files if smpl_name in file.replace(" ", "_").lower()]
        sample_files_list = sorted(sample_files_list)

        return sample_files_list

    def get_bkg_filepath(self, filepath) -> str:
        """
        Finds the file path to the background file reccorded closest in time to the sample of intrest
        """
        print(f"filepath: {filepath}")
        dirpath = os.path.dirname(filepath)
        print(f"dirpath: {dirpath}")
        data_file_type = self.file_tags["data_file_type"]
        bkg_tag = self.file_tags["bkg_tag"].replace(" ", "_").lower()
        data_files = glob(dirpath + "/*" + data_file_type)

        if not data_files:
            self.log_error(f"No background traces found in directory: {dirpath}")

        ctime_sample = os.path.getctime(filepath)
        bkg_files_list = [file for file in data_files if bkg_tag in file.replace(" ", "_").lower()]
        closest_bkg = min(bkg_files_list, key=lambda file: abs(ctime_sample - os.path.getctime(file)))

        return closest_bkg

    # -----Basic Task Methods START-----
    # -----Util Methods START-----

    def get_data_filepaths_list(self, dir_path):
        data_file_type = self.file_tags.get("data_file_type")
        data_files = glob(dir_path + "/*" + data_file_type)
        data_files = sorted(data_files)

        if not data_files:
            self.log_info(f"No {data_file_type} file type found in: {dir_path}")
            return

        return data_files

    def set_dirs(self, results_data_path, calib_data_path=None):
        self.results_data_dirpath = results_data_path
        if calib_data_path:
            self.calib_data_dirpath = calib_data_path

    def set_expected_filename(self, filename):
        filename = os.path.splitext(filename)[0]
        self.expected_filename = filename

    @staticmethod
    def log_info(message):
        logging.info(message)
        print(message)
    @staticmethod
    def log_error(message):
        logging.error(message)
        print(message)
        raise Exception(message)

    # -----Util Methods END-----


if __name__ == "__main__":
    analyser = Analyser()
    analyser.set_dirs(
        results_data_path=r"C:\Users\obayley\Platform_Data\Dummy_results_dir",
        calib_data_path=r"C:\Users\obayley\Platform_Data\Dummy_results_dir"
    )
    analyser.reagents_to_calibrate = ["additive_01", "additive_02"]
    ack = analyser.prepare_camp()
    print(f"Campaign analysis calibration: {ack}")
    analyser.set_expected_filename("RoboChem Sample292024-06-07 07-42-09+02-00.dx")
    res = analyser.analyse(smpl_selection='all')
    print(res)
    # path = os.path.join(os.path.dirname(__file__), "campaign.json")
    # with open(path, "w") as file:
    #     json.dump(res, file, indent=4)
    # df = res[0]
    # df.to_csv(r"C:\Users\obayley\OneDrive - UvA\Desktop\run_result.csv")
    # print(f"Campaign analysis result: {res[0]}")
