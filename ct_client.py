#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: An example client for connecting to the LCMS Server
"""
import socket
import os
from utils.script_utilities import load_file


class ChromTrollerClient:
    """Simple client interface to send commands to the LCMS server"""

    def __init__(self):
        ids_file = load_file(os.path.join('utils', 'private_connection_ids.json'))
        self.host_server = 'localhost' #ids_file['server_address']
        self.host_port = ids_file['socket_port']
        self.socket = self.open_connection()
        if self.socket is None:
            raise Exception("Failed to authenticate or connect to server.")

    def open_connection(self) -> socket.socket:
        """Opens the connection"""
        try:
            soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            soc.connect((self.host_server, self.host_port))
            print(f"Connecting to server at {self.host_server}:{self.host_port} ...")
            return soc
        except socket.error as e:
            print(f"Socket error: {e}")
            return None

    def send_command(self, com):
        """method to send commands from a control program to the server"""
        try:
            self.socket.sendall(com.encode())
            data = self.socket.recv(1024)
            print(f"Received: {data.decode()}")
            return data
        except Exception as e:
            print(f"Error during command transmission: {e}")

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

    def close(self):
        """Close connection with the server"""
        if self.socket:
            self.socket.close()
            print("Connection closed.")


if __name__ == "__main__":
    client = ChromTrollerClient()
    client.send_user_command()
