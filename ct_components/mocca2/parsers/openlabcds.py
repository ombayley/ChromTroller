#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Code by: O.Bayley

Read in the data produced by Agilent OpenLab CDS
"""
import io
import zipfile
import struct
import numpy as np
import pandas as pd

from ct_components.mocca2.classes import Data2D


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
    # Reset index to bring 'time' column back into the DataFrame
    df = dataframe.copy()

    # Rename the index column to 'time'
    df.rename(columns={df.columns[0]: 'time'}, inplace=True)

    # Calculate the acquisition time
    acq_time = df['time'].max() / len(df)

    # Generate new time column
    time_series = pd.Series(range(1, len(df) + 1)).astype(float) * acq_time
    df['time'] = time_series

    # Melt the DataFrame
    df = pd.melt(df, id_vars='time', value_vars=df.columns[1:],
                 var_name='wavelength', value_name='absorbance')

    # Convert 'wavelength' to float
    df['wavelength'] = df['wavelength'].astype(float)

    return df


def set_min_time_res(df, minimum_time):
    df = df.reset_index().copy()
    df.rename(columns={df.columns[0]: 'time'}, inplace=True)

    # Create a new column 'rounded_time' which rounds the 'time' column to the nearest 0.001
    df['rounded_time'] = (df['time'] / minimum_time).round() * minimum_time

    # Group by the 'rounded_time' column and calculate the mean for each group
    grouped_df = df.groupby('rounded_time').mean().reset_index()

    # Drop the original 'time' column from the grouped DataFrame to avoid duplication
    grouped_df.drop(columns=['time'], inplace=True)

    # Rename 'rounded_time' back to 'time' for clarity
    grouped_df.rename(columns={'rounded_time': 'time'}, inplace=True)

    return grouped_df


def absorbance_to_array(df):
    """
    Generates a 2D absorbance array of the absorbance values.
    """
    absorbance_array = df.absorbance.to_numpy(). \
        reshape(df.wavelength.nunique(), df.time.nunique())
    return absorbance_array


def df_to_array(df):
    """
    Takes a tidy dataframe of HPLC-DAD data and returns a numpy array of "
    absorbance values as well as a vector for the time domain and a vector for "
    the wavelength domain.
    """
    data = absorbance_to_array(df)
    time = df.time.unique()
    wavelength = df.wavelength.unique()
    return data, time, wavelength


def get_reference_signal(dataframe, bandwidth=5):
    """
    Returns the averaged signal over the last number of wavelengths as given by
    the bandwidth.
    """
    df = dataframe.copy()
    wls = df.wavelength.unique()[-bandwidth:]
    signals = []
    for wl in wls:
        signal = list(df[df['wavelength'] == wl].absorbance)
        signals.append(signal)
    mean_signal = list(map(lambda x: sum(x) / len(x), zip(*signals)))
    return pd.DataFrame({'absorbance': mean_signal})


def apply_filter(dataframe, wl_high_pass, wl_low_pass, bandwidth=2,
                 reference_wl=True):
    """
    Filters absorbance data of tidy 3D DAD dataframes to remove noise
    and background systematic error.
    """

    df = dataframe.copy()
    df['absorbance'] = df.groupby('time')['absorbance']. \
        rolling(window=bandwidth + 1, center=True). \
        mean().reset_index(0, drop=True)
    df = df.dropna().reset_index(0, drop=True)
    if reference_wl:
        n_times = len(df.time.unique())
        wls = df.wavelength.unique()
        reference_df = get_reference_signal(df)
        reference_series = reference_df.absorbance. \
            iloc[np.tile(np.arange(n_times), len(wls))].reset_index(0, drop=True)
        df['absorbance'] = df.absorbance - reference_series
    if wl_high_pass:
        df = df[df.wavelength >= wl_high_pass]
    if wl_low_pass:
        df = df[df.wavelength <= wl_low_pass]
    return df


def parse_openlabcds(path, wl_high_pass=None, wl_low_pass=None):
    """
    Chemstation read and processing function.
    """
    dx_reader = DxFileReader()
    df = dx_reader.get_uv_from_dx(path)
    # print(df)
    df = set_min_time_res(df, 0.001)
    # print(df)
    df = tidy_df_openlab(df)
    # print(df)
    df = apply_filter(df, wl_high_pass, wl_low_pass)
    # print(df)
    data, time, wavelength = df_to_array(df)
    return Data2D(time, wavelength, data)


class DxFileReader:
    def get_uv_from_dx(self, dx_file_path):
        """
        Agilent OpenLabs CDS stores 3D UV data inside .dx files which are effectively zip archives.
        This method opens these files and returns the .uv file contained within

        :param dx_file_path: path to the .dx file
        :return: .uv file contents
        """
        try:
            with open(dx_file_path, 'rb') as dx_file_binary:
                # Read the binary contents
                file_content = dx_file_binary.read()

                # Convert binary content to a byte stream
                dx_file_byte_stream = io.BytesIO(file_content)

                # Create a ZipFile object from the byte stream
                with zipfile.ZipFile(dx_file_byte_stream, 'r') as dx_file_unzipped:
                    # Find the first file ending with .UV
                    for subfile_name in dx_file_unzipped.namelist():
                        if subfile_name.endswith('.UV'):
                            # Extract the specific file and return its contents
                            with dx_file_unzipped.open(subfile_name) as target_uv_data_file:
                                times, wavelengths, data, metadata = self.parse_uv(target_uv_data_file.read())
                                uv_df = pd.DataFrame(data, index=times, columns=wavelengths)
                                return uv_df
                    else:
                        print("No files ending with .UV found in the ZIP archive")
        except Exception as e:
            print(e)
            return None

    """
    .uv PARSING METHODS

    """

    def parse_uv(self, uv_file_data):
        """
        Parses an Agilent .uv file.

        These files contain UV spectra.

        Learn more about this file format :ref:`here <uv>`.

        Args:
            path (str): Path to the Agilent .uv file.

        Returns:
            DataFile with UV data, if the file can be parsed. Otherwise, None.

        """

        f = io.BytesIO(uv_file_data)
        uint_unpack = struct.Struct('<I').unpack
        int_unpack = struct.Struct('<i').unpack
        short_unpack = struct.Struct('<h').unpack

        # Validate file header.
        head = self.read_string(f, 0, gap=1)

        if head == '131':
            data_offsets = {
                'num_times': 0x116,
                'scaling_factor': 0xC0D,
                'data_start': 0x1000
            }
            metadata_offsets = {
                "notebook": 0x35A,
                "date": 0x957,
                "method": 0xA0E,
                "unit": 0xC15,
                "signal": 0xC40,
                "vialpos": 0xFD7
            }
            file_type = self.read_string(f, 347, gap=2)
            if file_type.startswith('LC'):
                decode = self.decode_uv_delta
            elif file_type.startswith('OL'):
                decode = self.decode_uv_array
            else:
                return None
            gap = 2
        elif head == '31':
            data_offsets = {
                'num_times': 0x116,
                'scaling_factor': 0x13E,
                'data_start': 0x200
            }
            metadata_offsets = {
                "notebook": 0x18,
                "date": 0xB2,
                "method": 0xE4,
                "unit": 0x146
            }
            decode = self.decode_uv_delta
            gap = 1
        else:
            f.close()
            return None

        # Extract the number of retention times.
        f.seek(data_offsets["num_times"])
        num_times = struct.unpack(">I", f.read(4))[0]
        # If there are none, the file may be a partial.
        if num_times == 0:
            f.close()
            return self.parse_uv_partial(uv_file_data)

        # Compute the wavelengths by taking the range from
        #     the header of the first data segment
        f.seek(data_offsets["data_start"] + 0x8)
        start_wlen, end_wlen, delta_wlen = \
            tuple(num // 20 for num in struct.unpack("<HHH", f.read(6)))
        wavelengths = np.arange(start_wlen, end_wlen + 1, delta_wlen)
        num_wavelengths = wavelengths.size

        # Extract the retention times and absorbances from each data segment.
        times, data = decode(f, data_offsets, num_times, num_wavelengths)

        # Covert times to minutes.
        times = times / 60000

        # Scale the absorbances.
        f.seek(data_offsets['scaling_factor'])
        scaling_factor = struct.unpack('>d', f.read(8))[0]
        data = data * scaling_factor

        # Read file metadata.

        metadata = self.read_header(f, metadata_offsets, gap=gap)
        f.close()

        return times, wavelengths, data, metadata

    def decode_uv_delta(self, f, data_offsets, num_times, num_wavelengths):
        """

        """
        uint_unpack = struct.Struct('<I').unpack
        int_unpack = struct.Struct('<i').unpack
        short_unpack = struct.Struct('<h').unpack

        f.seek(data_offsets["data_start"])
        times = np.empty(num_times, dtype=np.uint32)
        data = np.empty((num_times, num_wavelengths), dtype=np.int64)
        for i in range(num_times):
            f.read(4)
            times[i] = uint_unpack(f.read(4))[0]
            f.read(14)
            # If the next short is equal to -0x8000
            #     then the next absorbance value is the next integer.
            # Otherwise, the short is a delta from the last absorbance value.
            absorb_accum = 0
            for j in range(num_wavelengths):
                check_int = short_unpack(f.read(2))[0]
                if check_int == -0x8000:
                    absorb_accum = int_unpack(f.read(4))[0]
                else:
                    absorb_accum += check_int
                data[i, j] = absorb_accum

        return times, data

    def decode_uv_array(self, f, data_offsets, num_times, num_wavelengths):
        uint_unpack = struct.Struct('<I').unpack

        f.seek(data_offsets["data_start"])
        times = np.empty(num_times, dtype=np.uint32)
        data = np.empty((num_times, num_wavelengths), dtype=np.float64)
        for i in range(num_times):
            f.read(4)
            times[i] = uint_unpack(f.read(4))[0]
            f.read(14)
            for j in range(num_wavelengths):
                data[i, j] = struct.unpack('<d', f.read(8))[0]

        return times, data

    def parse_uv_partial(self, path):
        """
        Parses a partial Agilent .uv file.

        Learn more about this file format :ref:`here <uv>`.

        Args:
            path (str): Path to the partial .uv file.

        Returns:
            DataFile with UV data, if the file can be parsed. Otherwise, None.

        """
        data_offsets = {
            'num_times': 0x116,
            'scaling_factor': 0xC0D,
            'data_start': 0x1000
        }

        f = open(path, 'rb')
        uint_unpack = struct.Struct('<I').unpack
        int_unpack = struct.Struct('<i').unpack
        short_unpack = struct.Struct('<h').unpack

        # Compute the wavelengths by taking the range from
        #     the header of the first data segment.
        # If this process fails, then the file is not a partial.
        f.seek(data_offsets["data_start"] + 0x8)
        try:
            start_wlen, end_wlen, delta_wlen = \
                tuple(num // 20 for num in struct.unpack("<HHH", f.read(6)))
            wavelengths = np.arange(start_wlen, end_wlen + 1, delta_wlen)
        except Exception:
            return None

        # Extract the retention times and absorbances from each data segment.
        f.seek(data_offsets['data_start'])
        times = []
        absorbances = []
        while True:
            try:
                f.read(4)
                time = uint_unpack(f.read(4))[0]
                times.append(time)
                f.read(14)
                # If the next short is equal to -0x8000
                #     then the next absorbance value is the next integer.
                # Otherwise, the short is a delta from the last absorbance value.
                absorb_accum = 0
                for _ in range(wavelengths.size):
                    check_int = short_unpack(f.read(2))[0]
                    if check_int == -0x8000:
                        absorb_accum = int_unpack(f.read(4))[0]
                    else:
                        absorb_accum += check_int
                    absorbances.append(absorb_accum)
            except Exception:
                break

        # Process the extracted values.
        times = np.array(times) / 60000
        data = np.array(absorbances).reshape((times.size, wavelengths.size))

        # Scale the absorbances.
        f.seek(data_offsets['scaling_factor'])
        scaling_factor = struct.unpack('>d', f.read(8))[0]
        data = data * scaling_factor

        # Read file metadata.
        metadata_offsets = {
            "notebook": 0x35A,
            "date": 0x957,
            "method": 0xA0E,
            "unit": 0xC15,
            "signal": 0xC40,
            "vialpos": 0xFD7
        }
        metadata = self.read_header(f, metadata_offsets)
        f.close()

        return times, wavelengths, data, metadata

    """ 
    FILE METADATA PARSING METHODS

    """

    def read_header(self, f, offsets, gap=2):
        """
        Extracts metadata from the header of an Agilent data file.

        Args:
            f (_io.BufferedReader): File opened in 'rb' mode.
            offsets (dict): Dictionary mapping properties to file offsets.
            gap (int): Distance between two adjacent characters.

        Returns:
            Dictionary containing metadata as string key-value pairs.

        """
        metadata = {}
        for key, offset in offsets.items():
            string = self.read_string(f, offset, gap)
            if string:
                metadata[key] = string
        return metadata

    def read_string(self, f, offset, gap=2):
        """
        Extracts a string from the specified offset.

        This method is primarily useful for retrieving metadata.

        Args:
            f (_io.BufferedReader): File opened in 'rb' mode.
            offset (int): Offset to begin reading from.
            gap (int): Distance between two adjacent characters.

        Returns:
            String at the specified offset in the file header.

        """
        f.seek(offset)
        str_len = struct.unpack("<B", f.read(1))[0] * gap
        try:
            return f.read(str_len)[::gap].decode().strip()
        except Exception:
            return ""


# TODO: Remove once debugging complete
if __name__ == '__main__':
    path = r"C:\Users\obayley\OneDrive - UvA\Desktop\RoboChem_FGT_Campaign - set of 5 with duplicates.rslt\Gradient362024-06-07 10-12-13+02-00.dx"
    data, time, wavelength = parse_openlabcds(path)
    print(time)
    print(wavelength)
    print(data)
    df = pd.DataFrame(data, index=wavelength, columns=time)
    df.to_csv(r"C:\Users\obayley\OneDrive - UvA\Desktop\df_test\dx_df.csv")
