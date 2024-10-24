#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""


import logging
import os
import json
import pandas as pd
from glob import glob
from matplotlib import pyplot as plt
from typing import Any, Dict, List, Optional

from ct_components.mocca2.classes import Component
from utils.get_project_directory import get_project_dir
from ct_components.mocca2.math import cosine_similarity
from ct_components.mocca2 import ProcessingSettings, Chromatogram

def run_multi_analysis(self, dirpath):
    """
    Central run method.
    """
    files = [file for file in next(os.walk(dirpath))[2] if file.endswith(".dx") and "sample" in file.lower()]
    data = []
    for file in files:
        try:
            sample_filepath = os.path.join(dirpath, file)
            bkg_filepath = self.get_bkg_filepath(sample_filepath)
            smpl_chromatogram = Chromatogram(sample=sample_filepath, blank=bkg_filepath, name=file)
            smpl_chromatogram = self.process_chrom(smpl_chromatogram)
            components = smpl_chromatogram.all_components()
            for index, component in enumerate(components):
                elut_time_index = component.elution_time
                elut_time = smpl_chromatogram.time[elut_time_index]
                integral = component.integral
                print(f"peak at: {elut_time}\nintegral: {integral}\n")
                data.append({
                    'file': file,
                    'peak': index,
                    'elut_time': elut_time,
                    'integral': integral
                })

            # smpl_chromatogram.plot()
            # plt.show()

        except Exception as e:
            print(f"Error processing file {file}: {e}")
            continue  # Skip to the next file

    if data:
        save_path = os.path.join(dirpath, 'integral_summary.csv')
        df = pd.DataFrame(data)
        df.to_csv(save_path, index=False)
        print("Results saved to 'integral_summary.csv'")
    # return integrals

    # vv ------ vv !! Trail methods used while developing better batch processing !! vv ------ vv
    # Mostly garbage methods at the moment but need to merge, clean and retest


def trim_integral_summary(self, path):
    # Load the CSV file into a DataFrame
    df = pd.read_csv(path)
    # Extract the concentration value before 'M' and add it to a new column called 'conc'
    df['conc'] = df['file'].str.extract(r'(\d+\.\d+)\s*M')
    # Remove the concentration part and '.dx' suffix to update the 'name' column
    df['file'] = df['file'].str.replace(r'\d+\.\d+\s*M\s*-\s*', '', regex=True) \
        .str.replace(r'-\d+\.dx$', '', regex=True)
    save_path = os.path.join(os.path.dirname(path), 'modified_file.csv')
    # Save the modified DataFrame back to a CSV file if needed
    df.to_csv(save_path, index=False)

    self.get_compound_peaks(save_path)


def get_compound_peaks(self, path):
    # Load the CSV file into a DataFrame
    df = pd.read_csv(path)

    # Identify the Internal Standard rows
    internal_standard_rows = df[df['file'] == 'Internal Standard']

    # Initialize a list to store the indices of rows to remove
    rows_to_remove = []

    # Loop through each internal standard entry
    for _, internal_row in internal_standard_rows.iterrows():
        internal_rt = internal_row['elut_time']
        internal_integral = internal_row['integral']

        # Define the tolerance ranges for retention time and integral (10% tolerance)
        rt_lower = internal_rt * 0.9
        rt_upper = internal_rt * 1.1
        integral_lower = internal_integral * 0.9
        integral_upper = internal_integral * 1.1

        # Find the rows in other files that fall within these tolerance ranges
        for idx, row in df[df['file'] != 'Internal Standard'].iterrows():
            if (rt_lower <= row['elut_time'] <= rt_upper) and (integral_lower <= row['integral'] <= integral_upper):
                rows_to_remove.append(idx)

    # Remove the identified rows
    df_filtered = df.drop(rows_to_remove)

    save_path = os.path.join(os.path.dirname(path), 'compound_peaks.csv')
    # Save the modified DataFrame back to a CSV file if needed
    df_filtered.to_csv(save_path, index=False)

    self.match_peaks()


def match_component(self, chromatogram, components_list, retention_time, uv_spectra=None, ms_spectra_peak=None):
    # check within expected expectred r.t
    # Dummy Method. NOT IMPLEMENTED
    min_elut_time = retention_time - self.settings_obj.max_peak_distance
    max_elut_time = retention_time + self.settings_obj.max_peak_distance

    for component in components_list:
        elut_time = chromatogram.time[component.elution_time]
        if min_elut_time <= elut_time <= max_elut_time:
            print("Component found with desire retention times")

        if uv_spectra and cosine_similarity(component.spectrum,
                                            uv_spectra) >= self.settings_obj.min_spectrum_correl:
            print("Component found with matching UV spectra")

        if ms_spectra_peak and ms_spectra_peak in component.ms_spectrum:
            print("Component found with desired mass")


def match_peaks(self):
    calibration_df = pd.read_csv(
        r"C:\Users\obayley\Documents\UPLCMS_Data\fgt_calibration.csv")  # Replace with your actual file path
    data_df = pd.read_csv(
        r"C:\Users\obayley\Documents\UPLCMS_Data\FGT_Samples\second_half\integral_summary.csv")  # Replace with your actual file path

    # Initialize a new column in the data DataFrame to store the assigned peak
    data_df['assigned_peak'] = None

    # Loop through each row in the data DataFrame
    for data_idx, data_row in data_df.iterrows():
        # Get the retention time of the current data peak
        data_rt = data_row['elut_time']

        # Find matching rows in the calibration DataFrame based on a 5% tolerance in retention time
        matching_calibration = calibration_df[
            (calibration_df['elut_time'] >= data_rt * 0.98) &
            (calibration_df['elut_time'] <= data_rt * 1.02)
            ]

        # If there is a match, assign the peak from the calibration DataFrame
        if not matching_calibration.empty:
            # In case there are multiple matches, we can take the first one
            matched_peak = matching_calibration.iloc[0]
            data_df.at[data_idx, 'assigned_peak'] = matched_peak['file']

    path = r"C:\Users\obayley\Documents\UPLCMS_Data"
    save_path = os.path.join(path, 'id_peaks.csv')
    # Save the modified DataFrame back to a CSV file if needed
    data_df.to_csv(save_path, index=False)


def get_conc_factor_df(self, path):
    calibration_df = pd.read_csv(path)

    # Initialize a list to store the results
    results = []

    # Group the data by 'file' (name)
    grouped = calibration_df.groupby('file')

    # Iterate over each group to calculate the average elution time and the calibration factor
    for name, group in grouped:
        # Calculate the average elution time for the group
        avg_elut_time = group['elut_time'].mean()

        # Calculate the slope (calibration factor) assuming the line passes through the origin
        slope = sum(group['conc'] * group['integral']) / sum(group['integral'] ** 2)

        # Calculate the concentration factor (inverse of slope)
        calibration_factor = 1 / slope

        # Append the results to the list
        results.append({'name': name, 'elut_time': avg_elut_time, 'concentration_factor': calibration_factor})

    # Convert the results list to a DataFrame
    result_df = pd.DataFrame(results)

    # Save the DataFrame to a CSV file
    save_path = os.path.join(os.path.dirname(path), 'correction_factor.csv')
    result_df.to_csv(save_path, index=False)

# ^^ ------ ^^ !! Trial methods used while developing better batch processing !! ^^ ------ ^^

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
            logging.error(message)

        sample_name = sample_name.replace(__old=" ", __new="_").lower()
        sample_files_list = [file for file in data_files if sample_name in file.replace(" ", "_").lower()]
        sample_files_list = sorted(sample_files_list)

        return sample_files_list

