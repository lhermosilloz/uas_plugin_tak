# ATAK-PX4 Integration Bridge

A bidirectional MAVLink bridge that enables ATAK (Android Team Awareness Kit) to control PX4 drones through a Windows → WSL2 → PX4 SITL relay setup.

## 🏗️ Architecture

```
ATAK Phone ←→ Windows (wsl_to_atak_relay.py) ←→ WSL2 (wsl_forwarder.py) ←→ PX4 SITL
    14550         14550 ←→ 14560                   14541 ←→ 14540
```

## 📁 Project Structure

- **`wsl_to_atak_relay.py`** - Windows UDP relay between ATAK and WSL2
- **`wsl_forwarder.py`** - WSL2 MAVLink bridge between Windows and PX4
- **`setup_windows.bat`** - Windows environment setup script
- **`setup_wsl.sh`** - WSL2 environment setup script

## 🚀 Quick Start

### Prerequisites

- **Windows 11/10** with WSL2 enabled
- **PX4 SITL** running in WSL2
- **ATAK** app on Android device
- **Python 3.8+** on both Windows and WSL2

### 1. Setup Windows Environment

Run in **PowerShell as Administrator**:
```powershell
.\setup_windows.bat
```

### 2. Setup WSL2 Environment

Run in **WSL2 terminal**:
```bash
chmod +x setup_wsl.sh
./setup_wsl.sh
```

### 3. Start PX4 SITL (WSL2)

```bash
# In WSL2 PX4 directory
make px4_sitl gazebo_iris

# In PX4 console, set parameters for external control:
param set COM_RC_IN_MODE 0
param set COM_ARM_WO_GPS 1
param set COM_ARM_AUTH_REQ 0
param save
commander mode manual
```

### 4. Start Bridge Services

**Terminal 1 (WSL2):**
```bash
python3 wsl_forwarder.py
```

**Terminal 2 (Windows PowerShell):**
```powershell
python wsl_to_atak_relay.py
```

### 5. Configure ATAK

On your ATAK device:
1. Go to **Settings → Network Preferences → Streaming**
2. Add connection:
   - **Address:** `<Windows_IP>:14550`
   - **Protocol:** UDP
   - **Role:** Server

## 🔧 Configuration

### Network Configuration

Upon setup, the scripts will use these variables:

**wsl_to_atak_relay.py (Windows):**
- `WSL2_IP` - Auto-detected WSL2 IP address
- `ATAK_IP` - Auto-detected or manually configured ATAK device IP
- `LISTEN_PORT = 14560` - Receives data from WSL2
- `ATAK_PORT = 14550` - Communicates with ATAK

**wsl_forwarder.py (WSL2):**
- `WINDOWS_HOST = '192.168.192.1'` - Windows host gateway
- `FORWARD_PORT = 14560` - Sends data to Windows
- `PX4_PORT = 14540` - PX4 SITL MAVLink port

### Custom IP Configuration

If auto-detection fails, manually edit the IP addresses in the script files.

## 🛠️ Usage

### Supported ATAK Commands

- ✅ **ARM/DISARM** - Arm or disarm the drone
- ✅ **TAKEOFF** - Takeoff to specified altitude
- ✅ **LANDING** - Land at current position
- ✅ **WAYPOINT NAVIGATION** - Send GPS waypoints
- ✅ **EMERGENCY STOP** - Immediate stop commands

### Command Flow

1. Send command from **ATAK interface**
2. **Windows relay** forwards to WSL2
3. **WSL2 forwarder** decodes MAVLink and sends to PX4
4. **PX4 responses** flow back to ATAK

### Troubleshooting

**🔍 Debug Mode**

Enable verbose logging by uncommenting print statements in both scripts.

**Common Issues:**

- **"ARM Temporarily Rejected"** - Check PX4 safety parameters
- **"No ATAK connection"** - Verify device IP and firewall settings
- **"Commands not reaching PX4"** - Ensure WSL2 IP is correct

**PX4 Safety Parameters:**
```bash
# Allow external arming
param set COM_ARM_AUTH_REQ 0
# Disable RC requirement 
param set COM_RC_IN_MODE 0
# Allow GPS-free arming
param set COM_ARM_WO_GPS 1
```

## 📊 Network Ports

| Port | Service | Direction |
|------|---------|----------|
| 14540 | PX4 SITL MAVLink | WSL2 ← → PX4 |
| 14541 | Command Relay | WSL2 ← Windows |
| 14550 | ATAK MAVLink | Windows ← → ATAK |
| 14560 | Status Relay | Windows ← WSL2 |

## 🧪 Testing

### Manual Testing

**Test Windows → WSL2 connection:**
```powershell
# Windows PowerShell
Test-NetConnection -ComputerName <WSL2_IP> -Port 14541
```

**Test PX4 connection:**
```bash
# WSL2 Terminal  
echo "heartbeat" | nc 127.0.0.1 14540
```

### Expected Output

**wsl_forwarder.py:**
```
Waiting for heartbeat from PX4...
Got heartbeat! Bidirectional forwarding active...
CMD to PX4: 44 bytes from ('192.168.192.1', 14560)
  → Message: COMMAND_LONG
    Command ID: 400
    → ARM command
PX4 ACK: Command 400 Result 0
Accepted
```

**wsl_to_atak_relay.py:**
```
Bidirectional relay running, press Enter to stop...
```

## 🤝 Contributing

1. Test with your specific PX4/ATAK setup
2. Submit issues for bugs or feature requests
3. Improve documentation for edge cases

## 📜 License

Open source project for ATAK and PX4 development.
