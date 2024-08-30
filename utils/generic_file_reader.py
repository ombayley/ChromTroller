#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import os
import stat


def read_file_header(file_path, num_bytes=16):
    """
    Reads the first 'num_bytes' of a file to get the file header.

    :param file_path: Path to the file to be analyzed.
    :param num_bytes: Number of bytes to read from the start of the file. Default is 16.
    :return: The header in hexadecimal format.
    """
    try:
        with open(file_path, 'rb') as file:
            header = file.read(num_bytes)
        print(f"First {num_bytes} bytes of Header info: {header.hex()}")
    except FileNotFoundError:
        print(f"File {file_path} not found.")
    except Exception as e:
        print(f"An error occurred: {e}")


def get_file_metadata(file_path):
    """
    Extracts basic metadata from a file.

    :param file_path: Path to the file to be analyzed.
    :return: A dictionary with basic metadata.
    """
    try:
        file_stat = os.stat(file_path)
        metadata = {
            'size': file_stat.st_size,  # File size in bytes
            'last_modified': file_stat.st_mtime,  # Last modified time
            'last_accessed': file_stat.st_atime,  # Last accessed time
            'creation_time': file_stat.st_ctime,  # Creation time
            'permissions': stat.filemode(file_stat.st_mode)  # File permissions
        }
        print(metadata)
    except FileNotFoundError:
        print(f"File {file_path} not found.")
    except Exception as e:
        print(f"An error occurred: {e}")


def read_hex_code(file_path, num_bytes=None):
    """
    Reads the hex code of a file.

    :param file_path: Path to the file to be analyzed.
    :param num_bytes: Number of bytes to read from the file. If None, read the entire file.
    :return: The hex code of the file.
    """
    try:
        with open(file_path, 'rb') as file:
            if num_bytes:
                file_content = file.read(num_bytes)
            else:
                file_content = file.read()
        print(f"Hex String: {file_content.hex()}")

        ascii_string = hex_to_ascii(file_content.hex())
        print(f"ASCII String: {ascii_string}")

    except FileNotFoundError:
        print(f"File {file_path} not found.")
    except Exception as e:
        print(f"An error occurred: {e}")


def hex_to_ascii(hex_string):
    """
    Converts a hex string to an ASCII string.

    :param hex_string: The hex string to be converted.
    :return: The ASCII representation of the hex string.
    """
    try:
        ascii_string = bytes.fromhex(hex_string).decode('latin-1')  # 'latin-1' to handle non-printable characters
        return ascii_string
    except ValueError as e:
        print(f"An error occurred during conversion: {e}")
        return None


def check_for_patterns(hex_data, pattern):
    """
    Checks for a specific pattern in the hex data.

    :param hex_data: Hexadecimal string to be analyzed.
    :param pattern: Hex pattern to search for.
    :return: List of positions where the pattern was found.
    """
    positions = []
    start = 0
    while True:
        start = hex_data.find(pattern, start)
        if start == -1:
            break
        positions.append(start)
        start += len(pattern)
    return positions


if __name__ == "__main__":
    file_path = r"C:\Users\obayley\Documents\UPLCMS_Data\FGT_Sequence_1-8-24.rslt\RoboChem_Sample_001.MSPeak.bin"
    read_file_header(file_path)
    read_hex_code(file_path, 1000)
