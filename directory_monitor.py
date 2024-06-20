#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley

Description: Actively monitors a specified project directory for changes. Specifically, it looks for '.sirslt'
directories to see if they contain '.csvrslt' sub-directories without a corresponding '3D_UV_Data.csv' file. If such
a case is found, it calls the data compiler to process those CSV files.

*Work in progress*
"""
import os
import re
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class Monitor(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.primary_dir = None
        self.result_dir_tag = re.compile(r'\.sirslt$')
        self.raw_data_dir_tag = re.compile(r'\.rsltcsv$')
        self.dad_3d_data_file_tag = re.compile(r'\.3D_UV_Data.csv$')
        self.is_running = False
        self.wait_time = 0.5  # Sleep time between checks. Default is 500ms.

    def set_dir(self, dir_path):
        self.primary_dir = dir_path
        self.initial_search()

    def initial_search(self):
        """
        Initial search to set up monitoring conditions.
        """
        for dir_name in next(os.walk(self.primary_dir))[1]:
            if self.result_dir_tag.search(dir_name):
                self.check_directory(os.path.join(self.primary_dir, dir_name))

    def check_directory(self, dir_path):
        """
        Checks a given directory for a '.rsltcsv' sub-directory and a '3D_UV_Data.csv' file.
        """
        for filename in next(os.walk(dir_path))[2]:
            if self.dad_3d_data_file_tag.search(filename):
                return  # Exit if the 3D data file is found. No need to search further

        has_rsltcsv = False
        for subdir in next(os.walk(dir_path))[1]:
            if self.raw_data_dir_tag.search(subdir):
                has_rsltcsv = True
                break

        if has_rsltcsv:
            print(f"Processing {dir_path}...")
            make_3d_spectra_chromatogram(dir_path)
            print(f"3D DAD data created for {os.path.basename(dir_path)}")

    def start_monitoring(self):
        """Starts the monitoring process in a separate thread."""
        if not self.is_running:
            print("Monitoring started.")
            self.is_running = True
            self.observer = Observer()
            self.observer.schedule(self, self.primary_dir, recursive=True)

            # Define the target function for the thread
            def run_observer():
                self.observer.start()
                try:
                    while self.is_running:
                        time.sleep(self.wait_time)
                except KeyboardInterrupt:
                    self.observer.stop()
                self.observer.join()

            # Start the thread
            self.monitor_thread = threading.Thread(target=run_observer)
            self.monitor_thread.start()

    def on_created(self, event):
        """Handle new file/directory creation events."""
        if not event.is_directory:
            return

        path = event.src_path
        if self.result_dir_tag.search(path) or self.raw_data_dir_tag.search(path):
            parent_dir = os.path.dirname(path) if self.raw_data_dir_tag.search(path) else path
            self.check_directory(parent_dir)

    def stop_monitoring(self):
        """Stops the monitoring process and waits for the thread to finish."""
        if self.is_running:
            print("Monitoring stopped.")
            self.is_running = False
            self.observer.stop()
            self.observer.join()  # Ensure the observer thread has fully stopped
            self.monitor_thread.join()  # Wait for the monitor thread to finish

