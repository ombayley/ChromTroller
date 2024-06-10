#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: Small tool to help with the visualisation of the 3D DAD data so that the appropritate
analysis parameters can be selected for the automated LAMA analysis.
"""
import tkinter as tk
from tkinter import ttk, filedialog
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import pandas as pd


class SummedChromPlotter:
    def __init__(self):
        # Initialize instance variables for storing data
        self.sample_df = None
        self.background_df = None
        self.edited_df = None
        self.start_wl = 200
        self.end_wl = 600

    def load_sample_data(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if file_path:
            self.sample_df = pd.read_csv(file_path, index_col=None)
            print("Sample data loaded.")

    def load_background_data(self):
        file_path = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        if file_path:
            self.background_df = pd.read_csv(file_path, index_col=None)
            print("Background data loaded.")

    def clear_data(self, ax, canvas):
        self.sample_df = None
        self.background_df = None
        self.edited_df = None
        ax.clear()
        ax.set_title('Absorbance Chromatogram')
        ax.set_xlabel('Time (min)')
        ax.set_ylabel('Summed Absorbance (mAu)')
        canvas.draw()


    def process_data(self):
        if self.sample_df is None:
            print("Sample data not loaded.")
            return None, None
        # Process the data even if the background is not loaded
        if self.background_df is not None:
            # Adjust this to align the sample and background data if necessary
            self.edited_df = self.sample_df.copy()
            self.edited_df.iloc[:, 1:] -= self.background_df.iloc[:, 1:]
        else:
            self.edited_df = self.sample_df

        # Extract time and wavelength from the DataFrame
        time = self.edited_df.iloc[:, 0].to_numpy()
        wavelength = self.edited_df.columns[1:].astype(float).to_numpy()

        # Find indices for the specified wavelength range
        start_index = np.searchsorted(wavelength, self.start_wl)
        end_index = np.searchsorted(wavelength, self.end_wl, side='right')

        # Sum absorbance within the specified wavelength range
        summed_absorbance = np.sum(self.edited_df.iloc[:, start_index + 1:end_index + 1], axis=1)
        return time, summed_absorbance

    def update_plot(self, ax, canvas):
        time, summed_absorbance = self.process_data()
        if time is not None and summed_absorbance is not None:
            # Clear the previous plot
            ax.clear()
            # Plot the new data
            ax.plot(time, summed_absorbance)
            ax.set_title('Absorbance Chromatogram')
            ax.set_xlabel('Time (min)')
            ax.set_ylabel('Summed Absorbance (mAu)')
            # Draw the updated plot
            canvas.draw()

    def update_data(self, start_wl_entry, end_wl_entry, ax, canvas):
        try:
            self.start_wl = float(start_wl_entry.get())
            self.end_wl = float(end_wl_entry.get())
            # print(f"Updated wavelengths to: start_wl = {self.start_wl}, end_wl = {self.end_wl}")  # Diagnostic
        except ValueError:
            print("Invalid wavelength input. Please enter a numeric value.")
        self.update_plot(ax, canvas)

    def setup_gui(self):
        root = tk.Tk()
        root.title("Absorbance Chromatogram Plotter")

        # Create a frame to hold the entries and their labels
        entry_frame = ttk.Frame(root)
        entry_frame.pack(pady=10)  # Add some padding for visual appeal
        entry_frame.columnconfigure(0, weight=1)
        entry_frame.columnconfigure(1, weight=1)

        # Start Wavelength
        start_wl_label = ttk.Label(entry_frame, text="Start Wavelength:")
        start_wl_label.grid(row=0, column=0, padx=5, sticky="w")  # 'sticky' aligns the text to the west (left)
        start_wl_entry = ttk.Entry(entry_frame)
        start_wl_entry.insert(0, str(self.start_wl))
        start_wl_entry.grid(row=1, column=0, padx=5)

        # End Wavelength
        end_wl_label = ttk.Label(entry_frame, text="End Wavelength:")
        end_wl_label.grid(row=0, column=1, padx=5, sticky="w")  # 'sticky' aligns the text to the west (left)
        end_wl_entry = ttk.Entry(entry_frame)
        end_wl_entry.insert(0, str(self.end_wl))
        end_wl_entry.grid(row=1, column=1, padx=5)

        # Frame to hold the buttons side by side
        button_frame = ttk.Frame(root)
        button_frame.pack(pady=10)  # Add some padding for visual appeal

        # Load Sample Data button
        load_sample_button = ttk.Button(button_frame, text="Load Sample Data", command=self.load_sample_data)
        load_sample_button.pack(side='left', padx=5)  # Pack the button on the left side

        # Load Background Data button
        load_background_button = ttk.Button(button_frame, text="Load Background Data",
                                            command=self.load_background_data)
        load_background_button.pack(side='left', padx=5)  # Pack the button next to the first, on the left side

        # Clear button
        clear_button = ttk.Button(button_frame, text="Clear", command=lambda: self.clear_data(ax, canvas))
        clear_button.pack(side='left', padx=5)

        # Plot button
        plot_button = ttk.Button(button_frame, text="Plot",
                                 command=lambda: self.update_data(start_wl_entry, end_wl_entry, ax, canvas))
        plot_button.pack(side='left', padx=5)

        # Ensure ax and canvas are accessible for update_plot
        fig = Figure(figsize=(5, 5), dpi=100)
        ax = fig.add_subplot(111)
        canvas = FigureCanvasTkAgg(fig, master=root)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack()

        return root

    def main(self):
        root = self.setup_gui()
        root.mainloop()


if __name__ == "__main__":
    plotter = SummedChromPlotter()
    plotter.main()
