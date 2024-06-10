#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import zipfile
import io
import rainbow as rb
import pandas as pd

class Unzipper:
    def open(self, path):

        try:
            with open(path, 'rb') as f:
                # Read the binary contents
                file_content = f.read()

                # Convert binary content to a byte stream
                file_stream = io.BytesIO(file_content)

                # Create a ZipFile object from the byte stream
                with zipfile.ZipFile(file_stream, 'r') as zip_ref:
                    # Extract all contents to a specified directory
                    zip_ref.extractall('extracted_contents_folder')
        except Exception as e:
            print (e)
    def open_uv_file(self):
        datadir = rb.read(r"C:\Users\obayley\OneDrive - UvA\Desktop\unzip_test\extracted_contents_folder.D")
        datafile = datadir.get_file("21438e09-8771-4962-b7c0-18a9a4844ad7.UV")
        print(datafile.xlabels)
        print(datafile.ylabels)
        print(datafile.data)


        # Create DataFrame
        df = pd.DataFrame(datafile.data, index=datafile.xlabels, columns=datafile.ylabels)

        # Print DataFrame
        print(df)

if __name__ == "__main__":
    path = r"C:\Users\obayley\OneDrive - UvA\Desktop\unzip_test\RoboChem Sample032024-06-06 18-59-40+02-00.dx"
    unzip = Unzipper()
    unzip.open_uv_file()

