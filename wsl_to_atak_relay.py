# Run this on Windows to relay the UDP
import socket
import threading
import subprocess
import sys
import time

# Auto-detect WSL2 IP if not manually set
try:
    result = subprocess.run(['wsl', 'hostname', '-I'], capture_output=True, text=True, timeout=5)
    WSL2_IP = result.stdout.strip().split()[0] if result.stdout.strip() else '192.168.205.171'
except:
    WSL2_IP = '192.168.205.171'  # fallback

WSL2_PORT = 14541          # send commands back to PX4 here  
ATAK_IP = '192.168.1.38'   # phone IP - update this for your device
LISTEN_PORT = 14560
ATAK_PORT = 14550

print(f"ATAK-PX4 Windows Relay Starting...")
print(f"WSL2 Target: {WSL2_IP}:{WSL2_PORT}")
print(f"ATAK Target: {ATAK_IP}:{ATAK_PORT}")
print(f"Listening on ports: {LISTEN_PORT}, {ATAK_PORT}")
print(f"Configure ATAK to connect to this machine's IP on port {ATAK_PORT}\n")

# Create sockets with error handling
try:
    sock_gcs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_gcs.bind(('0.0.0.0', LISTEN_PORT))
    print(f"Listening for WSL2 data on port {LISTEN_PORT}")
except Exception as e:
    print(f"Failed to bind to port {LISTEN_PORT}: {e}")
    sys.exit(1)

try:
    sock_atak = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_atak.bind(('0.0.0.0', ATAK_PORT))
    print(f"Listening for ATAK data on port {ATAK_PORT}")
except Exception as e:
    print(f"Failed to bind to port {ATAK_PORT}: {e}")
    sys.exit(1)

# WSL2 → ATAK
def wsl_to_atak():
    print("WSL2→ATAK relay thread started")
    while True:
        try:
            data, addr = sock_gcs.recvfrom(4096)
            sock_atak.sendto(data, (ATAK_IP, ATAK_PORT))
            if len(data) > 50:  # Log significant messages
                print(f'WSL→ATAK: {len(data)} bytes')
        except Exception as e:
            print(f'WSL→ATAK error: {e}')
            time.sleep(1)

# ATAK → WSL2
def atak_to_wsl():
    print("ATAK→WSL2 relay thread started")
    while True:
        try:
            data, addr = sock_atak.recvfrom(4096)
            sock_gcs.sendto(data, (WSL2_IP, WSL2_PORT))
            if len(data) > 30:  # Log command messages
                print(f'ATAK→WSL: {len(data)} bytes from {addr[0]}')
        except Exception as e:
            print(f'ATAK→WSL error: {e}')
            time.sleep(1)

print("Starting relay threads...")
threading.Thread(target=wsl_to_atak, daemon=True).start()
threading.Thread(target=atak_to_wsl, daemon=True).start()

print("\nBidirectional relay active!")
print("Status: Waiting for ATAK and WSL2 connections...")
print("Press Ctrl+C to stop\n")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nRelay stopped by user")
    sys.exit(0)