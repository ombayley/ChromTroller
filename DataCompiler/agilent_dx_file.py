#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import io
import os.path
import zipfile
import struct
import numpy as np
import pandas as pd
from DataCompiler.spectra_datafile import DataFile


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
                        print(subfile_name)
                        if subfile_name.endswith('.UV'):
                            # Extract the specific file and return its contents
                            with dx_file_unzipped.open(subfile_name) as target_uv_data_file:
                                print(target_uv_data_file)
                                times, wavelengths, data, metadata = self.parse_uv(target_uv_data_file.read())
                                uv_datafile = DataFile(dx_file_path, 'UV', times, wavelengths, data, metadata)
                                return uv_datafile
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

        return DataFile(path, 'UV', times, wavelengths, data, metadata)

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


if __name__ == "__main__":
    reader = DxFileReader()
    dir_path = r"C:\Users\obayley\OneDrive - UvA\Desktop\lcms_data\calibration for FGT additives complete.rslt"
    for file_name in next(os.walk(dir_path))[2]:
        if file_name.endswith(".dx"):
            file_path = os.path.join(dir_path, file_name)
            datafile = reader.get_uv_from_dx(file_path)
            if datafile:
                df = pd.DataFrame(datafile.data, index=datafile.xlabels, columns=datafile.ylabels)
                df.to_csv(f"{file_path}_3d_data.CSV", index=True)
                print(df)

    # file_path = r"C:\Users\obayley\OneDrive - UvA\Desktop\lcms_data\calibration for FGT additives complete.rslt\0.05 M - SM-86.dx"
    # datafile = reader.get_uv_from_dx(file_path)
    # df = pd.DataFrame(datafile.data, index=datafile.xlabels, columns=datafile.ylabels)
    # df.to_csv(f"{file_path}_3d_data.CSV", index=True)
    # print(df)
