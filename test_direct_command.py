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
    print("Successfully changed to Manual mode")
elif set_mode_via_command():
    print("Successfully changed mode via COMMAND_LONG")
else:
    print("Mode changes failed, trying force ARM in current mode")
    force_arm_in_current_mode()

# Final status check
hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=3)
if hb:
    armed = bool(hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    print(f"Final status - Mode: {hb.custom_mode}, Armed: {armed}")

def comprehensive_debug():
    """Complete diagnostic of PX4 state """
    print("\n=== COMPREHENSIVE PX4 DEBUG ===")
    
    # 1. Check heartbeat details
    print("1. Heartbeat Analysis:")
    hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=3)
    if hb:
        print(f"   System Type: {hb.type}")
        print(f"   Autopilot: {hb.autopilot}")
        print(f"   Base Mode: {hb.base_mode} (0x{hb.base_mode:02x})")
        print(f"   Custom Mode: {hb.custom_mode}")
        print(f"   System Status: {hb.system_status}")
        print(f"   MAVLink Version: {hb.mavlink_version}")
        
        # Decode base mode flags
        base_flags = []
        if hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED:
            base_flags.append("CUSTOM_MODE")
        if hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_TEST_ENABLED:
            base_flags.append("TEST")
        if hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_AUTO_ENABLED:
            base_flags.append("AUTO")
        if hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_GUIDED_ENABLED:
            base_flags.append("GUIDED")  
        if hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_STABILIZE_ENABLED:
            base_flags.append("STABILIZE")
        if hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_HIL_ENABLED:
            base_flags.append("HIL")
        if hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_MANUAL_INPUT_ENABLED:
            base_flags.append("MANUAL_INPUT")
        if hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED:
            base_flags.append("SAFETY_ARMED")
        
        print(f"   Base Mode Flags: {base_flags}")
    
    # 2. Try to get system status
    print("\n2. System Status:")
    m.mav.request_data_stream_send(
        target_system=1, target_component=1,
        req_stream_id=mavutil.mavlink.MAV_DATA_STREAM_ALL,
        req_message_rate=1, start_stop=1
    )
    
    time.sleep(1)
    sys_status = m.recv_match(type='SYS_STATUS', blocking=True, timeout=3)
    if sys_status:
        print(f"   Sensors Present: 0x{sys_status.onboard_control_sensors_present:08x}")
        print(f"   Sensors Enabled: 0x{sys_status.onboard_control_sensors_enabled:08x}")
        print(f"   Sensors Health:  0x{sys_status.onboard_control_sensors_health:08x}")
        print(f"   Load: {sys_status.load/10}%")
        print(f"   Battery: {sys_status.voltage_battery/100}V")
    
    # 3. Check for status messages
    print("\n3. Recent Status Messages:")
    start_time = time.time()
    while time.time() - start_time < 3:
        msg = m.recv_match(type='STATUSTEXT', blocking=False, timeout=0.1)
        if msg:
            print(f"   [{msg.severity}] {msg.text}")
    
    # 4. Try direct mode changes using different approaches
    print("\n4. Trying Different Mode Change Methods:")
    
    # Method 1: SET_MODE with different base modes
    print("   4a. SET_MODE with MAV_MODE_MANUAL_ARMED")
    m.mav.set_mode_send(
        target_system=1,
        base_mode=mavutil.mavlink.MAV_MODE_MANUAL_ARMED,
        custom_mode=0
    )
    time.sleep(1)
    hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=3)
    print(f"      Result: Mode {hb.custom_mode if hb else 'No response'}")
    
    # Method 2: Just the CUSTOM flag
    print("   4b. SET_MODE with CUSTOM_MODE flag only")
    m.mav.set_mode_send(
        target_system=1,
        base_mode=mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        custom_mode=1  # Manual
    )
    time.sleep(1)
    hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=3)
    print(f"      Result: Mode {hb.custom_mode if hb else 'No response'}")

    # 5. Test if PX4 accepts any commands  
    print("\n5. Testing Command Acceptance:")
    m.mav.command_long_send(
        target_system=1, target_component=1,
        command=mavutil.mavlink.MAV_CMD_REQUEST_AUTOPILOT_CAPABILITIES,
        confirmation=0,
        param1=1, param2=0, param3=0, param4=0, param5=0, param6=0, param7=0
    )
    
    # Wait for response
    start_time = time.time()
    while time.time() - start_time < 3:
        msg = m.recv_match(type='COMMAND_ACK', blocking=False, timeout=0.1)
        if msg:
            print(f"   Command {msg.command} -> Result {msg.result}")
            break
    else:
        print("   No command responses received")

# Add this call at the end
comprehensive_debug()