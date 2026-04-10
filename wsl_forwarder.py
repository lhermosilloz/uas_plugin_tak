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

def decode_mavlink_data(data, source="Unknown"):
    """Decode MAVLink messages from raw bytes"""
    try:
        # Create a temporary MAVLink connection for parsing
        temp_mav = mavutil.mavlink_connection('udp:localhost:0')
        
        messages = []
        for byte in data:
            msg = temp_mav.mav.parse_char(bytes([byte]))
            if msg is not None:
                messages.append(msg)
                
        return messages
    except Exception as e:
        print(f'Failed to decode MAVLink from {source}: {e}')
        return []
    
# PX4 to Windows
def px4_to_windows():
    while True:
        msg = m.recv_match(blocking=True)
        if msg:
            if msg.get_type() == 'COMMAND_ACK':
                cmd_id = msg.command
                result = msg.result

                print(f'PX4 ACK: Command {cmd_id} Result {result}')

                if result == 0:
                    print('Accepted')
                elif result == 1:
                    print('Temporarily Rejected')
                elif result == 2:
                    print('Denied')
                elif result == 3:
                    print('Unsupported')
                elif result == 4:
                    print('Failed')
                else:
                    print('Unknown result code')

            buf = msg.get_msgbuf()
            fwd.sendto(bytes(buf), (WINDOWS_HOST, FORWARD_PORT))

# Windows to PX4
cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
cmd_sock.bind(('0.0.0.0', 14541))

def windows_to_px4():
    while True:
        data, addr = cmd_sock.recvfrom(4096)
        
        messages = decode_mavlink_data(data, "ATAK/Windows")
        for msg in messages:
            if msg.get_type() == 'COMMAND_LONG' or msg.get_type() == 'COMMAND_INT':
                # Forward via MAVLink connection instead of raw UDP
                m.mav.command_long_send(
                    target_system=msg.target_system,
                    target_component=msg.target_component,
                    command=msg.command,
                    confirmation=msg.confirmation,
                    param1=msg.param1,
                    param2=msg.param2,
                    param3=msg.param3,
                    param4=msg.param4,
                    param5=msg.param5,
                    param6=msg.param6,
                    param7=msg.param7
                )

        # Forward to PX4
        # fwd.sendto(data, ('127.0.0.1', PX4_PORT))

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