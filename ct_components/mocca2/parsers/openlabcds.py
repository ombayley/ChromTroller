#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Code by: O.Bayley

Efficiently read time, wavelength, and absorbance data from Agilent OpenLab CDS files.
"""
import io
import time
import zipfile
import struct
import numpy as np
from ct_components.mocca2.classes import Data2D

def parse_openlabcds(path):
    """
    Chemstation read and processing function.
    """
    times, wavelengths, data = get_uv_from_dx(path)
    if times is None or wavelengths is None or data is None:
        print(f"Failed to read data from: {path}")
        return None

    # Convert times from milliseconds to minutes
    times = times / 60000
    return Data2D(times, wavelengths, data.T)  # Transpose data to match expected shape

def get_uv_from_dx(dx_file_path):
    """
    Opens .dx files and returns the .uv file contained within
    """
    try:
        with zipfile.ZipFile(dx_file_path, 'r') as dx_file_unzipped:
            for subfile_name in dx_file_unzipped.namelist():
                if subfile_name.endswith('.UV'):
                    with dx_file_unzipped.open(subfile_name) as target_uv_data_file:
                        return parse_uv(target_uv_data_file.read())
    except Exception as e:
        print(f"Error reading .dx file: {e}")
        return None, None, None

def parse_uv(uv_file_data):
    """
    Parses an Agilent .uv file.
    """
    f = io.BytesIO(uv_file_data)
    head = read_string(f, 0, gap=1)

    if head == '131':
        data_offsets = {'num_times': 0x116, 'scaling_factor': 0xC0D, 'data_start': 0x1000}
        decode = decode_uv_delta if read_string(f, 347, gap=2).startswith('LC') else decode_uv_array
    elif head == '31':
        data_offsets = {'num_times': 0x116, 'scaling_factor': 0x13E, 'data_start': 0x200}
        decode = decode_uv_delta
    else:
        return None, None, None

    f.seek(data_offsets["num_times"])
    num_times = struct.unpack(">I", f.read(4))[0]
    if num_times == 0:
        return None, None, None

    f.seek(data_offsets["data_start"] + 0x8)
    start_wlen, end_wlen, delta_wlen = tuple(num // 20 for num in struct.unpack("<HHH", f.read(6)))
    wavelengths = np.arange(start_wlen, end_wlen + 1, delta_wlen)

    times, data = decode(f, data_offsets, num_times, len(wavelengths))

    f.seek(data_offsets['scaling_factor'])
    scaling_factor = struct.unpack('>d', f.read(8))[0]
    data = data * scaling_factor

    print(f"Times shape: {times.shape}")
    print(f"Wavelengths shape: {wavelengths.shape}")
    print(f"Data shape: {data.shape}")

    return times, wavelengths, data

def decode_uv_delta(f, data_offsets, num_times, num_wavelengths):
    f.seek(data_offsets["data_start"])
    times = np.empty(num_times, dtype=np.uint32)
    data = np.zeros((num_times, num_wavelengths), dtype=np.float64)

    for i in range(num_times):
        f.read(4)  # Skip 4 bytes
        times[i] = struct.unpack('<I', f.read(4))[0]
        f.read(14)  # Skip 14 bytes
        absorb_accum = 0
        for j in range(num_wavelengths):
            check_int = struct.unpack('<h', f.read(2))[0]
            if check_int == -0x8000:
                absorb_accum = struct.unpack('<i', f.read(4))[0]
            else:
                absorb_accum += check_int
            data[i, j] = absorb_accum

    return times, data

def decode_uv_array(f, data_offsets, num_times, num_wavelengths):
    f.seek(data_offsets["data_start"])
    times = np.empty(num_times, dtype=np.uint32)
    data = np.empty((num_times, num_wavelengths), dtype=np.float64)

    for i in range(num_times):
        f.read(4)  # Skip 4 bytes
        times[i] = struct.unpack('<I', f.read(4))[0]
        f.read(14)  # Skip 14 bytes
        for j in range(num_wavelengths):
            data[i, j] = struct.unpack('<d', f.read(8))[0]

    return times, data

def read_string(f, offset, gap=2):
    f.seek(offset)
    str_len = struct.unpack("<B", f.read(1))[0] * gap
    try:
        return f.read(str_len)[::gap].decode().strip()
    except Exception:
        return ""

if __name__ == '__lain__':
    path = r"C:\Users\obayley\Platform_Data\Dummy_results_dir\Internal Standard-04.dx"
    start_time = time.time()
    result = parse_openlabcds(path)
    tot_time = round(time.time() - start_time, 3)
    print(f"Time taken: {tot_time} seconds")
    if result is not None:
        print(result.time)
        print(result.wavelength)
        print(result.data)
