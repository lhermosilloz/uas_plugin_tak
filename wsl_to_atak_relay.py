# Run this on Windows to relay the UDP
import socket
import threading

WSL2_IP = '192.168.205.171'
WSL2_PORT = 14541          # send commands back to PX4 here
ATAK_IP = '192.168.1.38'   # phone IP
LISTEN_PORT = 14560
ATAK_PORT = 14550

sock_gcs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_gcs.bind(('0.0.0.0', LISTEN_PORT))

sock_atak = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_atak.bind(('0.0.0.0', ATAK_PORT))

# WSL2 → ATAK
def wsl_to_atak():
    while True:
        data, addr = sock_gcs.recvfrom(4096)
        sock_atak.sendto(data, (ATAK_IP, ATAK_PORT))
        # print(f'WSL to ATAK: {len(data)} bytes')

# ATAK → WSL2
def atak_to_wsl():
    while True:
        data, addr = sock_atak.recvfrom(4096)
        sock_gcs.sendto(data, (WSL2_IP, WSL2_PORT))
        if len(data) > 23:
            print(f'ATAK to WSL: {len(data)} bytes')

            # Manual decode of COMMAND_LONG with proper length handling
            if len(data) >= 42 and data[0] == 0xfd:
                import struct
                try:
                    # Get payload length from header
                    payload_len = data[1]
                    msgid = int.from_bytes(data[7:10], 'little')
                    
                    print(f'  Message ID: {msgid}, Payload length: {payload_len}')
                    
                    # Extract payload (starts at byte 10)
                    payload = data[10:10+payload_len]
                    
                    if msgid == 76:  # COMMAND_LONG 
                        # Adjust struct format for actual payload length
                        if len(payload) >= 32:  # We have at least 32 bytes
                            # Try with 32 bytes (7 floats + uint16 + 2 uint8)
                            params = struct.unpack('<7f H 2B', payload[:32])
                            param1, param2, param3, param4, param5, param6, param7, command, target_sys, target_comp = params
                            
                            print(f'  Decoded COMMAND_LONG:')
                            print(f'    Command: {command} (expecting 192 for altitude or 252 for orbit)')
                            print(f'    Target: {target_sys}/{target_comp}')
                            print(f'    Params: [{param1:.2f}, {param2:.2f}, {param3:.2f}]')
                            print(f'            [{param4:.2f}, {param5:.2f}, {param6:.2f}, {param7:.2f}]')
                            
                            if command == 192:
                                print(f'SET ALTITUDE COMMAND! Target altitude: {param7:.2f}m')
                            elif command == 252:
                                print(f'ORBIT COMMAND! Radius={param1:.2f}, Velocity={param2:.2f}')
                            elif command == 21:
                                print(f'LAND COMMAND!')
                            elif command == 16:
                                print(f'WAYPOINT COMMAND!')
                            else:
                                print(f'Unknown command: {command}')
                                
                except Exception as e:
                    print(f'  Decode error: {e}')
                    print(f'  Raw payload length: {len(payload) if "payload" in locals() else "unknown"}')
            

            for i in range(0, len(data), 16):
                print(' '.join(f'{b:02x}' for b in data[i:i+16]))

threading.Thread(target=wsl_to_atak, daemon=True).start()
threading.Thread(target=atak_to_wsl, daemon=True).start()
input("Bidirectional relay running, press Enter to stop...\n")