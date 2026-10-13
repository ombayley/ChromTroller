from serial.tools import list_ports

def main():
    ports = list_ports.comports()
    for port in ports:
        print(f"Device: {port.description} | Serial Number: {port.serial_number} | Port: {port.name}")

if __name__ == "__main__":
    main()