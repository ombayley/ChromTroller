#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley

Description: Actively monitors a specified project directory for changes. Specifically, it looks for '.sirslt'
directories to see if they contain '.csvrslt' sub-directories without a corresponding '3D_UV_Data.csv' file. If such
a case is found, it calls the data compiler to process those CSV files.

*Work in progress*
"""
from queue import Queue
import os
import re
import time
import threading
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class Monitor(FileSystemEventHandler):
    def __init__(self, monitor_queue, data_dir):
        super().__init__()
        self.monitor_thread = None
        self.observer = None
        self.is_running = False
        self.queue = monitor_queue

        self.results_dir = data_dir
        self.data_file_tag = re.compile(r'\.dx$')
        self.prior_filename_list = []
        self.wait_time = 0.5  # Sleep time between checks. Default is 500ms.

    def set_dir(self, dir_path):
        self.results_dir = dir_path

    def initial_search(self):
        """
        Initial search to set up monitoring conditions.
        """
        for filename in next(os.walk(self.results_dir))[2]:
            if self.data_file_tag.search(filename):
                self.prior_filename_list.append(filename)

    def start_monitoring(self):
        """Starts the monitoring process in a separate thread."""
        if not self.is_running:
            self.initial_search()
            self.is_running = True
            self.observer = Observer()
            self.observer.schedule(self, self.results_dir, recursive=False)

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
        if event.is_directory:
            return
        filename = os.path.basename(event.src_path)
        logging.info(f"New File identified by ct_monitor: {filename}")
        if self.data_file_tag.search(filename) and filename not in self.prior_filename_list:
            logging.info(filename)
            self.queue.put(filename)

    def stop_monitoring(self):
        """Stops the monitoring process and waits for the thread to finish."""
        self.is_running = False
        if self.observer:
            self.observer.stop()
        if self.monitor_thread:
            self.monitor_thread.join()


if __name__ == "__main__":
    queue = Queue()
    # start_time = time.time()
    monitor = Monitor(queue)
    # print(time.time()-start_time)
    monitor.set_dir(r"C:\Users\obayley\Platform_Data\Dummy_results_dir")
    print("Monitoring started.")
    monitor.start_monitoring()
    filename = queue.get()
    print(f"file found: {filename}")

