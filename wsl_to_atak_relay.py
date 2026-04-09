# Run this on Windows
import socket
import threading

WSL2_IP = '192.168.205.171'
ATAK_IP = '192.168.1.38'    # your phone
LISTEN_PORT = 14560           # avoid conflict with QGC on 14550
ATAK_PORT = 14550

sock_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_in.bind(('0.0.0.0', LISTEN_PORT))

sock_out = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def relay():
    while True:
        data, addr = sock_in.recvfrom(4096)
        sock_out.sendto(data, (ATAK_IP, ATAK_PORT))
        # print(f"Relayed {len(data)} bytes from {addr}")

print(f"Relaying UDP :{LISTEN_PORT} → ATAK {ATAK_IP}:{ATAK_PORT}")
threading.Thread(target=relay, daemon=True).start()
input("Press Enter to stop...\n")