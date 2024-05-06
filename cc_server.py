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
import logging
from utils.script_utilities import setup_logging, load_config_file
from cc_controller import Controller


class Server:
    def __init__(self):
        config = load_config_file()
        self.port = config['socket_port']
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(("", self.port))
        self.allowed_ips = config['allowed_ips']
        setup_logging(script_name="Server")

        logging.info(f"Server listening on port: {self.port}")
        self.lcms_controller = Controller(port=config['serial_port'])
        logging.info(f"Server connected to controller")

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
                logging.info(f"Client: {client_addr} successfully connected")
                threading.Thread(target=self.handle_client, args=(client_socket,)).start()
            else:
                logging.info(f"Connection from {client_addr} rejected as IP is not in allowed list")
                client_socket.close()

    def handle_client(self, client_socket):
        """Receive commands from a client and send them to the Arduino."""
        response = "No Data Returned"
        try:
            while True:  # Set to constant listen
                data = client_socket.recv(1024)
                if not data:
                    break
                command = data.decode().strip()
                if command == 'close server connection':
                    logging.info("Client initiated disconnection")
                    client_socket.sendall(b"Closing Server Connection...\n")
                    self.close()
                    logging.info("Client disconnected")
                else:
                    logging.info(f"Client command sent: {command}")
                    response = self.lcms_controller.process_command(command)
                    logging.info(f"Response received: {response}")
                client_socket.sendall(response.encode())
        finally:
            client_socket.close()

    def close(self):
        """Close the server socket."""
        self.server_socket.close()


if __name__ == "__main__":
    server = Server()
    try:
        server.listen()
    except KeyboardInterrupt:
        print("Shutting down the server.")
        server.close()
