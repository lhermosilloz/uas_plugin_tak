import socket
import threading
from pymavlink import mavutil
import time

m = mavutil.mavlink_connection('udp:0.0.0.0:14540')
print('Waiting for heartbeat from PX4...')
m.wait_heartbeat()
print('Got heartbeat!')

def set_position_control_mode():
    """Set PX4 to Position Control mode"""
    print("Setting Position Control mode...")
    
    # PX4 Position Control mode
    m.mav.set_mode_send(
        target_system=1,
        base_mode=mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        custom_mode=3  # PX4 POSCTL (Position Control) mode
    )
    
    # Wait for mode change confirmation
    time.sleep(2)
    
    # Check if mode changed
    hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=3)
    if hb:
        print(f"New flight mode: {hb.custom_mode}")
        if hb.custom_mode == 3:
            print("Successfully changed to Position Control mode")
            return True
        else:
            print(f"Still in mode {hb.custom_mode}")
            return False
    return False

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
    while time.time() - start_time < 5:  # Wait up to 5 seconds
        msg = m.recv_match(type='COMMAND_ACK', blocking=False, timeout=1)
        if msg and msg.command == 400:
            result = msg.result
            print(f"ARM response: {result}")
            if result == 0:
                print("ARM ACCEPTED! Drone should be armed now")
            elif result == 1:
                print("ARM TEMPORARILY REJECTED (safety checks)")
            elif result == 4:
                print("ARM FAILED")
            return result
    
    print("No ARM response received")
    return -1

# First set the correct mode
if set_position_control_mode():
    # Then try to arm
    test_direct_px4_command()
    
    # Check final status
    hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=3)
    if hb:
        armed = bool(hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
        print(f"Final Armed Status: {armed}")
else:
    print("Could not change to Position Control mode")