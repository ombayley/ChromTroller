#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: O. Bayley
Description: This module controls the server element of the program. It is geared
entirely towards the socket communication and offloads all commands to the Controller object.

The IP address will default to the IP of the PC running the server but can be declared if
desired. The port must be specified and should be between 1024-49151. Ports <1024 are commonly
used/privileged ports for unix systems (avoid). Ports 49152-65535 are dynamic ports used by the
operating system (avoid). Ports use an unsigned 16-bit integer so 65,535 is the max.

The ports and IP addresses are sensitive info and are therefore stored and loaded from the
private_connection_ids.json file in the utils directory which is not git tracked.
"""
import socket
import threading
import logging
from utils.script_utilities import setup_logging, load_ids_file
from cc_controller import Controller


class Server:
    """
    Server to handle connections to different PC clients allowing them to control the LCMS
    controller system via the Controller object
    """
    def __init__(self):
        """
        Gets the id_file data, sets up the logging, connects to the controller and
        then opens the server port
        """
        # init sensitive data from id_file file
        id_file = load_ids_file()
        if id_file is None:
            logging.error("error occurred when opening the id file")
            return
        self.port = id_file['socket_port']
        self.allowed_ips = id_file['allowed_ips']

        # init logging
        setup_logging(script_name="Server")

        # Connect to the Arduino Controller
        try:
            self.lcms_controller = Controller(port=id_file['serial_port'])
        except Exception as controller_error:
            logging.error(
                "Server failed to connect to the instrument controller: %s",
                controller_error
            )
            return
        logging.info("Server successfully connected to instrument controller")

        # Open socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(("", self.port))
        logging.info("Server listening on port: %d", self.port)

    def listen(self):
        """
        Listen for incoming connections and handle them.
        Will only allow connections by a PC with the IP from the authorized IP list.
        Starts the 'Handle' process on separate thread for future implementation of
        dual-system connection but is not necessary for current use.
        """
        self.server_socket.listen()
        try:
            while True:
                try:
                    client_socket, client_addr = self.server_socket.accept()
                    client_ip = client_addr[0]
                    if client_ip in self.allowed_ips:
                        logging.info("Client: %s successfully connected", client_addr)
                        threading.Thread(target=self.handle_client, args=(client_socket,)).start()
                    else:
                        logging.info("Connection from %s rejected. IP not in IP list", client_addr)
                        client_socket.close()
                except socket.error as socket_error:
                    logging.exception("Error accepting connections: %s", socket_error)
        finally:
            self.server_socket.close()

    def handle_client(self, client_socket):
        """Receive commands from a client and send them to the Arduino via the Controller object."""
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
                    logging.info("Client command sent: %s", command)
                    response = self.lcms_controller.process_command(command)
                    logging.info("Response received: %s", response)
                    if response is None:
                        response = 'No Data Returned'
                    client_socket.sendall(response.encode())
        except socket.error as socket_error:
            logging.exception("Error accepting connections: %s", socket_error)
        finally:
            self.server_socket.close()

    def close(self):
        """Close the server socket."""
        self.server_socket.close()
        logging.info("Server socket closed.")


if __name__ == "__main__":
    server = Server()
    try:
        server.listen()
    except KeyboardInterrupt:
        print("Shutting down the server.")
        server.close()
