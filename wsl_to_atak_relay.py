# Run this on Windows to relay the UDP
import socket
import threading

WSL2_IP = '192.168.205.171'
WSL2_PORT = 14541          # send commands back to PX4 here
ATAK_IP = '192.168.1.38'   # phone IP
LISTEN_PORT = 14560
ATAK_PORT = 14550

sock_gcs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_gcs.bind(('0.0.0.0', LISTEN_PORT))

sock_atak = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_atak.bind(('0.0.0.0', ATAK_PORT))

# WSL2 → ATAK
def wsl_to_atak():
    while True:
        data, addr = sock_gcs.recvfrom(4096)
        sock_atak.sendto(data, (ATAK_IP, ATAK_PORT))
        # print(f'WSL to ATAK: {len(data)} bytes')

# ATAK → WSL2
def atak_to_wsl():
    while True:
        data, addr = sock_atak.recvfrom(4096)
        sock_gcs.sendto(data, (WSL2_IP, WSL2_PORT))
        # print(f'ATAK to WSL: {len(data)} bytes')

threading.Thread(target=wsl_to_atak, daemon=True).start()
threading.Thread(target=atak_to_wsl, daemon=True).start()
input("Bidirectional relay running, press Enter to stop...\n")