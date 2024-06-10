#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley

Takes the multiple single wavelength CSV outputs from OpenLabs CDS v2.7 and compiles it into
spectra x time data. This data exporting may change in later updates of OpenLabs CDS.
"""
import os
import re
import pandas as pd


class Compiler:
    """
    Compiler class takes paths to either a campiagn directory or to a result directory and compiles
    the relevant chromatograms into a single file. Have both time and wavelength processing methods
    to give the final file the desired resolutions for downstream processing and prevention of excessive
    file size from high time resolution of the spectrometer.
    """
    def __init__(self):
        self.result_dir_tag = '.rsltcsv'
        self.result_dir_re_pat = re.compile(rf'{re.escape(self.result_dir_tag)}$')
        self.dad_3d_file_tag = '3D_UV_Data.csv'
        self.dad_3d_file_re_pat = re.compile(rf'{re.escape(self.dad_3d_file_tag)}$')
        self.chromatogram_filename_pattern = re.compile(r'(.*)DAD\d+ (\d+\.\d+);\d+ Ref .*\.CSV$')
        self.wavelength_resolution = 1
        self.retention_time_resolution = 0.01
        self.unprocesed_data_subdir_paths = []

    def compile_all_result_data(self, campaign_dir_path):
        """
        Finds all unprocessed raw data directories and creates a 3d-data file
        """
        # Get list of result directories without the corresponding 3d data
        self.find_unprocessed_data_subdir_paths(campaign_dir_path)

        # for every compiled result make a 3d data file
        for subdir_path in self.unprocesed_data_subdir_paths:
            self.compile_single_result_data(subdir_path)

    def compile_single_result_data(self, result_dir_path):
        """
        Finds all unprocessed raw data directories and creates a 3d-data file
        """
        # Read in all chromatogram files
        raw_3d_data_df = self.import_rsltcsv(result_dir_path)

        # process as desired to give desired time and wavelength resolution
        rt_res = self.retention_time_resolution
        condensed_dad_data_df = self.condense_time_intervals(raw_3d_data_df, rt_res)
        wl_res = self.wavelength_resolution
        processed_dad_data_df = self.interpolate_missing_wavelengths(condensed_dad_data_df, wl_res)

        # save compiled and processed data
        self.save_dad_data(processed_dad_data_df, result_dir_path)

    @staticmethod
    def save_dad_data(processed_dad_data_df, result_dir_path):
        try:
            processed_dad_data_df.to_csv(f"{result_dir_path}3D_UV_Data.csv", index=False)
        except Exception as e:
            print(e)

    def find_unprocessed_data_subdir_paths(self, campaign_dir_path):
        """
        Looks through the CAMPAIGN directory at the given path and searches for any RESULT subdirectories
        that end with ".rsltcsv". It then adds any sub-directories that DO NOT have a coressponding
        3D data file to the unprocesed_data_subdir_paths list.
        """
        # Makes a list of all files in the campaign directory with the 3d data tag after removing the tag
        compiled_dad_files_name_list = []
        for file_name in next(os.walk(campaign_dir_path))[2]:
            if self.dad_3d_file_re_pat.search(file_name):
                base_name = file_name.removesuffix(self.dad_3d_file_tag)
                compiled_dad_files_name_list.extend(base_name)

        # looks through all subdirs for directories ending in raw_data_dir_tag (.rsltcsv)
        for sub_dir_name in next(os.walk(campaign_dir_path))[1]:
            if self.result_dir_re_pat.search(sub_dir_name):
                base_name = sub_dir_name.removesuffix(self.result_dir_tag)
                if base_name not in compiled_dad_files_name_list:
                    sub_dir_path = os.path.join(campaign_dir_path, sub_dir_name)
                    self.unprocesed_data_subdir_paths.append(sub_dir_path)

    def import_rsltcsv(self, results_subdir_path) -> pd.DataFrame():
        """
        Gets passed a path to a single result directory ('.rsltcsv'), reads all the individual
        UV chromatogram files (.csv) and adds this data to a pd.dataframe

        Takes: path to .rsltcsv result directory
        Returns: dataframe of 3d data with absorbances by time and wavelength
        """
        # Initialize a List to hold DataFrame data
        spectra_df_list = []

        # List all csv files in the directory
        result_chrom_files = [file for file in os.listdir(results_subdir_path) if file.endswith('.CSV')]

        # Iterate through each csv file in the result dir
        for chrom_file_name in result_chrom_files:
            match = self.chromatogram_filename_pattern.search(chrom_file_name)
            if match:
                single_chrom_path = os.path.join(results_subdir_path, chrom_file_name)
                chrom_wavelength = match.group(2)  # second bracket in re.compile = chrom hv
                try:
                    # Open the Chrom file
                    single_chrom_df = pd.read_csv(single_chrom_path)

                    # Get 'Time' data if the compiled list is empty
                    if not spectra_df_list:
                        spectra_df_list.append(
                            single_chrom_df.iloc[:, [0]].rename(columns={single_chrom_df.columns[0]: 'Time'}))

                    # Add the absorbance data
                    spectra_df_list.append(
                        single_chrom_df.iloc[:, [1]].rename(columns={single_chrom_df.columns[1]: chrom_wavelength}))
                except Exception as e:
                    print(f'Error processing the data file: {chrom_file_name} in dir: {results_subdir_path}: {e}')

        # Concatenate all DataFrames along the columns. PerformanceWarning if compiled_df['x'] = single_df.iloc[:, 1]
        spectra_files_df = pd.concat(spectra_df_list, axis=1)

        return spectra_files_df

    @staticmethod
    def interpolate_missing_wavelengths(df: pd.DataFrame, resolution: float) -> pd.DataFrame:
        """
        Interpolates missing wavelength chroms in the DataFrame to ensure chromatograms at specified
        wavelength intervals by averaging data from adjacent columns, starting from the second column.

        Parameters:
        - df: DataFrame containing the compiled 3D spectra data, with the first column being time data.
        - resolution: The wavelength interval (in nm) at which chromatograms should be present.

        Returns:
        - A new DataFrame with interpolated wavelengths to meet the required resolution.
        """
        # Extract column headers, excluding the first column (time data)
        column_headers = df.columns[1:]  # Skip the first column
        wavelengths = sorted([float(col) for col in column_headers if str(col).replace('.', '', 1).isdigit()])

        # Dictionary to hold new (interpolated) columns
        new_columns = {}

        for i in range(len(wavelengths) - 1):
            current_wavelength = wavelengths[i]
            next_wavelength = wavelengths[i + 1]
            gap = next_wavelength - current_wavelength

            if gap > resolution:
                num_missing_columns = int(gap / resolution) - 1
                for j in range(num_missing_columns):
                    missing_wavelength = current_wavelength + (j + 1) * resolution
                    # Format the wavelength string consistently
                    missing_wavelength_str = f"{missing_wavelength:.1f}"
                    current_wavelength_str = f"{current_wavelength:.1f}"
                    next_wavelength_str = f"{next_wavelength:.1f}"

                    # Interpolate and store in new_columns dictionary
                    if current_wavelength_str in df.columns and next_wavelength_str in df.columns:
                        new_columns[missing_wavelength_str] = (
                                                                      df[current_wavelength_str] + df[
                                                                  next_wavelength_str]
                                                              ) / 2.0

        # Create DataFrame from new_columns and concatenate with the original DataFrame
        new_columns_df = pd.DataFrame(new_columns)
        interpolated_df = pd.concat([df, new_columns_df], axis=1)

        # Reorder columns to ensure they are in sequential order, including the time column
        time_column = df.columns[0]  # The first column is the time data
        wavelength_columns = sorted(interpolated_df.columns[1:], key=lambda x: float(x))
        ordered_columns = [time_column] + wavelength_columns
        interpolated_df = interpolated_df.loc[:, ordered_columns]

        return interpolated_df

    @staticmethod
    def condense_time_intervals(df: pd.DataFrame, time_interval: float) -> pd.DataFrame:
        """
        Condenses the DataFrame by averaging absorbance values over specified time intervals.

        Parameters:
        - df: DataFrame containing the compiled 3D spectra data, with the first column being time data.
        - time_interval: The time interval over which to average absorbance values.

        Returns:
        - A new DataFrame with averaged absorbance values over the specified time intervals.
        """
        # Copy DataFrame to avoid modifying the original
        df_copy = df.copy()

        # Determine the time range and create new time intervals
        min_time = df_copy['Time'].min()
        max_time = df_copy['Time'].max()
        new_time_points = pd.interval_range(start=min_time, end=max_time, freq=time_interval)

        # Initialize list for the new DataFrame
        averaged_data = []

        for interval in new_time_points:
            interval_data = df_copy[df_copy['Time'].between(interval.left, interval.right)]
            if not interval_data.empty:
                mean_values = interval_data.mean()
                mean_values['Time'] = interval.mid
                averaged_data.append(mean_values)

        # Create the new DataFrame
        condensed_df = pd.DataFrame(averaged_data)

        return condensed_df


if __name__ == "__main__":
    dir_path = r"C:\Users\obayley\OneDrive - UvA\Desktop\test_camp"
    compiler = Compiler()
    compiler.compile_all_result_data(dir_path)
