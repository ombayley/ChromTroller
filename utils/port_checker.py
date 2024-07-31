import serial.tools.list_ports


def main():
    ports = serial.tools.list_ports.comports()

    for port in ports:
        print(f"COM Port: {port.device}, Description: {port.description}, Serial Number: {port.serial_number}")


if __name__ == "__main__":
    main()
