#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Original code by: HaasCP
Source: https://github.com/HaasCP/mocca
Licensed under the MIT License

Modified code for the LAMA package by: O.Bayley
"""
import os
import pandas as pd

from LAMA.LCMSLama.dad_data.utils import df_to_array, apply_filter


def read_csv_agilent(path):
    """
    Reads the UTF-16 encoded 3D data exported by the ChemStation macro.
    Parameters
    ----------
    path : str
        The directory, in which the experimental data are stored.

    Returns
    -------
    df : pandas.DataFrame
        First column is time, the following columns obtain the absorbance
        values at the given detection wavelength in the column name.
    """
    with open(os.path.join(path, 'DAD1.CSV'), 'r', encoding='utf-16') as f:
        df = pd.read_csv(f)
    return df


def tidy_df_agilent(dataframe, wl_high_pass=None, wl_low_pass=None):
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


def read_chemstation(path, wl_high_pass=None, wl_low_pass=None):
    """
    Chemstation read and processing function.
    """
    df = read_csv_agilent(path)
    df = tidy_df_agilent(df)
    df = apply_filter(df, wl_high_pass, wl_low_pass)
    data, time, wavelength = df_to_array(df)
    return data, time, wavelength


# TODO: Remove once debugging complete
if __name__ == '__main__':
    path = r"C:\Users\obayley\Platform_Data\Olly_Test\Test1\HPLC_data\2022-01-26_19-43-27_gradient.D"
    data1, time1, wavelength1 = read_chemstation(path)
    df1 = pd.DataFrame(data1)
    path = r"C:\Users\obayley\Platform_Data\Olly_Test\Test1\HPLC_data\2022-01-26_19-48-52_ba_1.D"
    data2, time2, wavelength2 = read_chemstation(path)
    df2 = pd.DataFrame(data2)
    df3 = df2 - df1
    filename = "chemstation_corrected_istd_data.csv"
    output_csv = (os.path.join(r"C:\Users\obayley\Platform_Data\check_folder", filename))
    df3.to_csv(output_csv, index=False)
