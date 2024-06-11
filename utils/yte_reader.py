#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: A generic file reader to find first file bytes
"""
import io


class GenReader:
    def read_any_and_stream(self):
        path = r"C:\Users\obayley\Documents\Project_Notes\MACCO\Data\export_test\ChemStation\2024-05-08 17-31-24+02-002nm slit BP02.D\DAD1.uv"
        with open(path, 'rb') as f:
            # Read the binary contents
            file_content = f.read()
            # Convert binary content to a byte stream
            byte_stream = io.BytesIO(file_content)

            for i in range(10):
                byte = byte_stream.read(1)
                if byte:
                    print("{:02x}".format(byte[0]), end=" ")


if __name__ == "__main__":
    reader = GenReader()
    reader.read_any_and_stream()
