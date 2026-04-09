import socket
import threading
from pymavlink import mavutil
import time

m = mavutil.mavlink_connection('udp:0.0.0.0:14540')
print('Waiting for heartbeat from PX4...')
m.wait_heartbeat()
print('Got heartbeat! Bidirectional forwarding active...')

def test_direct_px4_command():
    """Send ARM command directly through the MAVLink connection"""
    print("Testing direct ARM command to PX4...")
    
    # Send ARM command directly
    m.mav.command_long_send(
        target_system=1,
        target_component=1,
        command=400,  # MAV_CMD_COMPONENT_ARM_DISARM
        confirmation=0,
        param1=1,  # 1 = ARM
        param2=0,
        param3=0,
        param4=0,
        param5=0,
        param6=0,
        param7=0
    )
    
    # Wait for response
    start_time = time.time()
    while time.time() - start_time < 3:  # Wait up to 3 seconds
        msg = m.recv_match(type='COMMAND_ACK', blocking=False, timeout=1)
        if msg and msg.command == 400:
            print(f"Direct ARM response: {msg.result}")
            return
    
    print("No direct ARM response received")

# Call this before starting threads to test
test_direct_px4_command()