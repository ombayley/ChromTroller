#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Code by: O.Bayley

Read time, wavelength, and absorbance data from Agilent OpenLab CDS .dx data files.
"""
import io
import time
import zipfile
import struct
import numpy as np
from src.analysis.classes import Data2D
from src.analysis.exceptions import ParsingError
from src.utils.logger import get_logger, Logger

log: Logger = get_logger(name='open_labs_parser')

def parse_openlabcds(file_path: str) -> Data2D:
    """
    Reads in UV Chromatographic data from OpenLabs .dx files.
    Args:
        file_path (str): path to a .dx file

    Returns:
        Data 2D object made from np.arrays
    """
    # Read in raw data with a retry and backoff system
    read_attempts = 2
    backoff_time = 2
    times, wavelengths, data = None, None, None
    for _ in range(1, read_attempts + 1):
        try:
            # attempt to read the file
            times, wavelengths, data = parse_dx(file_path)

            # Treat empty/None data as a failure
            if any(x is None for x in (times, wavelengths, data)):
                raise ParsingError("parse_dx returned no data")
            # success
            break
        except (ParsingError, PermissionError) as e:
            if _ < read_attempts:
                log.error(f"Failed to read data from: {file_path} due to: {e}. Retrying...")
                time.sleep(backoff_time)
            else:
                log.error(f"Failed to read data from: {file_path} due to: {e}.")
                raise

    # Round times and merge identical
    times = round_timings(times)
    times, data = merge_identical_times(times, data)

    return Data2D(times, wavelengths, data)


def round_timings(times_ms: np.ndarray) -> np.ndarray:
    """
    The instrument reccords data to more decimal places than it is accurate to.
    This is rounded out and the spacing is averaged to be more accurate and help with inter-run timing variations.
    Args:
        times_ms (np.ndarray): sorted np.array of times in ms

    Returns:
        times_min (np.ndarray): sorted np.array of times in min (averaged spacing)
    """
    aqq_time_ms = times_ms[-1] / len(times_ms)
    aqq_time_min = aqq_time_ms / 60000

    # Create an equal spaced time array.
    # NOTE lack of equidistant spacing can cause downstream issues in chromatogram processing
    times_min = np.arange(start=0, stop=(len(times_ms) * aqq_time_min), step=aqq_time_min)

    times_min = np.round(times_min, 3)
    return times_min


def merge_identical_times(times: np.ndarray, data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Merges all identical time points after the rounding to avoid dual data-points at the same timing
    Args:
        times (np.ndarray): times in min
        data (np.ndarray): data

    Returns:
        tuple[np.ndarray, np.ndarray]: unique_times, new_absorbance
    """

    # Find unique times and the indices of their first occurrence
    unique_times, index = np.unique(times, return_index=True)

    # Initialize new absorbance array
    new_absorbance = np.zeros((data.shape[0], len(unique_times)))

    # Aggregate absorbances for each unique time
    for i, utime in enumerate(unique_times):
        mask = (times == utime)
        if mask.any():  # Only average if there are values
            new_absorbance[:, i] = data[:, mask].mean(axis=1)

    return unique_times, new_absorbance


def parse_dx(dx_file_path: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Opens the .dx file and returns the .uv file contents contained within.
    Args:
        dx_file_path (str): path to the file to open

    Returns:
        tuple[np.ndarray, np.ndarray, np.ndarray]: times, wavelengths, data
    """
    times, wavelengths, data = None, None, None

    # Open base .dx file using zipfile
    with zipfile.ZipFile(dx_file_path, 'r') as dx_file_unzipped:
        log.info(f"dx file at: {dx_file_path} unpacked with:{dx_file_unzipped.namelist()} files")

        # Check files are contained within
        if len(dx_file_unzipped.namelist()) == 0:
            log.error(f"Failed to read data from: {dx_file_path} as no data was found within")
            raise ParsingError(f"Failed to read data from: {dx_file_path} as no data was found within")

        # Check for missing .UV file
        if not any('.UV' in s for s in dx_file_unzipped.namelist()):
            log.error(f"Failed to read data from: {dx_file_path} as no .UV file was found within")
            raise ParsingError(f"Failed to read data from: {dx_file_path} as no .UV file was found within")

        # Check through unpacked files for .UV file
        for subfile_name in dx_file_unzipped.namelist():
            if subfile_name.endswith('.UV'):
                with dx_file_unzipped.open(subfile_name) as target_uv_data_file:
                    times, wavelengths, data = parse_uv(target_uv_data_file.read())

    # Check that data was read successfully
    if any(x is None for x in (times, wavelengths, data)):
        log.error(f"Failed to read data from: {dx_file_path} due to lack of data."
                  f"\ntimes: {times}\nwavelengths: {wavelengths}\ndata: {data}")
        raise ParsingError(f"Failed to read data from: {dx_file_path} due to lack of data. See log for more")

    return times, wavelengths, data


def parse_uv(uv_file_data: bytes) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Parses the byte stream of an Agilent .uv file.
    Args:
        uv_file_data (bytes): .UV file as bytes

    Returns:
        tuple[np.ndarray, np.ndarray, np.ndarray]: times, wavelengths, data
            times: np.ndarray (miliseconds, float64)
            wavelengths: np.ndarray (nm, int)
            data: np.ndarray (absorbance, float64), indexed as [wavelength, time].
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

    return times, wavelengths, data


def decode_uv_delta(f, data_offsets, num_times, num_wavelengths):
    f.seek(data_offsets["data_start"])
    times = np.empty(num_times, dtype=np.uint32)
    data = np.zeros((num_wavelengths, num_times), dtype=np.float64)  # Transposed shape

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
            data[j, i] = absorb_accum  # Fill the transposed data array

    return times, data


def decode_uv_array(f, data_offsets, num_times, num_wavelengths):
    f.seek(data_offsets["data_start"])
    times = np.empty(num_times, dtype=np.uint32)
    data = np.empty((num_wavelengths, num_times), dtype=np.float64)  # Transposed shape

    for i in range(num_times):
        f.read(4)  # Skip 4 bytes
        times[i] = struct.unpack('<I', f.read(4))[0]
        f.read(14)  # Skip 14 bytes
        for j in range(num_wavelengths):
            data[j, i] = struct.unpack('<d', f.read(8))[0]  # Fill the transposed data array

    return times, data


def read_string(f, offset, gap=2):
    f.seek(offset)
    str_len = struct.unpack("<B", f.read(1))[0] * gap
    try:
        return f.read(str_len)[::gap].decode().strip()
    except Exception:
        return ""
