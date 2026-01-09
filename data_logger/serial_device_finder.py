from serial.tools import list_ports

ports = list_ports.comports()

print("Connected Devices:")
for port in ports:
    print(f"{port.device} -> {{'description': '{port.description}', 'hwid': '{port.hwid}', 'serial_number': '{port.serial_number}'}}")