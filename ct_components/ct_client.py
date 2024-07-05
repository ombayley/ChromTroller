#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: An example client for connecting to the LCMS Server
"""
import socket
import os
import json
import time
from dotenv import load_dotenv


class HPLCServerClient:
    """Simple client interface to send commands to the LCMS server"""

    def __init__(self):
        # Get connection info from socket_settings.json or Sensitive_data.env
        self.ids_dict = self.load_from_env()  # self.load_from_file()
        # Make socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Connect socket to server
        self.connect_soc_to_server()

    # -----Init Methods START-----
    @staticmethod
    def load_from_file():
        """Get sensitive info such as IP address/ports, etc... from json file"""
        # Set path to the socket_settings.json
        path = os.path.join('../utils', 'socket_settings.json')
        try:
            if path:
                with open(path, 'r') as file:
                    file_dict = json.load(file)
                return file_dict
        except (FileNotFoundError, json.JSONDecodeError) as err:
            raise Exception(err)

    @staticmethod
    def load_from_env():
        path_to_platform = os.path.dirname(os.path.dirname(__file__))
        dotenv_path = os.path.join(path_to_platform, 'Sensitive_data.env')
        load_dotenv(dotenv_path)
        server_address = os.getenv("SERVER_IP")
        port = int(os.getenv("SERVER_PORT"))
        return {'server_address': server_address, 'socket_port': port}

    def connect_soc_to_server(self):
        """Opens the connection"""
        # Get connection data for the server
        host_server = 'localhost'  # self.ids_file['server_address']
        host_port = self.ids_dict['socket_port']
        try:
            print(f"Connecting to server: {host_server} on port: {host_port} ...")
            self.socket.connect((host_server, host_port))
            connect_response = self._receive_from_server()
            print(connect_response)
        except socket.error as error:
            raise Exception(f"Failed to authenticate or connect to server: {error}")

    # -----Init Methods END-----
    # -----Basic Client Methods START-----

    def _send_to_server(self, com, data=None):
        """method to send commands from a control program to the server"""
        try:

            message_dict = {'command': com, 'data': data}
            message = json.dumps(message_dict).encode()
            message_length = len(message).to_bytes(4, byteorder='big')
            self.socket.sendall(message_length + message)

        except Exception as error:
            print(f"Error during command transmission: {error}")

    def _receive_from_server(self):
        """Get reply from serve. Info is passed in the same ay as the send."""
        try:
            # Check the sockect hasn't been closed
            if not self.socket:
                return "No connected Socket"

            # Read the length of the incoming message (4 bytes) then read message
            message_length_bytes = self.socket.recv(4)
            if not message_length_bytes:
                return "Empty data byte received"
            message_length = int.from_bytes(message_length_bytes, byteorder='big')
            data = self.socket.recv(message_length)

            # Read the incoming data
            if data:
                reccieved_dict = json.loads(data.decode())
                # reply_check = 'reply' in reccieved_dict['command'] # Future use - confirm data a reply
                message = reccieved_dict['data']
                return message

            return "no data found in server response"

        except Exception as error:
            print(f"Error receiving updates: {error}")

    def close(self):
        """Close connection with the server"""
        if self.socket:
            self.socket.close()
            print("Connection closed.")

    # -----BasicClient Methods END-----
    # -----CT Specific Methods START-----
    def new_run(self, name):
        self._send_to_server(com="new_run_name", data=name)

    def set_reaction_conc(self, conc):
        self._send_to_server(com="set_run_conc", data=conc)

    def add_reagents(self, reag_list):
        self._send_to_server(com="add_reagents", data=reag_list)

    def add_reaction_conditions(self, condit_dict):
        self._send_to_server(com="add_reaction_conditions", data=condit_dict)

    def start_hplc_run(self):
        self._send_to_server(com="start_hplc_run")
        return self._receive_from_server()

    def start_file_monitoring(self):
        self._send_to_server(com="start_file_monitoring")
        return self._receive_from_server()

    def run_data_analysis(self):
        self._send_to_server(com="run_data_analysis")
        return self._receive_from_server()

    # -----CT Specific Methods END-----
    # -----Standalone Method START-----


if __name__ == "__main__":
    client = HPLCServerClient()
    try:
        client.new_run(name="1")
        client.set_reaction_conc(conc=0.999)
        client.add_reagents(reag_list=['EtPh', 'BP', 'One'])
        client.add_reaction_conditions(condit_dict={'light_intensity': 35, 'residence_time': 15})

        response1 = client.start_hplc_run()
        print(response1)

        response2 = client.start_file_monitoring()
        print(response2)

        response3 = client.run_data_analysis()
        print(response3)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client.close()

    # -----Standalone Method END-----
