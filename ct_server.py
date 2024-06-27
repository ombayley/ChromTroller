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


class Server:
    """
    Server to handle connections to different PC clients allowing them to control the LCMS
    controller system via the Controller object
    """

    def __init__(self, chromtroller):
        """
        Gets the id_file data, sets up the logging, connects to the controller and
        then opens the server port
        """
        # Setup Logging
        self._setup_logging()
        # Create reference to main program
        self.ct_program = chromtroller
        # Get sensitive data from id_file file
        self.id_file = self.load_private_ids_file()
        # Create server socket
        self.server_socket = self.init_socket()

    # -----Init Methods START-----
    @staticmethod
    def _setup_logging():
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

    # --

    @staticmethod
    def load_private_ids_file(secure_id_file_path=None):
        """Read in the (private) connection data. """
        try:
            if secure_id_file_path is None:
                secure_id_file_path = os.path.join('utils', 'private_connection_ids.json')
            with open(secure_id_file_path, 'r') as ids_file:
                config = json.load(ids_file)
                logging.info("Server loaded connection ids from .json file successfully")
            return config
        except (FileNotFoundError, json.JSONDecodeError, PermissionError) as err:
            logging.error(err)

    # --

    def init_socket(self):
        """Initialise socket"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(("", self.id_file['socket_port']))
        logging.info(f"Server listening on port: {self.id_file['socket_port']}")
        return server_socket

    # -----Init Methods END-----
    # -----Server Methods START -----

    def listen_for_new_connections(self):
        """
        Listen for incoming connections and handle them on seperate thread.
        Will only allow connections by a PC with the IP from the authorized IP list.
        """
        self.server_socket.listen()
        while True:
            try:
                # Get connection info
                client_socket, client_addr = self.server_socket.accept()
                client_ip = client_addr[0]
                # Check valid IP address
                if client_ip in self.id_file['allowed_ips']:
                    date_str = datetime.now().strftime("%d-%m-%Y--%H-%M-%S")
                    logging.info(f"Client: {client_addr} connected - {date_str}")
                    # Handle client on new thread
                    threading.Thread(target=self.handle_client, args=(client_socket,)).start()
                else:
                    logging.info(f"Connection from {client_addr} rejected. IP not in IP list")
                    client_socket.close()
            except socket.error as socket_error:
                logging.exception("Error accepting connections: %s", socket_error)

    # --

    def handle_client(self, client_socket):
        """Receive commands from a client and handle."""
        try:
            while True:
                # Connection + Data = action, Connection + No Data = wait, No Connection = break
                # .recv() is blocking but client sends empty byte (b'') on disconnect.
                data = client_socket.recv(1024)
                if not data:
                    date_str = datetime.now().strftime("%d-%m-%Y--%H-%M-%S")
                    logging.info(f"Client disconnected - date_str")
                    break
                # Get command as string rather than bytes
                command = data.decode().strip()
                # Handle command
                threading.Thread(target=self.ct_program.handle_command, args=(command, client_socket)).start()
                logging.info(f"Command reccieved from client: {command}")
                # Return a generic command acknowledge
                acknowledge = 'Command Recieved'
                client_socket.sendall(acknowledge.encode())
                logging.info("Generic acknowledge returned to client")

        except socket.error as socket_error:
            logging.exception("Error accepting connections: %s", socket_error)
        finally:
            client_socket.close()

    # -----Server Methods END-----

    def log_info(self, message):
        if self.ct_program.log_queue:
            logging.info(message)
            log_info = {'program': 'server', 'message': message}
            self.ct_program.log_queue.put(log_info)


