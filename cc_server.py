#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: This module controls the server element of the program. It is geared
entirely towards the socket communication and offloads all commands to the Controller object.
You should give the system the IP address (cmd prompt 'ipconfig') and select the port for
communication withing a network. 'localhost' and 1025 are good settings for the same PC.
"""
import socket
import threading
from cc_controller import Controller


class Server:
    def __init__(self, host='localhost', port=12345):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))

        self.list_of_users = ["RoboChem"]  # Piss security only implemented to prevent accidental connections.
        print(f"Server listening on {self.host}:{self.port}")
        self.lcms_controller = Controller(port="COM10")
        print(f"Server connected to controller")

    def listen(self):
        """Listen for incoming connections and handle them."""
        self.server_socket.listen()
        while True:
            client_socket, client_addr = self.server_socket.accept()
            print(f"Connected by {client_addr}")
            threading.Thread(target=self.handle_client, args=(client_socket,)).start()

    def check_credentials(self, username):
        return username in self.list_of_users

    def handle_client(self, client_socket):
        """Receive commands from a client and send them to the Arduino."""
        authenticated = False
        response = "Command Sent But No Data Returned"
        try:
            while True:  # Set to constant listen
                data = client_socket.recv(1024)
                if not data:
                    break
                command = data.decode().strip()

                if authenticated:
                    if command == 'close server connection':
                        client_socket.sendall(b"Closing Server Connection...\n")
                        self.close()
                    else:
                        response = self.lcms_controller.process_command(command)
                    client_socket.sendall(response.encode())

                if not authenticated:  # check connection starts with a user
                    authenticated = self.check_credentials(command)
                    if authenticated:
                        client_socket.sendall(b"Authentication Successful.\n")
                    else:
                        client_socket.sendall(b"Authentication Failed.\n")
                        client_socket.close()

        finally:
            client_socket.close()

    def close(self):
        """Close the server socket and Arduino connection."""
        self.server_socket.close()


if __name__ == "__main__":
    server = Server()
    try:
        server.listen()
    except KeyboardInterrupt:
        print("Shutting down the server.")
        server.close()
