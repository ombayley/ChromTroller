#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import logging
import os
import json
from ct_components.mocca2.math import cosine_similarity
from matplotlib import pyplot as plt
from glob import glob
from ct_components.mocca2 import ProcessingSettings, Chromatogram


class Analyser:
    def __init__(self):

        self.analysis_json_data = self.load_analysis_json()
        self.settings_obj = self.get_settings_obj()
        self.file_tags = self.analysis_json_data["file_tags"]
        self.fast_bkg = False
        self.log_info("Analyser Object Initialized Successfully")

    # -----Init Methods START-----

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
            raise error

    def get_settings_obj(self):
        try:
            sett_dict = self.analysis_json_data["analysis_settings"]
            sett_obj = ProcessingSettings.from_dict(sett_dict)
            logging.info(f"settings object created from analysis json")
            return sett_obj
        except Exception as error:
            logging.error(f"Error: {error}")
            raise error

    # -----Init Methods END----
    # -----Analysis Methods START-----

    def run_analysis(self, sample_filepath):
        """
        Central run method.
        """
        bkg_filepath = self.get_bkg_filepath(sample_filepath)
        smpl_chromatogram = Chromatogram(sample=sample_filepath, blank=bkg_filepath, name='sample')
        smpl_chromatogram = self.process_chrom(smpl_chromatogram)
        components = smpl_chromatogram.all_components()
        for component in components:
            elut_time_index = component.elution_time
            elut_time = smpl_chromatogram.time[elut_time_index]
            integral = component.integral
            id = component.compound_id
            spectrum = component.spectrum

        smpl_chromatogram.plot()
        plt.show()
        # return integrals

    def process_chrom(self, chrom):
        chrom = chrom.correct_baseline(
            method=self.settings_obj.baseline_model,
            smoothness=self.settings_obj.baseline_smoothness
        )

        chrom = chrom.extract_wavelength(
            min_wavelength=self.settings_obj.min_wavelength,
            max_wavelength=self.settings_obj.max_wavelength
        )

        chrom = chrom.extract_time(
            min_time=self.settings_obj.min_elution_time,
            max_time=self.settings_obj.max_elution_time
        )

        chrom = chrom.find_peaks(
            min_rel_height=self.settings_obj.min_rel_prominence,
            min_height=self.settings_obj.min_prominence,
            width_at=self.settings_obj.border_max_peak_cutoff,
            split_threshold=self.settings_obj.split_threshold,
            min_elution_time=self.settings_obj.min_elution_time,
            max_elution_time=self.settings_obj.max_elution_time
        )

        chrom = chrom.deconvolve_peaks(
            model=self.settings_obj.peak_model,
            min_r2=self.settings_obj.explained_threshold,
            relaxe_concs=self.settings_obj.relaxe_concs,
            max_comps=self.settings_obj.max_peak_comps
        )

        return chrom

    def match_component(self, chromatogram, components_list, retention_time, uv_spectra=None, ms_spectra_peak=None):
        # check within expected expectred r.t
        min_elut_time = retention_time - self.settings_obj.max_peak_distance
        max_elut_time = retention_time + self.settings_obj.max_peak_distance

        for component in components_list:
            elut_time = chromatogram.time[component.elution_time]
            if min_elut_time <= elut_time <= max_elut_time:
                print("Component found with desire retention times")

            if uv_spectra and cosine_similarity(component.spectrum, uv_spectra) >= self.settings_obj.min_spectrum_correl:
                print("Component found with matching UV spectra")

            if ms_spectra_peak and ms_spectra_peak in component.ms_spectrum:
                print("Component found with desired mass")



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
    filepath = r"C:\Users\obayley\Platform_Data\Dummy_results_dir\RoboChem Sample292024-06-07 07-42-09+02-00.dx"
    analyser = Analyser()
    res = analyser.run_analysis(filepath)
    print(res)

