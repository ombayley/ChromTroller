import numpy as np

from src.ct_components.analysis_backend.classes import Data2D

def parse_labsolutions_old(path) -> Data2D:
    """Reads the .txt Lab Solutions file"""
    with open(path, "r") as f:
        text = f.read()
        start_idx = text.find("R.Time (min)")
        skip_lines = sum([ 1 for ch in text[:start_idx+1] if ch == '\n']) + 1

    raw = np.genfromtxt(path, delimiter=',', skip_header=skip_lines)

    time = raw[1:,0]
    wavelength = raw[0,1:]/100.
    data = raw[1:,1:].T/1000.
    return Data2D(time, wavelength, data)

def parse_labsolutions(path) -> Data2D:
    with open(path, 'r') as f:
        lines = f.readlines()
        section_marker = "[PDA 3D]"
        for i, line in enumerate(lines):
            if line.strip() == section_marker:
                pda3d_index = i
                break
        if pda3d_index is None:
            raise ValueError(f"Section {section_marker} not found in file.")

        lines = lines[pda3d_index:]

        section_marker = "R.Time (min)"
        for i, line in enumerate(lines):
            if line.strip() == section_marker:
                data_start_index = i+1
                break

        # Parse header information immediately following the section marker.
        header = {}
        j = 0
        while j < data_start_index and lines[j].strip():
            parts = lines[j].strip().split('\t')
            if len(parts) >= 2:
                header[parts[0]] = parts[1]
            j += 1

        # Get axis parameters (with defaults if not provided).
        start_wl = float(header.get("Start Wavelength(nm)"))
        end_wl = float(header.get("End Wavelength(nm)"))
        num_wl = int(header.get("# of Wavelength Axis Points"))

        start_time = float(header.get("Start Time(min)"))
        end_time = float(header.get("End Time(min)"))
        num_time = int(header.get("# of Time Axis Points"))
        expected_count = num_wl * num_time

        # Parse the absorbance data.
        data_value_rows = []
        wavelengths = []
        times = []

        for line_index, line in enumerate(lines[data_start_index:]):
            line = line.strip()
            tokens = line.split()
            if line.startswith('['):
                break
            if line_index ==0:
                wavelengths = [float(token)/100 for token in tokens]
            else:
                row = []
                for token_index, token in enumerate(tokens):
                    try:
                        if token_index == 0:
                            times.append(float(token))
                        else:
                            row.append(float(token))
                    except ValueError:
                        continue
                if len(row) > 0:
                    data_value_rows.append(row)
                if len(data_value_rows)*len(data_value_rows[0]) >= expected_count:
                    break

        times=np.array(times)
        wavelengths = np.array(wavelengths)

        data = np.array(data_value_rows)
        data = data.T

        # Verify the dimensions are consistent.
        assert data.shape[0] == wavelengths.shape[0], "Parsing raw data yields inconsistent shapes - wavelength"
        assert data.shape[1] == times.shape[0], "Parsing raw data yields inconsistent shapes - time"

        return Data2D(times, wavelengths, data)

