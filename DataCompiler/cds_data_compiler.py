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


def make_3d_spectra_chromatogram(path) -> pd.DataFrame:
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
                    spectra_files_df = get_time_data(full_file_path).iloc[:, 0]
                    file_prefix = match.group(1)
                    first_file = False
                new_columns[chrom_wavelength] = get_absorbance_data(full_file_path).iloc[:, 0]

    spectra_files_df = pd.concat([spectra_files_df] + [pd.DataFrame({k: v}) for k, v in new_columns.items()], axis=1)

    spectra_files_df = interpolate_missing_wavelengths(spectra_files_df, required_resolution)

    # Save to csv in case later reprocessing is desired [Optional]
    filename = f"{file_prefix}3D_UV_Data.csv"
    output_csv = os.path.normpath(os.path.join(path, filename))  # ".." goes up directories
    spectra_files_df.to_csv(output_csv, index=False)

    return spectra_files_df


def get_absorbance_data(path) -> pd.DataFrame:
    """
    Takes intensity data from the second column of the exported chrom CSV file
    """
    try:
        df = pd.read_csv(path, usecols=[1], header=None)  # Reads the second column
        return df
    except Exception as e:
        print(f'Error processing file at {path}: {e}')


def get_time_data(path) -> pd.DataFrame:
    """
    Takes the time data from the first column of the exported chrom CSV file
    """
    try:
        df = pd.read_csv(path, usecols=[0], header=None)  # Reads the second column
        return df
    except Exception as e:
        print(f'Error processing file at {path}: {e}')


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
                        df[current_wavelength_str] + df[next_wavelength_str]
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

