# Run this inside WSL2
import socket
from pymavlink import mavutil

WINDOWS_HOST = '192.168.192.1'
FORWARD_PORT = 14560

m = mavutil.mavlink_connection('udp:0.0.0.0:14540')
print('Waiting for heartbeat from PX4...')
m.wait_heartbeat()
print('Got heartbeat! Forwarding to Windows...')

fwd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

while True:
    msg = m.recv_match(blocking=True)
    if msg:
        buf = msg.get_msgbuf()
        fwd.sendto(bytes(buf), (WINDOWS_HOST, FORWARD_PORT))
        # print(f'Forwarded: {msg.get_type()}')