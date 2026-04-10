# Run this on Windows to relay the UDP
import socket
import threading

WSL2_IP = '172.19.216.248' # PheratechOffice: '192.168.205.171'
WSL2_PORT = 14541          # send commands back to PX4 here
ATAK_IP = '192.168.1.6' # PheratechOffice: '192.168.1.38'   # phone IP
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
        if len(data) != 23 and len(data) != 17:
            print(f'ATAK to WSL: {len(data)} bytes')

            if data[0] == 0xfd:
                import struct
                try:
                    payload_len = data[1]
                    msgid = int.from_bytes(data[7:10], 'little')
                    
                    print(f'  Message ID: {msgid}, Payload length: {payload_len}')
                    
                    payload = data[10:10+payload_len]
                    
                    if msgid == 76:  # COMMAND_LONG 
                        if len(payload) >= 32:
                            params = struct.unpack('<7f H 2B', payload[:32])
                            param1, param2, param3, param4, param5, param6, param7, command, target_sys, target_comp = params
                            
                            print(f'  Decoded COMMAND_LONG:')
                            print(f'    Command: {command}')
                            print(f'    Params: [{param1:.2f}, {param2:.2f}, {param3:.2f}, {param7:.2f}]')
                            
                            if command == 192:
                                print(f'SET ALTITUDE: {param7:.2f}m')
                            
                    elif msgid == 75:  # COMMAND_INT (waypoints, orbits)
                        if len(payload) >= 32:
                            # COMMAND_INT: param1-4 (floats), x,y (int32), z (float), command (uint16), target_sys, target_comp (uint8)
                            params = struct.unpack('<4f 2l f H 2B', payload[:32])
                            param1, param2, param3, param4, x, y, z, command, target_sys, target_comp = params
                            
                            print(f'  Decoded COMMAND_INT:')
                            print(f'    Command: {command}')
                            print(f'    Params: [{param1:.2f}, {param2:.2f}, {param3:.2f}, {param4:.2f}]')
                            print(f'    Position: x={x}, y={y}, z={z:.2f}')
                            
                            if command == 34:
                                print(f'ORBIT COMMAND! Radius={param1:.2f}, Velocity={param2:.2f}')
                            elif command == 192:
                                print(f'WAYPOINT COMMAND! Alt={z:.2f}')
                            elif command == 21:
                                print(f'LAND COMMAND!')
                            else:
                                print(f'Unknown COMMAND_INT: {command}')
                                
                except Exception as e:
                    print(f'  Decode error: {e}')
            

            for i in range(0, len(data), 16):
                print(' '.join(f'{b:02x}' for b in data[i:i+16]))

threading.Thread(target=wsl_to_atak, daemon=True).start()
threading.Thread(target=atak_to_wsl, daemon=True).start()
input("Bidirectional relay running, press Enter to stop...\n")