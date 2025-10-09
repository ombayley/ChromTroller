#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: A Python-based tool for automating in-line chromatographic data analysis.
"""

import os
import json
import time
from copy import copy
from glob import glob
from typing import Any, Dict, List, Optional, Literal

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d
from src.analysis.math import cosine_similarity

# Project imports
from src.utils.get_project_path import get_project_path
from src.utils.logger import get_logger, Logger
from src.analysis.classes import Component
from src.analysis import ProcessingSettings, Chromatogram


class Analyser:
    """
    Class responsible for performing chromatographic data analysis.

    Attributes:
        log (CustomLogger): Logger for recording messages.
        settings (dict): Analysis settings loaded from a JSON file.
    """

    def __init__(self, settings: Optional[Dict[str, Any]] = None) -> None:
        self.log: Logger = get_logger("Analyser")
        self.settings: dict = settings if settings is not None else self.load_analysis_json()
        self.log.info("Analyser object initialized successfully", print_msg=True)

    def run_analysis(self, sample_filepath: str, save_data: bool = False) -> Optional[pd.DataFrame]:
        """
        Perform chromatogram analysis on a given sample file.

        Args:
            sample_filepath (str): Path to the sample chromatogram file.
            save_data (bool): Flag indicating whether to save the analysis results.

        Returns:
            Optional[pd.DataFrame]: DataFrame with peak data (columns include peak_rt, integral,
                                    peak_height, and peak_width) or None if no peaks are found.
        """
        # Identify background file using tag from settings
        bkg_filepath: Optional[str] = self.get_bkg_filepath(sample_filepath)

        # Get the raw chromatogram (with optional background correction)
        raw_chrom: Chromatogram = self.get_chrom(file_path=sample_filepath, bkg_filepath=bkg_filepath)

        self.log.info(f"Chromatogram loaded successfullyfrom {sample_filepath} with background: {bkg_filepath}", print_msg=True)

        # Process the chromatogram (e.g., wavelength extraction, baseline correction, peak detection)
        proc_chrom: Chromatogram = self.process_chrom(chrom=raw_chrom)

        # Summarize processed chromatogram into a DataFrame
        peak_data: Optional[pd.DataFrame] = self.get_df(chrom=proc_chrom)

        self.log.info(f"Identified peaks: {peak_data}", print_msg=False)

        # Add spectral matching results if peak data exists
        if peak_data is not None:
            peak_data = self.add_spectral_matches(chrom=raw_chrom, peak_data=peak_data)

        # Save analysis results if save_data is True
        if save_data:
            self.save_analysis_results(peak_data)

        return peak_data

    def get_chrom(self, file_path: str, bkg_filepath: Optional[str] = None) -> Chromatogram:
        """
        Load a chromatogram from a file with an optional background reference.

        Args:
            file_path (str): Path to the chromatogram file.
            bkg_filepath (Optional[str]): Path to the background file.

        Returns:
            Chromatogram: Loaded chromatogram object.
        """
        try:
            if bkg_filepath is not None:
                chrom = Chromatogram(sample=file_path, blank=bkg_filepath, name="sample")
                self.log.info("Chromatogram loaded WITH background reference correction")
            else:
                chrom = Chromatogram(sample=file_path, name="sample")
                self.log.info("Chromatogram loaded WITHOUT a background reference file")
            return chrom
        except Exception as e:
            self.log.error(
                f"Error loading chromatogram from {file_path} with background {bkg_filepath}: {e}",
                print_msg=True,
            )
            raise

    def get_bkg_filepath(self, sample_filepath: str) -> Optional[str]:
        """
        Find the background file recorded closest in time to the sample file.

        Args:
            sample_filepath (str): Path to the sample chromatogram file.

        Returns:
            Optional[str]: Path to the closest background file or None if not found.
        """
        dirpath = os.path.dirname(sample_filepath)
        bkg_tag = self.settings["tags"]["bkg_filename_tag"].replace(" ", "_").lower()
        data_file_tag = self.settings["tags"]["data_file_tag"].replace(" ", "_").lower()

        self.log.info(f"Searching {dirpath} for tag '{bkg_tag}' of type '{data_file_tag}'")

        # Find all candidate data files and filter for background files
        data_files = glob(os.path.join(dirpath, f"*{data_file_tag}"))
        bkg_files = [
            file for file in data_files if bkg_tag in file.replace(" ", "_").lower()
        ]

        if not bkg_files:
            self.log.info(f"No background files found in {dirpath}", print_msg=True)
            return None

        ctime_sample = os.path.getctime(sample_filepath)
        closest_bkg = min(bkg_files, key=lambda file: abs(ctime_sample - os.path.getctime(file)))
        return closest_bkg

    def process_chrom(self, chrom: Chromatogram) -> Chromatogram:
        """
        Process the chromatogram based on the analysis settings.

        Args:
            chrom (Chromatogram): Raw chromatogram object.

        Returns:
            Chromatogram: Processed chromatogram.
        """
        proc_settings: ProcessingSettings = self.get_proc_settings()  #self.proc_settings

        # Trim the chromatogram based on wavelength limits
        trimmed_data2d = chrom.extract_wavelength(
            min_wavelength=proc_settings.min_wavelength,
            max_wavelength=proc_settings.max_wavelength,
        )
        proc_chrom = Chromatogram(trimmed_data2d, name=chrom.name)

        proc_chrom = proc_chrom.correct_baseline(
            method=proc_settings.baseline_model,
            smoothness=proc_settings.baseline_smoothness,
        )


        proc_chrom = proc_chrom.find_peaks(
            contraction="max",
            min_rel_height=proc_settings.min_rel_prominence,
            min_height=proc_settings.min_prominence,
            width_at=proc_settings.border_max_peak_cutoff,
            split_threshold=proc_settings.split_threshold,
            expand_borders=True,
            merge_overlapping=True,
            min_elution_time=proc_settings.min_elution_time,
            max_elution_time=proc_settings.max_elution_time,
        )

        proc_chrom = proc_chrom.deconvolve_peaks(
            model=proc_settings.peak_model,
            min_r2=proc_settings.explained_threshold,
            relaxe_concs=proc_settings.relaxe_concs,
            max_comps=proc_settings.max_peak_comps,
        )

        return proc_chrom

    def get_df(self, chrom: Chromatogram) -> Optional[pd.DataFrame]:
        """
        Generate a DataFrame summarizing peak data from a processed chromatogram.

        Args:
            chrom (Chromatogram): Processed chromatogram object.

        Returns:
            Optional[pd.DataFrame]: DataFrame with columns:
                - peak_rt
                - integral
                - peak_height
                - peak_width
            Returns None if no peaks are detected.
        """
        components: List[Component] = chrom.all_components()
        if not components:
            self.log.info("No peaks found in chromatogram", print_msg=True)
            return None

        peaks_dict = {
            "peak_rt": [chrom.time[comp.elution_time] for comp in components],
            "integral": [round(comp.integral,2) for comp in components],
            "peak_height": [round(max(comp.concentration),2) for comp in components],
            "peak_width": [round(float(chrom.time[peak.right] - chrom.time[peak.left]), 2) for peak in chrom.peaks]
        }
        return pd.DataFrame(peaks_dict)

    def add_spectral_matches(
        self, chrom: Chromatogram, peak_data: pd.DataFrame, refs_dirpath: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Match the spectra of each detected peak to reference spectra and add similarity scores
        as new DataFrame columns.

        Args:
            chrom (Chromatogram): Chromatogram used to extract spectra.
            peak_data (pd.DataFrame): DataFrame with peak data (must include a 'peak_rt' column).
            refs_dirpath (Optional[str]): Directory path for reference spectra CSV files.

        Returns:
            pd.DataFrame: Updated DataFrame with additional columns for each reference spectrum.
        """
        dirpath = refs_dirpath or os.path.join(get_project_path(), "reference_spectra")
        ref_spectra = self.load_all_ref_spectra(dirpath)

        # Initialize new columns for each reference spectrum with NaN values
        for ref_name in ref_spectra.keys():
            peak_data[ref_name] = np.nan

        # Iterate over each peak and calculate similarity for every reference spectrum
        for idx, row in peak_data.iterrows():
            chrom_spectrum = self.get_spectrum(chrom, row["peak_rt"])
            for ref_name, ref_spec in ref_spectra.items():
                similarity = self.compare_spectra(chrom_spectrum, ref_spec)
                peak_data.at[idx, ref_name] = round(similarity, 3)  # round similarity

        return peak_data

    def add_assignments(self, peak_data: pd.DataFrame) -> pd.DataFrame:
        """
        Provides a compound assignment based on the spectral correlation and retention time
        Args:
            peak_data:

        Returns:

        """
        calib_dict = self.settings["assignment_settings"]
        assignments = []

        for _, row in peak_data.iterrows():
            peak_rt = row["peak_rt"]
            assignment = None

            for label, settings in calib_dict.items():
                rt_tolerance = settings["rt_tolerance"]
                rt = settings["rt"]
                match_id = settings["match_id"]
                min_match_correl = settings["min_match_correl"]

                # Check if retention time is within tolerance
                if abs(peak_rt - rt) <= rt_tolerance:
                    # Check if spectral correlation meets the minimum requirement
                    if row[match_id] >= min_match_correl:
                        assignment = label
                        break

            assignments.append(assignment)

        # Add the assignments to the DataFrame
        peak_data["assignment"] = assignments
        return peak_data

    def get_spectrum(
        self, chrom: Chromatogram, time: float, min_wl: Optional[float] = None, max_wl: Optional[float] = None
    ) -> pd.DataFrame:
        """
        Extract the spectrum for a specific time point from the chromatogram.

        Args:
            chrom (Chromatogram): Chromatogram to extract from.
            time (float): Target time point.
            min_wl (Optional[float]): Minimum wavelength (defaults to chrom.wavelength.min()).
            max_wl (Optional[float]): Maximum wavelength (defaults to chrom.wavelength.max()).

        Returns:
            pd.DataFrame: DataFrame with columns 'wavelength' and 'absorbance'.
        """
        if time < chrom.time.min() or time > chrom.time.max():
            raise ValueError(
                f"Target time {time} is out of range. Available range: {chrom.time.min()} to {chrom.time.max()}"
            )

        min_wl = min_wl if min_wl is not None else chrom.wavelength.min()
        max_wl = max_wl if max_wl is not None else chrom.wavelength.max()

        wavelengths = np.array([wl for wl in chrom.wavelength if min_wl <= wl <= max_wl])

        # Extract the specified wavelength range (this call may modify the chromatogram in place)
        chrom.extract_wavelength(min_wavelength=min_wl, max_wavelength=max_wl, inplace=True)

        time_idx, _ = chrom.closest_time(time)
        absorbance = chrom.data[:, time_idx]

        return pd.DataFrame({"wavelength": wavelengths, "absorbance": absorbance})

    def load_all_ref_spectra(self, dirpath: str) -> Dict[str, pd.DataFrame]:
        """
        Load all reference spectra CSV files from a directory.

        Args:
            dirpath (str): Directory containing CSV files.

        Returns:
            Dict[str, pd.DataFrame]: Dictionary mapping reference names to their spectrum DataFrames.
        """
        ref_spectra = {}
        os.makedirs(dirpath, exist_ok=True)
        for file in os.listdir(dirpath):
            if file.endswith(".csv"):
                spectrum_df = pd.read_csv(os.path.join(dirpath, file))
                name = file.split(".csv")[0]
                ref_spectra[name] = spectrum_df
        return ref_spectra

    def compare_spectra(self, spectrum1: pd.DataFrame, spectrum2: pd.DataFrame) -> float:
        """
        Compare two spectra and return a percentage similarity score.

        Args:
            spectrum1 (pd.DataFrame): Spectrum with columns 'wavelength' and 'absorbance'.
            spectrum2 (pd.DataFrame): Reference spectrum with columns 'wavelength' and 'absorbance'.

        Returns:
            float: Percentage similarity between the two spectra.
        """
        wl1, abs1 = np.array(spectrum1["wavelength"]), np.array(spectrum1["absorbance"])
        wl2, abs2 = np.array(spectrum2["wavelength"]), np.array(spectrum2["absorbance"])

        # Determine overlapping wavelength range and resample
        min_wl, max_wl = max(min(wl1), min(wl2)), min(max(wl1), max(wl2))
        common_wavelengths = np.linspace(min_wl, max_wl, 500)

        interp1 = interp1d(wl1, abs1, kind="linear", bounds_error=False, fill_value=0)
        interp2 = interp1d(wl2, abs2, kind="linear", bounds_error=False, fill_value=0)
        aligned_abs1 = interp1(common_wavelengths)
        aligned_abs2 = interp2(common_wavelengths)

        # Normalize spectra
        norm_abs1 = aligned_abs1 / np.linalg.norm(aligned_abs1)
        norm_abs2 = aligned_abs2 / np.linalg.norm(aligned_abs2)

        return self.get_similarity(norm_abs1, norm_abs2, model="cosine")

    def get_similarity(
        self,
        vec_a: np.ndarray,
        vec_b: np.ndarray,
        model: Literal["cosine", "rmse", "manhattan", "euclidean", "pearson"],
    ) -> float:
        """
        Calculate similarity between two vectors using the specified model.

        Args:
            vec_a (np.ndarray): First normalized vector.
            vec_b (np.ndarray): Second normalized vector.
            model (Literal[...]): Similarity metric ("cosine", "rmse", "manhattan", "euclidean", or "pearson").

        Returns:
            float: Similarity percentage.
        """
        if model == "cosine":
            cosine_sim = cosine_similarity(vec_a.reshape(1, -1), vec_b.reshape(1, -1))[0, 0]
            return cosine_sim * 100
        elif model == "rmse":
            rmse = np.sqrt(np.mean((vec_a - vec_b) ** 2))
            return 100 - (rmse * 100)
        elif model == "manhattan":
            manhattan_distance = np.sum(np.abs(vec_a - vec_b))
            return 100 - (manhattan_distance * 100 / len(vec_a))
        elif model == "euclidean":
            euclidean_distance = np.sqrt(np.sum((vec_a - vec_b) ** 2))
            return 100 - (euclidean_distance * 100 / len(vec_a))
        elif model == "pearson":
            correlation = np.corrcoef(vec_a, vec_b)[0, 1]
            return float(correlation) * 100
        else:
            return 0.0

    def save_spectrum_to_csv(self, spectrum_df: pd.DataFrame, filename: str) -> None:
        """
        Save a spectrum DataFrame to a CSV file.

        Args:
            spectrum_df (pd.DataFrame): DataFrame containing 'wavelength' and 'absorbance'.
            filename (str): Destination CSV file path.
        """
        path = os.path.join(get_project_path(), "reference_spectra", filename)
        spectrum_df.to_csv(path, index=False)
        self.log.info(f"Spectrum saved to {filename}", print_msg=True)

    def save_all_peak_spectra(self, chrom: Chromatogram) -> None:
        """
        Save the spectrum of each detected peak to separate CSV files.

        Args:
            chrom (Chromatogram): Chromatogram object.
        """
        for comp in chrom.all_components():
            peak_time = chrom.time[comp.elution_time]
            spectrum = self.get_spectrum(chrom, float(peak_time))
            self.save_spectrum_to_csv(spectrum, f"{peak_time}.csv")

    def save_analysis_results(self, peak_data: pd.DataFrame, name: str = None) -> None:
        """
        Save the analysis results to a CSV file and save a copy of the chromatogram.

        Args:
            peak_data (pd.DataFrame): The processed peak data
            name (str): optional name to include in the save file

        """
        timestamp = time.strftime("%Y_%m_%d-%H_%M_%S")
        day = time.strftime("%Y_%m_%d")
        save_dir = os.path.join(get_project_path(), "results", "summaries", day)
        os.makedirs(save_dir, exist_ok=True)
        name = name if name else f"{name}_"
        filename = f"{name}{timestamp}.csv"
        file_path = os.path.join(save_dir, filename)
        peak_data.to_csv(file_path)


    def save_chromatogram(self, chrom: Chromatogram) -> None:
        """
        Save the chromatogram to a CSV file.

        Args:
            chrom (Chromatogram): The chromatogram object to save.
        """
        day = time.strftime("%Y_%m_%d")
        save_dir = os.path.join(get_project_path(), "results", "chromatograms", day)
        os.makedirs(save_dir, exist_ok=True)
        ax = chrom.plot(color="black")
        fig = ax.get_figure()
        plot_label_colour= "black"
        plot_facecolour = '#ffffff'
        ax.set_title(chrom.name, color=plot_label_colour, fontsize=11)
        ax.set_xlabel("Elution Time (min)", color=plot_label_colour, fontsize=9)
        ax.set_ylabel("Absorbance", color=plot_label_colour, fontsize=9)
        ax.tick_params(axis='x', colors=plot_label_colour)
        ax.tick_params(axis='y', colors=plot_label_colour)
        fig.patch.set_facecolor(plot_facecolour)
        ax.set_facecolor(plot_facecolour)
        fig.subplots_adjust(left=0.06, right=0.98, top=0.95, bottom=0.09)
        fig.savefig(os.path.join(save_dir, chrom.name+".png"), dpi=600, bbox_inches="tight")

    def load_analysis_json(self) -> dict:
        """
        Load analysis settings from a JSON file.

        Returns:
            dict: Analysis settings.
        """
        try:
            settings_json_path = os.path.join(get_project_path(), "settings_files", "settings.json")
            with open(settings_json_path, mode="r", encoding="utf-8") as infile:
                self.log.info(f"Loaded analysis settings from {settings_json_path}")
                return json.load(infile)
        except Exception as e:
            self.log.error(f"Error loading settings JSON: {e}", print_msg=True)
            raise

    def get_proc_settings(self) -> ProcessingSettings:
        """
        Create a ProcessingSettings object from loaded JSON settings.

        Returns:
            ProcessingSettings: Object with chromatogram processing parameters.
        """
        try:
            sett_dict = copy(self.settings.get("analysis_settings", {}))
            if not sett_dict:
                raise KeyError("No 'analysis_settings' key found in the loaded JSON")
            sett_obj = ProcessingSettings.from_dict(sett_dict)
            self.log.info("Processing settings object created from analysis JSON")
            return sett_obj
        except Exception as error:
            self.log.error(f"Error creating processing settings: {error}")
            raise

    def plot_spectra(self, spectra: pd.DataFrame) -> None:
        """
        Plot a given spectrum.

        Args:
            spectra (pd.DataFrame): DataFrame with 'wavelength' and 'absorbance' columns.
        """
        plt.figure(figsize=(8, 5))
        plt.plot(spectra["wavelength"], spectra["absorbance"], label="Component")
        plt.title("Spectrum of Component")
        plt.xlabel("Wavelength")
        plt.ylabel("Absorbance/Intensity")
        plt.legend()
        plt.grid(False)
        plt.show()

    def plot_chromatogram(self, chrom: Chromatogram) -> None:
        """
        Plot a chromatogram.

        Args:
            chrom (Chromatogram): Chromatogram object.
        """
        ax = chrom.plot()
        ax.plot()
        plt.tight_layout()
        plt.show()
