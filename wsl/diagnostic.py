from pymavlink import mavutil
import time

m = mavutil.mavlink_connection('udp:0.0.0.0:14540')
print('Waiting for heartbeat from PX4...')
m.wait_heartbeat()
print('Got heartbeat! Checking system status...')

def check_px4_status():
    """Check PX4 status to see why ARM is being rejected"""
    
    # Request system status
    print("\n=== Checking System Status ===")
    
    # Get heartbeat info
    hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
    if hb:
        print(f"System Type: {hb.type}")
        print(f"Autopilot: {hb.autopilot}")
        print(f"Flight Mode: {hb.custom_mode}")
        print(f"System Status: {hb.system_status}")
        print(f"Armed: {bool(hb.base_mode & 0x80)}")
    
    # Get detailed status
    sys_status = m.recv_match(type='SYS_STATUS', blocking=True, timeout=5)
    if sys_status:
        print(f"\n=== System Health ===")
        sensors = sys_status.onboard_control_sensors_health
        print(f"Sensors Health: 0x{sensors:08x}")
        print(f"GPS: {'OK' if sensors & 0x20 else 'FAIL'}")
        print(f"IMU: {'OK' if sensors & 0x08 else 'FAIL'}")
        print(f"MAG: {'OK' if sensors & 0x04 else 'FAIL'}")
        print(f"BARO: {'OK' if sensors & 0x01 else 'FAIL'}")
    
    # Check GPS status
    gps = m.recv_match(type='GPS_RAW_INT', blocking=True, timeout=5)
    if gps:
        print(f"\n=== GPS Status ===")
        print(f"GPS Fix Type: {gps.fix_type}")
        print(f"Satellites: {gps.satellites_visible}")
    
    # Request parameter for safety checks
    print(f"\n=== Requesting Safety Parameters ===")
    
    # Request COM_ARM_* parameters 
    m.mav.param_request_read_send(
        target_system=1, target_component=1,
        param_id=b'COM_ARM_WO_GPS', param_index=-1
    )
    
    param_msg = m.recv_match(type='PARAM_VALUE', blocking=True, timeout=3)
    if param_msg and param_msg.param_id.decode('utf-8').strip('\x00') == 'COM_ARM_WO_GPS':
        print(f"COM_ARM_WO_GPS: {param_msg.param_value}")

def try_flight_mode_change():
    """Try changing to a flight mode that allows arming"""
    print(f"\n=== Changing to MANUAL mode ===")
    
    # Send SET_MODE command (MANUAL mode = 1 for PX4)
    m.mav.set_mode_send(
        target_system=1,
        base_mode=1,  # MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
        custom_mode=1  # PX4 MANUAL mode
    )
    
    time.sleep(1)
    
    # Check if mode changed
    hb = m.recv_match(type='HEARTBEAT', blocking=True, timeout=3)
    if hb:
        print(f"New Flight Mode: {hb.custom_mode}")

check_px4_status()
try_flight_mode_change()

# Try ARM again after mode change
print(f"\n=== Trying ARM after mode change ===")
m.mav.command_long_send(
    target_system=1, target_component=1, command=400, confirmation=0,
    param1=1, param2=0, param3=0, param4=0, param5=0, param6=0, param7=0
)

# Wait for response
start_time = time.time()
while time.time() - start_time < 3:
    msg = m.recv_match(type='COMMAND_ACK', blocking=False, timeout=1)
    if msg and msg.command == 400:
        print(f"ARM response after mode change: {msg.result}")
        if msg.result == 0:
            print("SUCCESS! Drone should be armed now")
        break
else:
    print("No response received")