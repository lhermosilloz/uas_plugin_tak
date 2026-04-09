# Run this inside WSL2
import socket
import threading
from pymavlink import mavutil
import time
import subprocess
import sys

# Auto-detect Windows host IP (gateway)
try:
    result = subprocess.run(['ip', 'route'], capture_output=True, text=True)
    for line in result.stdout.split('\n'):
        if 'default' in line:
            WINDOWS_HOST = line.split()[2]
            break
    else:
        WINDOWS_HOST = '192.168.192.1'
except:
    WINDOWS_HOST = '192.168.192.1'  # fallback

FORWARD_PORT = 14560
PX4_PORT = 14540

print(f"ATAK-PX4 WSL2 Forwarder Starting...")
print(f"Windows Host: {WINDOWS_HOST}:{FORWARD_PORT}")
print(f"PX4 Target: 127.0.0.1:{PX4_PORT}")
print(f"Command Port: 14541\n")

try:
    m = mavutil.mavlink_connection('udp:0.0.0.0:14540')
    print('🔍 Connecting to PX4...')
    m.wait_heartbeat(timeout=30)
    print('✅ Connected to PX4! Bidirectional forwarding active...')
except Exception as e:
    print(f'❌ Failed to connect to PX4: {e}')
    print('Make sure PX4 SITL is running: make px4_sitl gazebo_iris')
    sys.exit(1)

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
try:
    cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cmd_sock.bind(('0.0.0.0', 14541))
    print('📡 Command relay listening on port 14541')
except Exception as e:
    print(f'❌ Failed to bind command socket: {e}')
    sys.exit(1)

def windows_to_px4():
    print('📱 Windows→PX4 relay thread started')
    while True:
        try:
            data, addr = cmd_sock.recvfrom(4096)
            
            messages = decode_mavlink_data(data, "ATAK/Windows")
            for msg in messages:
                if msg.get_type() == 'COMMAND_LONG':
                    cmd_id = msg.command
                    cmd_name = {
                        400: 'ARM/DISARM',
                        22: 'TAKEOFF', 
                        21: 'LAND',
                        16: 'WAYPOINT',
                        176: 'SET_MODE'
                    }.get(cmd_id, f'CMD_{cmd_id}')
                    
                    print(f'🎯 Forwarding {cmd_name} to PX4')
                    
                    # Forward via MAVLink connection
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
                    
                elif msg.get_type() == 'HEARTBEAT':
                    # Forward heartbeats too for proper GCS identification
                    m.mav.heartbeat_send(
                        msg.type, msg.autopilot, msg.base_mode,
                        msg.custom_mode, msg.system_status, msg.mavlink_version
                    )
        except Exception as e:
            print(f'Windows→PX4 error: {e}')
            time.sleep(1)

def send_heartbeat():
    while True:
        m.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_GCS,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            0, 0, 0
        )
        time.sleep(1)

print('🚀 Starting forwarder threads...')
threading.Thread(target=px4_to_windows, daemon=True).start()
threading.Thread(target=windows_to_px4, daemon=True).start()
threading.Thread(target=send_heartbeat, daemon=True).start()

print("\n✅ WSL2 Forwarder active!")
print("📋 Status: Ready to relay ATAK commands to PX4")
print("🔄 Press Ctrl+C to stop\n")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Forwarder stopped by user")
    sys.exit(0)