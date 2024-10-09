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
        self.expected_time = None
        self.peak_match_rt_tolerance = 0.1

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
        """Creates a settings object to store the settings data from the .json"""
        try:
            sett_dict = self.analysis_json_data["analysis_settings"]
            sett_obj = ProcessingSettings.from_dict(sett_dict)
            logging.info(f"settings object created from analysis json")
            return sett_obj
        except Exception as error:
            logging.error(f"Error: {error}")
            raise error

    def set_peak_search(self, peak_rt, rt_tolerance=0.1):
        """
        Method to set the retention time target for the peak to pick.
        Can also specify a varience in retention time.
        !THIS IS A BASIC METHOD TO HELP TEST PEAK ASSIGNMENT!
        """
        self.expected_time = peak_rt
        self.peak_match_rt_tolerance = rt_tolerance


    # -----Init Methods END----
    # -----Analysis Methods START-----

    def run_analysis(self, sample_filepath):
        """
        Central run method.
        """

        # TODO catch whether a gradient file is present !! either allow the run without or reind the user up startup
        # Identify bkg file. File tag for searching specified in analysis.json but is typically 'gradient'
        bkg_filepath = self.get_bkg_filepath(sample_filepath)

        # Create Chrom
        smpl_chromatogram = Chromatogram(sample=sample_filepath, blank=bkg_filepath, name='sample')

        # Process Chrom
        smpl_chromatogram = self.process_chrom(smpl_chromatogram)

        # Get processed data
        components = smpl_chromatogram.all_components()

        # Find all peaks within the processed data that are close to the given retetion time (within the tolerance)
        min_time = self.expected_time - self.peak_match_rt_tolerance
        max_time = self.expected_time + self.peak_match_rt_tolerance
        peaks_dict_list = []
        for component in components:
            elut_time_index = component.elution_time
            elut_time = smpl_chromatogram.time[elut_time_index]
            if min_time <= elut_time <= max_time:
                integral = component.integral
                peaks_dict_list.append({"peak_rt": elut_time, "integral": integral})
                print(f"peak at: {elut_time}\nintegral: {integral}\n")

        # Filter the peaks that were close to the given retention time
        # !!!Placeholder method for peak identification filter!!!
        closest_dict = None
        smallest_diff = float('inf')
        for dict in peaks_dict_list:
            current_time = dict["peak_rt"]
            diff = abs(current_time - self.expected_time)
            # If the current difference is smaller than the smallest_diff, update
            if diff < smallest_diff:
                smallest_diff = diff
                closest_dict = dict

        return closest_dict


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

    def get_compound_peaks (self, path):

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
        calibration_df = pd.read_csv(r"C:\Users\obayley\Documents\UPLCMS_Data\fgt_calibration.csv")  # Replace with your actual file path
        data_df = pd.read_csv(r"C:\Users\obayley\Documents\UPLCMS_Data\FGT_Samples\second_half\integral_summary.csv")  # Replace with your actual file path

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

# ^^ ------ ^^ !! Trail methods used while developing better batch processing !! ^^ ------ ^^


    def process_chrom(self, chrom):
        """
        Processes the chromatogram. NOTE: the methods using inplace rather than
        chrom = chrom.method(...) return Data2D objects not Chromatogram Objects
        """

        chrom.extract_wavelength(
            min_wavelength=self.settings_obj.min_wavelength,
            max_wavelength=self.settings_obj.max_wavelength,
            inplace=True
        )

        chrom.extract_time(
            min_time=self.settings_obj.min_elution_time,
            max_time=self.settings_obj.max_elution_time,
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
    dirpath = r"C:\Users\obayley\Documents\UPLCMS_Data\FGT_Calibration"
    analyser = Analyser()
    analyser.run_multi_analysis(dirpath)
    # analyser.trim_integral_summary(r"C:\Users\obayley\Documents\UPLCMS_Data\FGT_Calibration\integral_summary.csv")
    # analyser.match_peaks()
    # analyser.get_conc_factor_df(r"C:\Users\obayley\Documents\UPLCMS_Data\fgt_calibration.csv")