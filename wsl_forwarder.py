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
            buf = msg.get_msgbuf()
            fwd.sendto(bytes(buf), (WINDOWS_HOST, FORWARD_PORT))

# Windows to PX4
cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
cmd_sock.bind(('0.0.0.0', 14541))

def windows_to_px4():
    while True:
        data, addr = cmd_sock.recvfrom(4096)
        print(f'CMD to PX4: {len(data)} bytes from {addr}')
        
        # Decode and analyze the MAVLink messages
        messages = decode_mavlink_data(data, "ATAK/Windows")
        for msg in messages:
            msg_type = msg.get_type()
            print(f'  → Message: {msg_type}')
            
            # Show details for command messages
            if msg_type == 'COMMAND_LONG':
                cmd_id = msg.command
                print(f'    Command ID: {cmd_id}')
                print(f'    Target System: {msg.target_system}')
                print(f'    Target Component: {msg.target_component}')
                print(f'    Params: [{msg.param1}, {msg.param2}, {msg.param3}, {msg.param4}, {msg.param5}, {msg.param6}, {msg.param7}]')
                
                # Decode common commands
                if cmd_id == 400:  # MAV_CMD_COMPONENT_ARM_DISARM
                    arm_state = "ARM" if msg.param1 == 1 else "DISARM"
                    print(f'    → {arm_state} command')
                elif cmd_id == 22:  # MAV_CMD_NAV_TAKEOFF
                    altitude = msg.param7
                    print(f'    → TAKEOFF to {altitude}m')
                elif cmd_id == 21:  # MAV_CMD_NAV_LAND
                    print(f'    → LAND command')
            
            elif msg_type == 'HEARTBEAT':
                print(f'    Type: {msg.type}, Autopilot: {msg.autopilot}')
                
        # Forward to PX4
        fwd.sendto(data, ('127.0.0.1', PX4_PORT))

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