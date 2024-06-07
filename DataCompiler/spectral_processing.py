#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: *Brief script description*.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, peak_widths
from scipy.integrate import simps


class SpectralAnalyser:
    def baseline_correction(self, chromatogram, deg=3):
        """
        Perform a polynomial baseline correction on the chromatogram.
        """
        x = np.arange(len(chromatogram))
        coeffs = np.polyfit(x, chromatogram, deg)
        baseline = np.polyval(coeffs, x)
        corrected = chromatogram - baseline
        return corrected, baseline

    def find_peaks_above_threshold(self,chromatogram, threshold):
        """
        Find peaks in the chromatogram that are above the specified threshold.
        """
        peaks, _ = find_peaks(chromatogram, height=threshold)
        return peaks

    def integrate_peaks(self, chromatogram, peaks, width):
        """
        Integrate the area under each peak in the chromatogram.
        """
        peak_areas = []
        for peak in peaks:
            start = max(peak - width, 0)
            end = min(peak + width, len(chromatogram) - 1)
            area = simps(chromatogram[start:end], dx=1)
            peak_areas.append(area)
        return peak_areas

    def analyze_chromatogram(self, df, column_name, threshold, baseline_deg=3, peak_width=10):
        """
        Analyze the chromatogram to baseline correct, find peaks, and integrate areas.
        """
        chromatogram = df[column_name].values
        corrected_chromatogram, baseline = baseline_correction(chromatogram, baseline_deg)
        peaks = find_peaks_above_threshold(corrected_chromatogram, threshold)
        peak_areas = integrate_peaks(corrected_chromatogram, peaks, peak_width)

        return corrected_chromatogram, baseline, peaks, peak_areas

    def plot_chromatogram(self, df, column_name, corrected_chromatogram, baseline, peaks, peak_areas):
        """
        Plot the original and corrected chromatograms, along with identified peaks.
        """
        x = df.index
        original_chromatogram = df[column_name].values

        plt.figure(figsize=(12, 6))

        plt.subplot(2, 1, 1)
        plt.plot(x, original_chromatogram, label='Original Chromatogram')
        plt.plot(x, baseline, label='Baseline', linestyle='--')
        plt.title('Original Chromatogram with Baseline')
        plt.legend()

        plt.subplot(2, 1, 2)
        plt.plot(x, corrected_chromatogram, label='Corrected Chromatogram')
        plt.plot(peaks, corrected_chromatogram[peaks], "x", label='Peaks')
        for i, peak in enumerate(peaks):
            plt.annotate(f'Area: {peak_areas[i]:.2f}', (peak, corrected_chromatogram[peak]), textcoords="offset points",
                         xytext=(0, 10), ha='center')
        plt.title('Corrected Chromatogram with Peaks')
        plt.legend()

        plt.tight_layout()
        plt.show()

    # Example usage
    # Assuming df is a DataFrame with a column 'signal' containing the chromatogram data

    df = pd.DataFrame({
        'time': np.linspace(0, 100, 1000),
        'signal': np.random.randn(1000) + np.sin(np.linspace(0, 10 * np.pi, 1000)) ** 2
    })

    corrected_chromatogram, baseline, peaks, peak_areas = analyze_chromatogram(df, 'signal', threshold=0.5)

    plot_chromatogram(df, 'signal', corrected_chromatogram, baseline, peaks, peak_areas)
