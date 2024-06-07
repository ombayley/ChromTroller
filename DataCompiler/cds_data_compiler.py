#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley

Takes the multiple single wavelength CSV outputs from OpenLabs CDS v2.7 and compiles it into
spectra x time data. This data exporting may change in later updates of OpenLabs CDS.
"""
import os
import re
import glob
import pandas as pd


class Compiler:
    def __init__(self):
        self.raw_data_dir_tag = re.compile(r'\.rsltcsv$')
        self.dad_3d_file_tag = re.compile(r'\.3D_UV_Data.csv$')
        self.unprocesed_data_subdir_paths = []

    def analyse(self, dir_path):
        self.find_unprocessed_data_subdir_paths(dir_path)
        print(self.unprocesed_data_subdir_paths)
        for subdir_path in self.unprocesed_data_subdir_paths:
            raw_3d_data = self.import_spectra_files(subdir_path)
            print(raw_3d_data)
            prcoessed_3d_data = self.format_data(raw_3d_data)

    def find_unprocessed_data_subdir_paths(self, dir_path):
        """
        Looks through the directory at the given path and searches for any directories that end
        with ".rsltcsv". Then it adds any sub-directories that DO NOT contain the already processed
        3D data to the unprocesed_data_subdir_paths list.
        """
        for sub_dir in next(os.walk(dir_path))[1]:
            if self.raw_data_dir_tag.search(sub_dir):
                sub_dir_path = os.path.join(dir_path, sub_dir)
                for file in next(os.walk(sub_dir_path))[2]:
                    if not self.dad_3d_file_tag.search(file):
                        self.unprocesed_data_subdir_paths.append(os.path.join(dir_path, sub_dir))

    def import_spectra_files(self, results_dir_path) -> dict:
        """
        Reads the exported UV chromatogram files (.csv) and adds this data (as a sub-dictionary) to a
        parent dictonary with the chrom_wavelength as the key.

        Returns: a dictionary of chromatogram data with the wavelength as the dictionary key
        """
        spectra_files_dict = {}
        uv_spectra_filename_pattern = re.compile(r'(.*)DAD\d+ (\d+\.\d+);\d+ Ref .*\.CSV$')
        for file in next(os.walk(results_dir_path))[2]:
            match = uv_spectra_filename_pattern.search(file)
            if match:
                chrom_wavelength = match.group(2)  # second bracket in re.compile = chrom hv
                try:
                    single_chrom_df = pd.read_csv(os.path.join(results_dir_path, file))
                    single_chrom_dict = single_chrom_df.set_index('Time').to_dict()['Absorbance']  # TODO THIS CAUSES ERROR
                    spectra_files_dict[chrom_wavelength] = single_chrom_dict
                except Exception as e:
                    print(f'Error processing file: {file} in dir: {results_dir_path}: {e}')

        return spectra_files_dict

    def format_data(self, raw_3d_data):
        """
             Converts the raw 3D data dictionary into a formatted pandas DataFrame.
             """
        if not raw_3d_data:
            return pd.DataFrame()

        # Extract retention times from the first wavelength's data
        first_key = next(iter(raw_3d_data))
        retention_times = list(raw_3d_data[first_key].keys())

        # Initialize DataFrame with retention times
        df = pd.DataFrame(retention_times, columns=['Retention Time'])

        # Add absorbance data for each wavelength
        for wavelength, values in raw_3d_data.items():
            df[wavelength] = df['Retention Time'].map(values)

        return df

    def make_3d_spectra_chromatogram(self, path) -> pd.DataFrame:
        """
        Takes the path to a .sirslt directory containing a .rsltcsv sub-directory
        of exported CSV chromatograms and assembles them into a 3D data file and df
        """
        # Initialise vars and patterns
        spectra_files_df = pd.DataFrame()
        first_file = True
        file_prefix = ""
        data_dirnames = glob.glob(os.path.join(path, "*.rsltcsv"))
        data_dir = data_dirnames[0]
        uv_spectra_filename_pattern = re.compile(r'(.*)DAD\d+ (\d+\.\d+);\d+ Ref .*\.CSV$')
        required_resolution = 1
        new_columns = {}

        # Identify spectra files
        for root, dirs, files in os.walk(data_dir):
            for file in files:
                match = uv_spectra_filename_pattern.search(file)
                if match:
                    chrom_wavelength = match.group(2)  # second bracket in re.compile = chrom hv
                    full_file_path = os.path.join(root, file)
                    if first_file:
                        spectra_files_df = self.get_time_data(full_file_path).iloc[:, 0]
                        file_prefix = match.group(1)
                        first_file = False
                    new_columns[chrom_wavelength] = self.get_absorbance_data(full_file_path).iloc[:, 0]

        spectra_files_df = pd.concat([spectra_files_df] + [pd.DataFrame({k: v}) for k, v in new_columns.items()],
                                     axis=1)

        spectra_files_df = self.interpolate_missing_wavelengths(spectra_files_df, required_resolution)

        # Save to csv in case later reprocessing is desired [Optional]
        filename = f"{file_prefix}3D_UV_Data.csv"
        output_csv = os.path.normpath(os.path.join(path, filename))  # ".." goes up directories
        spectra_files_df.to_csv(output_csv, index=False)

        return spectra_files_df

    @staticmethod
    def get_absorbance_data(path) -> pd.DataFrame:
        """
        Takes intensity data from the second column of the exported chrom CSV file
        """
        try:
            df = pd.read_csv(path, usecols=[1], header=None)  # Reads the second column
            return df
        except Exception as e:
            print(f'Error processing file at {path}: {e}')

    @staticmethod
    def get_time_data(path) -> pd.DataFrame:
        """
        Takes the time data from the first column of the exported chrom CSV file
        """
        try:
            df = pd.read_csv(path, usecols=[0], header=None)  # Reads the first column
            return df
        except Exception as e:
            print(f'Error processing file at {path}: {e}')

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


if __name__ == "__main__":
    dir_path = r"C:\Users\obayley\Documents\RoboChem_FGT_Campaign - set of 5 with duplicates.rslt"
    compiler = Compiler()
    compiler.analyse(dir_path)

    # result_dir_tag = re.compile(r'\.sirslt$')
    # raw_data_dir_tag = re.compile(r'\.rsltcsv$')
    # for dir_name in next(os.walk(dir_path))[1]:
    #     if result_dir_tag.search(dir_name):
    #         has_rsltcsv = False
    #         for subdir in next(os.walk(os.path.join(dir_path, dir_name)))[1]:
    #             if raw_data_dir_tag.search(subdir):
    #                 has_rsltcsv = True
    #                 break
    #
    #         if has_rsltcsv:
    #             print(f"Processing {dir_path}...")
    #             compiler.make_3d_spectra_chromatogram(dir_path)
    #             print(f"3D DAD data created for {os.path.basename(dir_path)}")

