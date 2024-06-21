#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: An example client for connecting to the LCMS Server
"""
import socket
import os
import json


class HPLCServerClient:
    """Simple client interface to send commands to the LCMS server"""

    def __init__(self):
        # Set path to the private_connection_ids.json
        path_to_private_keys = os.path.join('utils', 'private_connection_ids.json')
        # Get connection info from private_connection_ids.json
        self.ids_file = self.load_file(path_to_private_keys)
        # Make socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Connect socket to server
        self.connect_soc_to_server()

    # -----Init Methods START-----
    @staticmethod
    def load_file(path):
        try:
            if path:
                with open(path, 'r') as file:
                    file_dict = json.load(file)
                return file_dict
        except (FileNotFoundError, json.JSONDecodeError) as err:
            raise Exception(err)

    # -----Init Methods END-----
    # -----Basic Client Methods START-----
    def connect_soc_to_server(self):
        """Opens the connection"""
        # Get connection data for the server
        host_server = 'localhost'  # self.ids_file['server_address']
        host_port = self.ids_file['socket_port']
        try:
            self.socket.connect((host_server, host_port))
            print(f"Connecting to server at {host_server}:{host_port} ...")
        except socket.error as e:
            raise Exception(f"Failed to authenticate or connect to server: {e}")

    def _send_command(self, com):
        """method to send commands from a control program to the server"""
        try:
            self.socket.sendall(com.encode())
            data = self.socket.recv(1024)
            print(f"Received: {data.decode()}")
            return data
        except Exception as e:
            print(f"Error during command transmission: {e}")

    def close(self):
        """Close connection with the server"""
        if self.socket:
            self.socket.close()
            print("Connection closed.")

    # -----BasicClient Methods END-----
    # -----Action Methods START-----

    def send_exp_detail(self, exp_info):
        response = self._send_command(f"run_info-{exp_info}")
        return response

    def get_exp_run_info(self):
        run_info = self._send_command("get_exp_run_info")
        return run_info

    def start_hplc_run(self):
        response = self._send_command("start_hplc_run")
        return response

    def get_hplc_run_status(self):
        curr_stat = self._send_command("get_hplc_run_status")
        return curr_stat

    def start_data_analysis(self):
        response = self._send_command("start_hplc_run")
        return response

    def get_analysis_status(self):
        curr_stat = self._send_command("get_status")
        return curr_stat

    # -----Action Methods END-----
    # -----Standalone User Run START-----

    def send_user_command(self):
        """method to send commands from a user to the server via cmd line interface"""
        try:
            while True:
                message = input("Enter command to send: ")  # !CHANGE input to the actual calls in the
                self.socket.sendall(message.encode())
                data = self.socket.recv(1024)
                print(f"Received: {data.decode()}")
        except KeyboardInterrupt:
            print("Client stopped by user.")
        finally:
            self.close()


if __name__ == "__main__":
    client = HPLCServerClient()
    client.send_user_command()

    # -----Standalone User Run END-----
