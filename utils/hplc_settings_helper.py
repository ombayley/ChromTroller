#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: Small tool to help with the visualisation of the 3D DAD data so that the appropriate
analysis parameters can be selected for the automated LAMA analysis.
"""
import os
import json
import tkinter as tk
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib import pyplot as plt
from ct_components.mocca2 import Chromatogram


class ChromPlotter:
    def __init__(self, parent):
        # Initialize instance variables for storing data
        self.parent = parent
        self.json_file_path = self.get_json_pathname()
        # self.sample_file_path = r"C:\Users\obayley\Platform_Data\Dummy_results_dir\0.1 M sm 01.dx"
        # self.bkg_file_path = r"C:\Users\obayley\Platform_Data\Dummy_results_dir\Gradient-03.dx"
        self.sample_file_path = r"C:\Users\obayley\Documents\Project_Notes\SuFEX\Early_Results\Merve - NN_10_02.dx"
        self.bkg_file_path = r"C:\Users\obayley\Documents\Project_Notes\SuFEX\Early_Results\Gradient_01.dx"
        self.chrom = self.get_chrom()
        self.settings = self.load_analysis_json()

        # Create figure and axes for plotting
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111)

        # Create frames
        self.create_gui_widgets()

        # Create canvas and place it inside the plot_frame
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        # Initial plot
        self.update_plot()

    # --- Init Methods START ---
    @staticmethod
    def get_json_pathname():
        project_dir = os.path.dirname(os.path.dirname(__file__))
        settings_json_path = os.path.join(project_dir, 'settings_files', 'analysis_settings.json')
        return settings_json_path

    def save_settings(self):
        # Save current settings to JSON file
        try:
            with open(self.json_file_path, 'r+', encoding='utf-8') as file:
                settings_dict = json.load(file)
                settings_dict["analysis_settings"].update(self.settings)
                file.seek(0)  # Move the file pointer to the beginning of the file
                json.dump(settings_dict, file, indent=4)
                file.truncate()  # Truncate the file to remove remaining old data
            print("Settings saved successfully.")
        except (FileNotFoundError, PermissionError, json.JSONDecodeError) as error:
            print(f"Error: {error}")

    def load_analysis_json(self) -> dict:
        """Load all analysis info from JSON file."""
        try:
            with open(self.json_file_path, mode='r', encoding='utf-8') as infile:
                settings_dict = json.load(infile)
                return settings_dict['analysis_settings']
        except (FileNotFoundError, PermissionError, json.JSONDecodeError) as error:
            print(f"Error: {error}")

    def get_chrom(self):
        chrom = Chromatogram(
            sample=self.sample_file_path,
            blank=self.bkg_file_path
        )
        return chrom

    # --- Init Methods END ---
    # --- GUI Methods START ---
    def create_gui_widgets(self):
        # Create frames
        self.plot_frame = ttk.Frame(self.parent)
        self.plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        self.bottom_frame = ttk.Frame(self.parent)
        self.bottom_frame.pack(side=tk.TOP, fill=tk.X)

        self.right_frame = ttk.Frame(self.parent)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y)

        # Create control panel 1
        cp_1 = ttk.Frame(self.bottom_frame)
        cp_1.pack(side=tk.TOP, fill=tk.X)

        # Create entry widgets for settings in cp_1
        self.min_wl_entry = self.create_entry(cp_1, "Min Wavelength", self.settings["min_wavelength"])
        self.max_wl_entry = self.create_entry(cp_1, "Max Wavelength", self.settings["max_wavelength"])
        self.min_time_entry = self.create_entry(cp_1, "Min Elution Time", self.settings["min_elution_time"])
        self.max_time_entry = self.create_entry(cp_1, "Max Elution Time", self.settings["max_elution_time"])
        self.min_height_entry = self.create_entry(cp_1, "Min Peak Height", self.settings["min_prominence"])

        # Create Update button
        update_button = ttk.Button(cp_1, text="Update Plot", command=self.update_plot)
        update_button.pack(side=tk.LEFT)

        # Create Save button
        save_button = ttk.Button(cp_1, text="Save Settings", command=self.save_settings)
        save_button.pack(side=tk.LEFT)

        # Create control panel 2
        cp_2 = ttk.Frame(self.bottom_frame)
        cp_2.pack(side=tk.TOP, fill=tk.X)

        # Create entry widgets for settings in cp_2
        self.peak_model_entry = self.create_entry(cp_2, "Peak Pick Model", self.settings['peak_model'])
        self.r2_threshold = self.create_entry(cp_2, "Min R2 for resolution", self.settings["explained_threshold"])
        self.rlx_conc = self.create_entry(cp_2, "Relax concs", self.settings["relaxe_concs"])
        self.max_comps = self.create_entry(cp_2, "Max Comp per peak", self.settings["max_peak_comps"])
        self.min_spect_correl = self.create_entry(cp_2, "Min UV correl.", self.settings["min_spectrum_correl"])

        # Create peak pick button
        pick_button = ttk.Button(cp_2, text="Pick Peaks", command=self.pick_peaks)
        pick_button.pack(side=tk.LEFT)

        # Create deconvolute button
        deconv_button = ttk.Button(cp_2, text="Deconv. Peaks", command=self.deconvolve_peaks)
        deconv_button.pack(side=tk.LEFT)

    def create_entry(self, parent, label_text, default_value):
        frame = ttk.Frame(parent)
        frame.pack(side=tk.LEFT, padx=5, pady=5)
        label = ttk.Label(frame, text=label_text)
        label.pack(side=tk.TOP)
        entry = ttk.Entry(frame)
        entry.insert(0, str(default_value))
        entry.pack(side=tk.BOTTOM)
        return entry

    def update_plot(self):
        # Update settings from entry widgets
        self.settings["min_wavelength"] = float(self.min_wl_entry.get())
        self.settings["max_wavelength"] = float(self.max_wl_entry.get())
        self.settings["min_elution_time"] = float(self.min_time_entry.get())
        self.settings["max_elution_time"] = float(self.max_time_entry.get())
        self.settings["min_prominence"] = float(self.min_height_entry.get())
        self.settings["peak_model"] = str(self.peak_model_entry.get())
        self.settings["explained_threshold"] = float(self.r2_threshold.get())
        self.settings["relaxe_concs"] = bool(self.rlx_conc.get())
        self.settings["max_peak_comps"] = int(self.max_comps.get())
        self.settings["min_spectrum_correl"] = float(self.min_spect_correl.get())

        # Clear the current plot
        self.ax.clear()

        # Re-plot with updated settings
        self.plot_chrom()
        self.plot_analysis_window()

        # Draw the updated canvas
        self.canvas.draw()

    # --- GUI Methods END ---
    # --- Chromatogram Methods START ---

    def plot_chrom(self):
        self.chrom.correct_baseline()
        self.chrom.extract_wavelength(
            min_wavelength=self.settings["min_wavelength"],
            max_wavelength=self.settings["max_wavelength"],
            inplace=True)
        self.chrom.plot(ax=self.ax)

    def plot_chrom_raw(self):
        self.chrom.plot(ax=self.ax)

    def plot_analysis_window(self):
        min_peak_height = self.settings['min_prominence']
        min_time = self.settings['min_elution_time']
        max_time = self.settings['max_elution_time']
        top = self.ax.get_ylim()[1]  # top side (top of the plot)
        # rect = plt.Rectangle(
        #     xy=(min_time, min_peak_height),
        #     width=max_time - min_time,
        #     height=top - min_peak_height,
        #     linewidth=1,
        #     facecolor='orange',
        #     alpha=0.2
        # )
        # self.ax.add_patch(rect)

    def pick_peaks(self):
        self.chrom.find_peaks(
            min_rel_height=self.settings["min_rel_prominence"],
            min_height=self.settings["min_prominence"],
            width_at=self.settings["border_max_peak_cutoff"],
            merge_overlapping=False,
            expand_borders=False,
            split_threshold=self.settings["split_threshold"],
            min_elution_time=self.settings["min_elution_time"],
            max_elution_time=self.settings["max_elution_time"]
        )
        for peak in self.chrom.peaks:
            print(f"Peak at {self.chrom.time[peak.maximum]} with height {peak.height}")
            self.ax.annotate(f'{peak.height:.2f}',
                             xy=(peak.maximum, peak.height),
                             xytext=(peak.maximum, peak.height + 0.1 * peak.height),
                             arrowprops=dict(facecolor='black', shrink=0.05),
                             horizontalalignment='center')

        self.chrom.plot(ax=self.ax)
        self.canvas.draw()

    def deconvolve_peaks(self):
        self.chrom.deconvolve_peaks(
            model=self.settings['peak_model'],
            min_r2=self.settings["explained_threshold"],
            relaxe_concs=self.settings["relaxe_concs"],
            max_comps=self.settings["max_peak_comps"]
        )
        self.chrom.plot(ax=self.ax)

# --- Chromatogram Methods END ---
# --- Standalone Methods START ---

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Chromatogram Plotter")
    plotter = ChromPlotter(root)
    root.mainloop()
