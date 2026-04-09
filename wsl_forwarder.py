# Run this inside WSL2
import socket
import threading
from pymavlink import mavutil
import time

WINDOWS_HOST = '192.168.192.1'
FORWARD_PORT = 14560
PX4_PORT = 14540

m = mavutil.mavlink_connection('udp:0.0.0.0:14540')
print('Waiting for heartbeat from PX4...')
m.wait_heartbeat()
print('Got heartbeat! Bidirectional forwarding active...')

fwd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# PX4 to Windows
def px4_to_windows():
    while True:
        msg = m.recv_match(blocking=True)
        if msg:
            buf = msg.get_msgbuf()
            fwd.sendto(bytes(buf), (WINDOWS_HOST, FORWARD_PORT))

# Windows to PX4
cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
cmd_sock.bind(('0.0.0.0', 14541))

def windows_to_px4():
    while True:
        data, addr = cmd_sock.recvfrom(4096)
        fwd.sendto(data, ('127.0.0.1', PX4_PORT))
        print(f'CMD to PX4: {len(data)} bytes')

def send_heartbeat():
    while True:
        m.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_GCS,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            0, 0, 0
        )
        time.sleep(1)

threading.Thread(target=px4_to_windows, daemon=True).start()
threading.Thread(target=windows_to_px4, daemon=True).start()
threading.Thread(target=send_heartbeat, daemon=True).start()
input("Press Enter to stop...\n")