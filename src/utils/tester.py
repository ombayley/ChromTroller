#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: **Add Desc**.
"""
import zipfile
import re

def extract_strings(b: bytes, min_run: int = 3):
    out = []

    # 1) ASCII runs: e.g., ... D:\CDSProjects ...
    for m in re.finditer(rb"[ -~]{%d,}" % min_run, b):
        out.append(m.group().decode("ascii", "ignore"))

    # 2) UTF-16LE runs: e.g., O\x00L\x00 \x00D\x00A\x00T\x00A\x00 ...
    for m in re.finditer(rb"(?:[ -~]\x00){%d,}" % min_run, b):
        out.append(m.group().decode("utf-16-le", "ignore"))

    # Dedup while keeping order
    seen = set()
    deduped = []
    for s in out:
        s = s.strip()
        if s and s not in seen:
            seen.add(s)
            deduped.append(s)
    return deduped

def main ():
    fl_path = r"C:\Users\OllyBayley\Downloads\Recryst_of_Mereve_Crude_2025-10-07 17-09-34+02-00.dx"
    with zipfile.ZipFile(fl_path, 'r') as dx_file_unzipped:
        for subfile_name in dx_file_unzipped.namelist():
            # print(subfile_name)
            if subfile_name.endswith('.UVD'):
                with dx_file_unzipped.open(subfile_name) as target_uv_data_file:
                    return print(extract_strings(target_uv_data_file.read()))

if __name__ == "__main__":
    main()
