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
import json
import os
from datetime import datetime
from ct_controller import Controller


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
        # Setup Log
        self.setup_logging()
        # Get sensitive data from id_file file
        self.id_file = self.load_ids_file()
        # Connect to the Arduino Controller
        self.lcms_controller = self.init_controller()
        # Open socket
        self.server_socket = self.init_socket()

    # -----Init Methods START-----
    @staticmethod
    def setup_logging():
        """ Sets log format and file destination """
        # Set path to the 'logs' directory.
        root_dir_path = os.path.dirname(os.path.abspath(__file__))
        log_dir_path = os.path.join(root_dir_path, 'logs')

        # Ensure the logs directory exists
        os.makedirs(log_dir_path, exist_ok=True)

        # Set the log file name
        date_str = datetime.now().strftime("%d-%m-%Y--%H-%M-%S")
        log_file_name = f"ChromTroller_{date_str}_logfile.log"
        log_file_path = os.path.join(log_dir_path, log_file_name)

        # Set up logging configuration
        logging.basicConfig(
            filename=log_file_path,
            level=logging.INFO,
            format=f'%(asctime)s - %(levelname)s - %(filename)s - %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S',
            filemode='w'  # w=write, a=append
        )

    @staticmethod
    def load_ids_file(secure_id_file_path=None):
        """Read in the (private) connection data. """
        try:
            if secure_id_file_path is None:
                secure_id_file_path = os.path.join('utils', 'private_connection_ids.json')
            with open(secure_id_file_path, 'r') as ids_file:
                config = json.load(ids_file)
            return config
        except (FileNotFoundError, json.JSONDecodeError, PermissionError) as err:
            logging.error(err)

    def init_controller(self):
        """Initialise the controller object"""
        try:
            controller = Controller(port=self.id_file['serial_port'])
        except Exception as err:
            logging.error("Failed to connect to controller: %s", err)
            return
        logging.info("Server successfully connected to instrument controller")
        return controller

    def init_socket(self):
        """Initialise socket"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(("", self.id_file['socket_port']))
        logging.info("Server listening on port: %d", self.id_file['socket_port'])
        return server_socket

    # -----Init Methods END-----
    # -----Server Methods START -----

    def listen(self):
        """
        Listen for incoming connections and handle them.
        Will only allow connections by a PC with the IP from the authorized IP list.
        """
        self.server_socket.listen()
        while True:
            try:
                client_socket, client_addr = self.server_socket.accept()
                client_ip = client_addr[0]
                if client_ip in self.id_file['allowed_ips']:
                    logging.info("Client: %s successfully connected", client_addr)
                    threading.Thread(target=self.handle_client, args=(client_socket,)).start()
                else:
                    logging.info("Connection from %s rejected. IP not in IP list", client_addr)
                    client_socket.close()
            except socket.error as socket_error:
                logging.exception("Error accepting connections: %s", socket_error)

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
                    logging.info("Command received from client: %s", command)
                    response = self.handle_command(command)
                    logging.info("Response sent back to client: %s", response)
                    if response is None:
                        response = 'No Data Returned'
                    client_socket.sendall(response.encode())
        except socket.error as socket_error:
            logging.exception("Error accepting connections: %s", socket_error)
        # finally:
        #     self.server_socket.close()  # this causes a bug when executed

    def close(self):
        """Close the server socket."""
        self.server_socket.close()
        logging.info("Server socket closed.")

    # -----Server Methods END-----
    # -----Action Methods START -----

    def handle_command(self, command):
        if "Run Info:" in command:
            self.interaction_log(command)
        if command == "Analyse":
            resp = self.lcms_controller.process_command(command)
            self.interaction_log(resp)
            self.wait_on_file()
            analysis_obj = LamsAnalysis(data_dir_path, anal_json_path)
            analysis_obj.prepare_analysis()
            # analysis_obj.load_analysis_pkl()
            analysis_obj.run_analysis()

    # -----Action Methods END -----

if __name__ == "__main__":
    server = Server()
    try:
        server.listen()
    except KeyboardInterrupt:
        logging.info("Shutting down the server.")
        server.close()
