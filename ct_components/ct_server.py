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
socket_settings.json file in the utils directory which is not git tracked.
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
        # Create reference to main program
        self.ct_program = chromtroller
        # Get sensitive data from id_file file
        self.id_file = self.load_socket_info()
        # Create server socket
        self.server_socket = self.init_socket()
        # Public var
        self.active_connection = False

    # -----Init Methods START-----

    @staticmethod
    def load_socket_info(secure_id_file_path=None):
        """Read in the (private) connection data. """
        try:
            if secure_id_file_path is None:
                project_path = os.path.dirname(os.path.dirname(__file__))
                settings_path = os.path.join(project_path, 'settings_files')
                secure_id_file_path = os.path.join(settings_path, 'socket_settings.json')
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
        print(f"Server listening on port: {self.id_file['socket_port']}")
        return server_socket

    # -----Init Methods END-----
    # -----Connect Method START -----

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

                # Reject connections if one is already active
                if self.active_connection:
                    # Action - Close the new socket attempting to connect
                    client_socket.close()
                    # Info/Logging
                    denied_message = "Connection rejected. A client is already connected to the controller"
                    logging.info(denied_message)
                    self.send_to_client(client_socket, denied_message, data_type='reply')  # update to handle 'info'
                    print(denied_message)

                # Connect any client with valid IP address
                if client_ip in self.id_file['allowed_ips']:
                    # Action - Handle the client on new thread so the server is still responsive
                    threading.Thread(target=self.handle_client, args=(client_socket,)).start()
                    # Info/Logging
                    self.set_active_connection(True)
                    date_str = datetime.now().strftime("%H:%M:%S_%d-%m-%Y")
                    connect_message = f"Client connected at {date_str}"
                    logging.info(connect_message)
                    self.send_to_client(client_socket, connect_message, data_type='reply')  # update to handle 'info'
                    print(connect_message)

                # Reject any address not in the IP whitelist
                else:
                    # Action - Close the new socket attempting to connect
                    client_socket.close()
                    # Info/Logging
                    denied_message = f"Connection from {client_addr} rejected. IP not in IP list"
                    logging.info(denied_message)
                    self.send_to_client(client_socket, denied_message, data_type='reply')  # update to handle 'info'
                    print(denied_message)

            except socket.error as socket_error:
                logging.exception("Error accepting connections: %s", socket_error)

    # -----Connect Method END -----
    # -----Handle Client Methods START -----

    def handle_client(self, client_socket):
        """Receive commands from a client and handle."""
        try:

            while True:
                # Check the socket is an active socket
                if self.is_socket_closed(client_socket):
                    # Info/logging
                    date_str = datetime.now().strftime("%H_%M_%S-%d_%m_%Y")
                    disconnect_message = f"Client disconnected at {date_str}"
                    logging.info(disconnect_message)
                    print(disconnect_message)
                    # Action - set public vars and break loop
                    self.ct_program.client_socket = None
                    self.set_active_connection(False)
                    return "No connected Socket"

                # set the CT public var to the current client socket
                self.ct_program.client_socket = client_socket

                # Get info from client
                client_comm_dict = self._receive_from_client(client_socket)

                # Handle the command
                response = self.ct_program.handle_command(client_comm_dict)

                # Send response back to client
                if response:
                    self.send_to_client(client_socket=client_socket, data=response, data_type='reply')
                    logging.info(f"Response sent to client: {response}")

        except socket.error as socket_error:
            logging.exception("Error accepting connections: %s", socket_error)
        finally:
            client_socket.close()
            self.active_connection = False
            self.ct_program.client_socket = None

    @staticmethod
    def send_to_client(client_socket, data, data_type='reply'):
        try:
            message_dict = {'command': data_type, 'data': data}
            message = json.dumps(message_dict).encode()
            message_length = len(message).to_bytes(4, byteorder='big')
            client_socket.sendall(message_length + message)
        except OSError as e:
            logging.error(f"Error sending data to client {client_socket} - {e}")

    @staticmethod
    def _receive_from_client(client_socket):
        try:
            # Read the length of the incoming message (4 bytes) then read the message
            message_length_bytes = client_socket.recv(4)
            if not message_length_bytes:
                return "Empty data byte received"
            message_length = int.from_bytes(message_length_bytes, byteorder='big')
            data = client_socket.recv(message_length)

            # Read the incoming data
            if data:
                reccieved_dict = json.loads(data.decode())
                return reccieved_dict

            return "no data found in server response"

        except Exception as error:
            print(f"Error receiving updates: {error}")

    @staticmethod
    def is_socket_closed(sock):
        try:
            # Try to read 1 byte in a non-blocking way to check the socket state
            data = sock.recv(1, socket.MSG_PEEK)
            if len(data) == 0:
                return True  # Socket is closed
        except BlockingIOError:
            # Non-blocking read didn't succeed, socket is still open
            return False
        except ConnectionResetError:
            # Connection was reset
            return True
        except socket.error as e:
            # Catch other socket errors
            print(f"Socket error: {e}")
            return True
        return False

    # ----- Handle Client Methods END -----
    # ----- Util Methods START -----

    def set_active_connection(self, state: bool):
        with threading.Lock():
            self.active_connection = state

# ----- Util Methods END -----
