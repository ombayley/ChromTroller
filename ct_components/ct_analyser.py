#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: A Python-based tool for automating in-line chromatographic data analysis.
This script handles:
    - File monitoring
    - Background and sample data comparison
    - Peak detection and processing
    - Multi-file batch analysis and logging of results
"""
import logging
from datetime import datetime
import os
import json
from glob import glob
from typing import Any, Dict, List, Optional

from ct_components.mocca2.classes import Component
from utils.get_project_directory import get_project_dir
from ct_components.mocca2 import ProcessingSettings, Chromatogram


class Analyser:
    """
        Analyser class is responsible for performing chromatographic data analysis.

        It handles file management, loading analysis settings from a JSON file,
        processing chromatogram data, detecting peaks, and managing batch analysis.

        Attributes:
            analysis_json_data (dict): Holds the analysis settings loaded from a JSON file.
            settings_obj (ProcessingSettings): An object holding the processed settings.
            file_tags (dict): Tags used to filter and identify files.
            fast_bkg (bool): Flag to indicate whether to use fast background subtraction.
            expected_peak_rt (float): Target retention time for peak detection.
            peak_match_rt_tolerance (float): Tolerance range for matching retention times.
        """

    def __init__(self, log_file: Optional[logging] = None):

        self.log_file = log_file if log_file is not None else self.setup_logging()
        self.analysis_json_data: Dict[str, Any] = self.load_analysis_json()
        self.settings_obj: ProcessingSettings = self.get_settings_obj()
        self.file_tags: Dict[str, Any] = self.analysis_json_data["tags"]
        self.fast_bkg: bool = False
        self.expected_peak_rt: float = 0.0
        self.peak_match_rt_tolerance: float = 0.1

        message = "Analyser Object Initialized Successfully"
        print(message)
        self.log_file.info(message)

    # -----Init Methods START-----
    def setup_logging(self):
        """
       Sets up basic logging to file
       """
        date_str = datetime.now().strftime("%Y-%m-%d--%H-%M-%S")
        log_path = os.path.join(get_project_dir(), 'log_files', f"CTAnalysis_{date_str}.log")
        log_file = logging
        log_file.basicConfig(level=logging.DEBUG,
                             datefmt='%Y-%m-%d %H-%M-%S',
                             format='%(asctime)s %(message)s',
                             filename=log_path,
                             filemode='w')
        return log_file

    def load_analysis_json(self) -> dict:
        """
        Load the analysis settings from a JSON file.

        Returns:
            dict: A dictionary containing the loaded JSON data.

        Raises:
            FileNotFoundError: If the settings file is not found.
            PermissionError: If the settings file cannot be accessed due to permission issues.
            json.JSONDecodeError: If there is an error decoding the JSON file.
        """
        try:

            settings_json_path = os.path.join(get_project_dir(), 'settings_files', 'settings.json')
            with open(settings_json_path, mode='r', encoding='utf-8') as infile:
                self.log_file.info(f"loaded analysis settings from json at path: {settings_json_path}")
                return json.load(infile)

        except (FileNotFoundError, PermissionError, json.JSONDecodeError) as error:
            self.log_file.error(f"Error: {error}")
            raise error

    def get_settings_obj(self) -> ProcessingSettings:
        """
        Create a ProcessingSettings object from the loaded JSON.

        Returns:
            ProcessingSettings: An object containing the settings for chromatogram processing.

        Raises:
            Exception: If the settings object cannot be created.
        """
        try:
            sett_dict = self.analysis_json_data.get("analysis_settings", {})
            if not sett_dict:
                raise KeyError("No analysis_settings key found in the loaded JSON dict")

            sett_obj = ProcessingSettings.from_dict(sett_dict)
            self.log_file.info("Settings object created from analysis JSON")
            return sett_obj
        except Exception as error:
            self.log_file.error(f"Error: {error}")
            raise error

    # -----Analysis Methods -----

    def run_analysis(self, sample_filepath: str, peak_rt: float, rt_tolerance: float = 0.1, ) -> \
            Optional[Dict[str, Any]]:
        """
        Perform chromatogram analysis on a given sample file.

        Args:
            sample_filepath (str): Path to the sample chromatogram file.
            peak_rt (float): The expected retention time for the target peak.
            rt_tolerance (float, optional): The tolerance for retention time matching. Default is 0.1 min.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing information about the closest peak detected,
            or None if no peaks are found.
        """
        try:
            # Identify bkg file. File tag for searching specified in analysis.json but is typically 'gradient'
            bkg_filepath = self.get_bkg_filepath(sample_filepath)

            # Create Chrom
            if bkg_filepath:
                smpl_chromatogram = Chromatogram(sample=sample_filepath, blank=bkg_filepath, name='sample')
                self.log_file.info(f"Chromatogram object generated with background reference correction")
            else:
                smpl_chromatogram = Chromatogram(sample=sample_filepath, name='sample')
                message = f"Chromatogram object generated WITHOUT a background reference file"
                print(message)
                self.log_file.warning(message)

            # Set min and max times based on the given target and tolerance
            min_time = peak_rt - rt_tolerance
            max_time = peak_rt + rt_tolerance

            # Process Chrom
            smpl_chromatogram = self.process_chrom(chrom=smpl_chromatogram, min_time=min_time, max_time=max_time)

            # From the smpl_chromatogram find the most applicable component
            best_fit_component: Component = self.filter_best_fit(smpl_chromatogram=smpl_chromatogram,
                                                                 filter_conditions=peak_rt)

            # Return dictionary of elution_time and integral of the best fitting component
            elut_time = smpl_chromatogram.time[best_fit_component.elution_time]
            return {"peak_rt": elut_time, "integral": best_fit_component.integral}

        except Exception as e:
            self.log_file.error(f"Error during analysis of file {sample_filepath}: {e}")
            return None

    @staticmethod
    def filter_best_fit(smpl_chromatogram: Chromatogram, filter_conditions: float) -> Component:
        """
        Filters the list of suitable peaks and identifies the most applicable based on retention time.

        NOTE 1: The filtering requirements will change to filter based on mass once the MS data can be accessed.
        NOTE 2: Component objects have attributes: concentration (NDArray), spectrum (NDArray),
        compound_id (int | None), elution_time (int), integral (float) and peak_fraction (float)

        Args:
            smpl_chromatogram (Chromatogram): Chromatogram object
            filter_conditions (float): The expected retention time for the target peak.

        Returns:
            Component: The component object correlating to the best match with the target peak
        """
        # Get processed data
        components: List[Component] = smpl_chromatogram.all_components()

        # Set search variables
        closest_component: Optional[Component] = None
        smallest_diff = float('inf')
        max_integral = max(component.integral for component in components)
        peak_size_min_cutoff = 0.1  # ignore any peaks that are less than 10% of the max peak
        min_integral = peak_size_min_cutoff * max_integral

        for component in components:
            elut_time_index = component.elution_time
            elut_time = smpl_chromatogram.time[elut_time_index]
            if component.integral >= min_integral and abs(elut_time - filter_conditions) > smallest_diff:
                smallest_diff = abs(elut_time - filter_conditions)
                closest_component = component

        return closest_component

    def process_chrom(self, chrom: Chromatogram, min_time: float = None, max_time: float = None) -> Chromatogram:
        """
        Processes the chromatogram according to the settings stored in the analysis_settings.json
        NOTE: the methods using inplace=True mutate the chrom object.

        Args:
            chrom (Chromatogram): The chromatogram to process.
            min_time (float, optional): Minimum elution time to consider.
            max_time (float, optional): Maximum elution time to consider.

        Returns:
            Chromatogram: The processed chromatogram.
        """

        min_time = min_time if not None else self.settings_obj.min_elution_time
        max_time = max_time if not None else self.settings_obj.max_elution_time

        chrom.extract_wavelength(
            min_wavelength=self.settings_obj.min_wavelength,
            max_wavelength=self.settings_obj.max_wavelength,
            inplace=True
        )

        chrom = chrom.correct_baseline(
            method=self.settings_obj.baseline_model,
            smoothness=self.settings_obj.baseline_smoothness
        )

        chrom = chrom.find_peaks(
            contraction="max",
            min_rel_height=self.settings_obj.min_rel_prominence,
            min_height=self.settings_obj.min_prominence,
            width_at=self.settings_obj.border_max_peak_cutoff,
            split_threshold=self.settings_obj.split_threshold,
            expand_borders=True,
            merge_overlapping=True,
            min_elution_time=min_time,
            max_elution_time=max_time
        )

        chrom = chrom.deconvolve_peaks(
            model=self.settings_obj.peak_model,
            min_r2=self.settings_obj.explained_threshold,
            relaxe_concs=self.settings_obj.relaxe_concs,
            max_comps=self.settings_obj.max_peak_comps
        )

        return chrom

    def get_data_filepath_list(self, sample_name: str, dirpath: str) -> List[str]:
        """
        Finds all files in the given directory that match the given sample name.
        NOTE: Returns all data runs whether they be file duplicates or different conditions.

        Args:
          sample_name (str): The name of the sample to search for.
          dirpath (str): The directory path to search in.

        Returns:
          List[str]: A sorted list of file paths that match the sample name.
        """
        data_file_type = self.file_tags["data_file_type"]
        data_files = glob(dirpath + "/*" + data_file_type)
        if not data_files:
            message = f"No {data_file_type} files found in: {dirpath}"
            print(message)
            self.log_file.error(message)

        sample_name = sample_name.replace(__old=" ", __new="_").lower()
        sample_files_list = [file for file in data_files if sample_name in file.replace(" ", "_").lower()]
        sample_files_list = sorted(sample_files_list)

        return sample_files_list

    def get_bkg_filepath(self, sample_filepath: str) -> Optional[str]:
        """
        Find the background file recorded closest in time to the sample file.

        Args:
            sample_filepath (str): Path to the sample chromatogram file.

        Returns:
            str: Path to the closest background file.
        """
        self.log_file.info(f"get_bkg_filepath method called with filepath: {sample_filepath}")

        # Get dirname and tag info.
        dirpath = os.path.dirname(sample_filepath)
        bkg_tag = self.file_tags.get("bkg_tag", "").replace(" ", "_").lower()
        data_file_type = self.file_tags.get("data_file_type", "")
        message = (f"Searching dirpath: {dirpath} for a background trace of type {data_file_type} "
                   f"containing the tag {bkg_tag}")
        print(message)
        self.log_file.info(message)

        # Find all gradient files
        data_files = glob(dirpath + "/*" + data_file_type)
        bkg_files_list = [file for file in data_files if bkg_tag in file.replace(" ", "_").lower()]

        # Catch no cases with no background data
        if not bkg_files_list:
            message = f"No background files of type {data_file_type} found in {dirpath} with the tag {bkg_tag}"
            print(message)
            self.log_file.info(message)
            return

        # Filter based on file creation time
        ctime_sample = os.path.getctime(sample_filepath)
        closest_bkg = min(bkg_files_list, key=lambda file: abs(ctime_sample - os.path.getctime(file)))

        return closest_bkg


if __name__ == "__main__":
    dirpath = r"\\fnwi-s0.science.uva.nl\hims-nrg-robochem\lcms_data\FGT\FGT_12_11_2024.rslt\Sample_003_06.dx"
    analyser = Analyser()
    run_result = analyser.run_analysis(sample_filepath=dirpath, peak_rt=2.0, rt_tolerance=0.1)
    print(run_result)
