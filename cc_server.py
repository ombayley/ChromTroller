#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: This module controls the server element of the program. It is geared
entirely towards the socket communication and offloads all commands to the Controller object.

The IP address will default to the IP of the PC running the server but can be declared if
desired. The port must be specified and should be between 1024-49151. Ports <1024 are commonly
used/priviliged ports for unix systems (avoid). Ports 49152-65535 are dynamic ports used by the
operating system (avoid). Ports use an unsigned 16-bit integer so 65,535 is the max.
"""
import socket
import threading
from cc_controller import Controller


class Server:
    def __init__(self, port=10989):
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(("", self.port))
        self.allowed_ips = ["10.10.29.199", "10.10.29.202", "10.10.29.201"]  # TODO Store these values elsewhere

        print(f"Server listening on port: {self.port}")
        self.lcms_controller = Controller(port="COM3")
        print(f"Server connected to controller")

    def listen(self):
        """
        Listen for incoming connections and handle them.
        Will only allow connections by a PC with the IP from the authorised IP list
        """
        self.server_socket.listen()
        while True:
            client_socket, client_addr = self.server_socket.accept()
            client_ip = client_addr[0]
            if client_ip in self.allowed_ips:
                print(f"Connected by {client_addr}")
                threading.Thread(target=self.handle_client, args=(client_socket,)).start()
            else:
                print(f"Rejected connection from {client_addr}")
                client_socket.close()

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
                if command == 'close server connection':
                    client_socket.sendall(b"Closing Server Connection...\n")
                    self.close()
                else:
                    response = self.lcms_controller.process_command(command)
                client_socket.sendall(response.encode())
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
