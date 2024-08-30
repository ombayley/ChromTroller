#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: uses netCDF4 to read .cdf files.
"""
import netCDF4 as nc
import matplotlib.pyplot as plt


def read_file():
    # Open the CDF file
    file_path = r"C:\Users\obayley\Documents\UPLCMS_Data\MS_Files\AIA\Merve - NN_20_07_MS1 +TIC SCAN ESI Frag=100V Gain=1,0_spectra.cdf"
    dataset = nc.Dataset(file_path, 'r')

    # Print basic information about the file
    print(dataset)

    # List all variables in the file
    print(dataset.variables.keys())

    # Access specific variables (replace 'variable_name' with actual variable name)
    # Example: mass_values, intensity_values, time_values etc.
    mass_values = dataset.variables['mass_values'][:]
    intensity_values = dataset.variables['intensity_values'][:]
    time_values = dataset.variables['time_values'][:]

    # Print some data
    print("Mass Values:", mass_values)
    print("Intensity Values:", intensity_values)
    print("Time Values:", time_values)
    plot(mass_values, intensity_values)
    # Close the dataset
    dataset.close()


def plot(mass_values, intensity_values):
    plt.figure(figsize=(10, 6))
    plt.plot(mass_values, intensity_values, drawstyle='steps-mid')
    plt.xlabel('m/z')
    plt.ylabel('Intensity')
    plt.title('Mass Spectrum')
    plt.show()


if __name__ == "__main__":
    read_file()
