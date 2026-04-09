import socket
import threading
from pymavlink import mavutil
import time

m = mavutil.mavlink_connection('udp:0.0.0.0:14540')
print('Waiting for heartbeat from PX4...')
m.wait_heartbeat()
print('Got heartbeat!')

def set_mode_via_command():
    """Try setting mode using COMMAND_LONG instead of SET_MODE"""
    print("Trying mode change via COMMAND_LONG...")
    
    # MAV_CMD_DO_SET_MODE command
    m.mav.command_long_send(
        target_system=1,
        target_component=1,
        command=176,  # MAV_CMD_DO_SET_MODE
        confirmation=0,
        param1=1,    # base_mode: MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
        param2=3,    # custom_mode: 3 = POSCTL
        param3=0,
        param4=0,
        param5=0,
        param6=0,
        param7=0
    )
    
    time.sleep(2)
    
    # Check response
    hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=3)
    if hb:
        print(f"Mode after COMMAND_LONG: {hb.custom_mode}")
        return hb.custom_mode == 3
    return False

def try_manual_mode():
    """Try Manual mode first (sometimes easier to transition)"""
    print("Trying Manual mode first...")
    
    m.mav.set_mode_send(
        target_system=1,
        base_mode=mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED | mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED,
        custom_mode=1  # Manual mode
    )
    
    time.sleep(2)
    hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=3)
    if hb:
        print(f"Mode after Manual attempt: {hb.custom_mode}")
        return hb.custom_mode == 1
    return False

def force_arm_in_current_mode():
    """Try forcing ARM in whatever mode we're in"""
    print("Trying to force ARM in current mode...")
    
    # Send ARM command with force flag
    m.mav.command_long_send(
        target_system=1,
        target_component=1,
        command=400,  # MAV_CMD_COMPONENT_ARM_DISARM
        confirmation=0,
        param1=1,     # 1 = ARM
        param2=21196, # Magic number to force arm (bypasses some checks)
        param3=0,
        param4=0,
        param5=0,
        param6=0,
        param7=0
    )
    
    # Wait for response
    start_time = time.time()
    while time.time() - start_time < 3:
        msg = m.recv_match(type='COMMAND_ACK', blocking=False, timeout=1)
        if msg and msg.command == 400:
            result = msg.result
            print(f"Force ARM response: {result}")
            return result == 0
    return False

# Try different approaches
print(f"Current mode: {m.recv_match(type='HEARTBEAT', blocking=True, timeout=3).custom_mode}")

if try_manual_mode():
    print("✅ Successfully changed to Manual mode")
elif set_mode_via_command():
    print("✅ Successfully changed mode via COMMAND_LONG")
else:
    print("❌ Mode changes failed, trying force ARM in current mode")
    force_arm_in_current_mode()

# Final status check
hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=3)
if hb:
    armed = bool(hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    print(f"Final status - Mode: {hb.custom_mode}, Armed: {armed}")