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
from queue import Queue
from datetime import datetime

from ct_controller import Controller
from ct_analyser import Analyser
from ct_tracker import CommTracker


class Server:
    """
    Server to handle connections to different PC clients allowing them to control the LCMS
    controller system via the Controller object
    """

    def __init__(self, master_program):
        """
        Gets the id_file data, sets up the logging, connects to the controller and
        then opens the server port
        """
        # Setup Log
        self.setup_server_logging()
        # Get sensitive data from id_file file
        self.id_file = self.load_private_ids_file()
        # Create server socket
        self.server_socket = self.init_socket()
        # Create master_program_object
        self.master_program = master_program

        # Move to ChromTroller
        # Shared log queue with the controller
        self.log_queue = Queue()
        # Connect to the Arduino Controller
        self.lcms_controller = self.init_controller()
        # Connect to the Analysis Controller
        self.analyser = self.init_analyser()
        # Connect to the Analysis Controller
        self.tracker = self.init_comm_tracker()

    # -----Init Methods START-----
    @staticmethod
    def setup_server_logging():
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
            return config
        except (FileNotFoundError, json.JSONDecodeError, PermissionError) as err:
            logging.error(err)

    # --

    def init_controller(self):
        """Initialise the controller object"""
        try:
            controller = Controller(port=self.id_file['serial_port'], log_queue=self.log_queue)
            threading.Thread(target=self.process_log_queue()).start()
        except Exception as err:
            logging.error("Failed to connect to controller: %s", err)
            return
        logging.info("Server successfully connected to instrument controller")
        return controller

    def process_log_queue(self):
        while True:
            log_message = self.log_queue.get()
            logging.info(log_message)

    # --
    @staticmethod
    def init_analyser():
        """Initialise the controller object"""
        try:
            analyser = Analyser()
        except Exception as err:
            logging.error("Failed to connect to controller: %s", err)
            return
        logging.info("Server successfully connected to instrument controller")
        return analyser

    # --

    @staticmethod
    def init_comm_tracker():
        """Initialise the controller object"""
        try:
            tracker = CommTracker()
        except Exception as err:
            logging.error("Failed to connect to controller: %s", err)
            return
        logging.info("Server successfully connected to instrument controller")
        return tracker

    # --

    def init_socket(self):
        """Initialise socket"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(("", self.id_file['socket_port']))
        logging.info("Server listening on port: %d", self.id_file['socket_port'])
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

    # --

    def handle_client(self, client_socket):
        """Receive commands from a client and handle."""
        try:
            while True:  # Set to constant listen
                # Connection + Data = action, Connection + No Data = wait, No Connection = break
                # .recv() is blocking, Client returns empty byte (b'') on disconnect.
                data = client_socket.recv(1024)
                if not data:
                    logging.info("Client disconnected")
                    break
                # Get command as string rather than bytes
                command = data.decode().strip()
                # Handle command
                response = self.handle_command(command)
                # Ensure a response is sent
                if response is None:
                    response = 'No Data Returned'
                logging.info("Response sent back to client: %s", response)

                client_socket.sendall(response.encode())

        except socket.error as socket_error:
            logging.exception("Error accepting connections: %s", socket_error)
        finally:
            client_socket.close()

    # -----Server Methods END-----
    # -----Command Methods START -----

    def handle_command(self, command):
        logging.info("Command received from client: %s", command)
        # Seperate any passed info from the command
        command, data = self.split_command(command)

        match command:
            case 'run_info':
                self.tracker.add_client_info(data)
                return "Exp data added to run tracker"
            case 'get_exp_run_info':
                status = self.tracker.get_run_info()
                return status
            case 'start_hplc_run':
                resp = self.lcms_controller.run_analysis_cycle
                return resp
            case 'get_hplc_run_status':
                status = self.lcms_controller.get_status()
                return status
            case 'start_data_analysis':
                resp = self.analyser.process_command(command)
                return resp
            case 'get_data_analysis_status':
                status = self.analyser.get_status()
                return status

    # -----Command Methods END -----
    # -----Utility Methods START -----
    @staticmethod
    def split_command(cmd) -> tuple:
        """
        Splits a comand at first "-". Everything BEFORE = command. Everything After = data.
        E.g. 'comm-{data}' becomes: command = 'comm', info = '{data}'
        """
        # Split at first instance to ensure only 2 parts
        cmd_parts = cmd.strip().split('-', 1)

        if len(cmd_parts) > 1:
            command, info = cmd_parts[0].strip(), cmd_parts[1].strip()
        else:
            command = cmd_parts[0].strip()
            info = ""
        return command, info

    # -----Utility Methods END -----


if __name__ == "__main__":
    server = Server()
    try:
        server.listen_for_new_connections()
    except KeyboardInterrupt:
        logging.info("Shutting down the server.")
        server.close()
