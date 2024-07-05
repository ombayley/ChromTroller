#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: An example client for connecting to the LCMS Server
"""
import socket
import os
import json
import asyncio


class HPLCServerClient:
    """Simple client interface to send commands to the LCMS server"""

    def __init__(self):
        # Set path to the socket_settings_private.json
        path_to_private_keys = os.path.join('../utils', 'socket_settings_private.json')
        # Get connection info from socket_settings_private.json
        self.ids_file = self.load_file(path_to_private_keys)
        # Make socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Connect socket to server
        self.connect_soc_to_server()
        # Initialize the event loop
        self.loop = asyncio.get_event_loop()
        # Listen to Server
        self.listen_to_serv = True

    # -----Init Methods START-----
    @staticmethod
    def load_file(path):
        """Get sensitive info such as IP address/ports, etc... from json file"""
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

    def _send_command(self, com, data=None):
        """method to send commands from a control program to the server"""
        try:
            message_dict = {'command': com, 'data': data}
            message = json.dumps(message_dict).encode()
            message_length = len(message).to_bytes(4, byteorder='big')
            self.socket.sendall(message_length + message)
        except Exception as e:
            print(f"Error during command transmission: {e}")

    def close(self):
        """Close connection with the server"""
        if self.socket:
            self.socket.close()
            print("Connection closed.")

    # -----BasicClient Methods END-----
    # -----Streaming Methods START-----
    async def listen_for_updates(self):
        """Listen for updates from the server."""
        while self.listen_to_serv:
            try:
                data = await self.loop.sock_recv(self.socket, 1024)
                if data:
                    message = data.decode()
                    print(f"Update from server: {message}")
                    if message == 'TERMINATE':
                        self.listen_to_serv = False
            except Exception as e:
                print(f"Error receiving updates: {e}")
                break

    async def close_async(self):
        """Close connection with the server asynchronously."""
        if self.socket:
            self.socket.close()
            print("Connection closed.")

    # -----Streaming Methods END-----
    # -----CT Specific Methods START-----
    def new_run(self, name):
        self._send_command(com="new_run_name", data=name)

    def set_reaction_conc(self, conc):
        self._send_command(com="set_run_conc", data=conc)

    def add_reagents(self, reag_list):
        self._send_command(com="add_reagents", data=reag_list)

    def add_reaction_conditions(self, condit_dict):
        self._send_command(com="add_reaction_conditions", data=condit_dict)

    def start_hplc_run(self):
        self._send_command(com="start_hplc_run")

    # -----CT Specific Methods END-----
    # -----Standalone Method START-----

    def listen(self):
        try:
            self.loop.run_until_complete(self.listen_for_updates())
        except KeyboardInterrupt:
            print("Interrupted by user.")
        finally:
            self.loop.run_until_complete(self.close_async())


if __name__ == "__main__":
    client = HPLCServerClient()
    client.new_run(name="1")
    client.set_reaction_conc(conc=0.1)
    client.add_reagents(reag_list=['EtPh', 'BP', 'One'])
    client.add_reaction_conditions(condit_dict={'light_intensity': 35, 'residence_time': 15})
    client.start_hplc_run()
    client.listen()

    # -----Standalone Method END-----
