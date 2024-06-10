#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Code by: O.Bayley

Read in the data produced by Agilent OpenLab CDS
"""
import os
import re
import pandas as pd
from LAMA.LCMSLama.dad_data.apis.cdsutils import make_3d_spectra_chromatogram
from LAMA.LCMSLama.dad_data.utils import df_to_array, apply_filter


def read_csv_openlab(path):
    """
    Reads the exported CSV files from the OpenLabs CDS processing method. First checks if a
    processed 3D data file is present if not it will generate one from the series of CSV files
    Parameters
    ----------
    path : str
        The directory, in which the experimental data is stored.

    Returns
    -------
    df : pandas.DataFrame
        First column is time, the following columns obtain the absorbance
        values at the given detection wavelength in the column name.
    """

    if check_3d_data_exists(path):
        pattern = re.compile(r'.*3D_UV_Data\.csv$')
        matching_files = [entry.path for entry in os.scandir(path) if entry.is_file() and pattern.match(entry.name)]
        with open(os.path.join(path, matching_files[0]), 'r', encoding='utf-8') as uv_data_file:
            uv_data_df = pd.read_csv(uv_data_file)
        return uv_data_df

    uv_data_df = make_3d_spectra_chromatogram(path)
    return uv_data_df


def check_3d_data_exists(path) -> bool:
    """
    Checks whether the 3D data has already been generated to save any reprocessing
    """
    proc_data_tag_3d_uv = re.compile(r'.*3D_UV_Data.csv')
    for root, dirs, files in os.walk(path):
        for file in files:
            match = proc_data_tag_3d_uv.search(file)
            if match:
                return True
    return False


def check_csv_data_exists(path) -> bool:
    """
    Checks the dir with raw CSV data is present.
    """
    raw_data_tag_3d_uv = re.compile(r'.*rsltcsv')
    for root, dirs, files in os.walk(path):
        for dir in dirs:
            match = raw_data_tag_3d_uv.search(dir)
            if match:
                return True
    return False


def tidy_df_openlab(dataframe, wl_high_pass=None, wl_low_pass=None):
    """
    Tidies the raw data obtained from reading the CSV

    Parameters
    ----------
    dataframe : pandas.DataFrame
        First column is time, the following columns obtain the absorbance
        values at the given detection wavelength in the column name.

    Raises
    ------
    ValueError
        If acquisition rate of the DAD was not constant, this error is raised.

    Returns
    -------
    df : pandas.DataFrame
        Columns:
            time: Chromatogram time
            wavelength: Detection wavelength
            absorbance: Absorbance value
    """
    df = dataframe.copy()
    # name time column
    df.rename(columns={df.columns[0]: 'time'}, inplace=True)

    acq_time = df.time.max() / len(df)

    # generate new time column
    time_series = pd.Series(range(1, (len(df) + 1))).astype(float) * acq_time
    df['time'] = time_series
    df = pd.melt(df, id_vars='time', value_vars=df.columns[1:],
                 var_name='wavelength', value_name='absorbance')
    df['wavelength'] = df['wavelength'].astype(float)
    return df


def read_openlabcds(path, wl_high_pass=None, wl_low_pass=None):
    """
    Chemstation read and processing function.
    """
    df = read_csv_openlab(path)
    df = tidy_df_openlab(df)
    df = apply_filter(df, wl_high_pass, wl_low_pass)
    data, time, wavelength = df_to_array(df)
    return data, time, wavelength


# TODO: Remove once debugging complete
if __name__ == '__main__':
    path = r"C:\Users\obayley\Platform_Data\Olly_Test\Test11\LCMS_data\2024-02-29 18-27-22+01-00gradient.sirslt"
    data1, time1, wavelength1 = read_openlabcds(path)
    df1 = pd.DataFrame(data1)
    output_csv = (os.path.join(r"C:\Users\obayley\Platform_Data\check_folder", "openlab_gradient_data.csv"))
    df1.to_csv(output_csv, index=False)

    path = r"C:\Users\obayley\Platform_Data\Olly_Test\Test11\LCMS_data\2024-02-29 18-32-33+01-005mM_TMB.sirslt"
    data2, time2, wavelength2 = read_openlabcds(path)
    df2 = pd.DataFrame(data2)
    output_csv = (os.path.join(r"C:\Users\obayley\Platform_Data\check_folder", "openlab_istd_data.csv"))
    df2.to_csv(output_csv, index=False)

    df3 = df2-df1
    output_csv = (os.path.join(r"C:\Users\obayley\Platform_Data\check_folder", "openlab_corrected_istd_data.csv"))
    df3.to_csv(output_csv, index=False)
