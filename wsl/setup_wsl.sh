#!/bin/bash

echo "================================================================"
echo "           ATAK-PX4 Bridge - WSL2 Setup Script"
echo "================================================================"
echo

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if Python3 is installed
echo -e "${BLUE}[INFO]${NC} Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} Python3 is not installed"
    echo "Installing Python3..."
    sudo apt update && sudo apt install -y python3 python3-pip
else
    echo -e "${GREEN}[INFO]${NC} Python3 found: $(python3 --version)"
fi

# Check if pip3 is available
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} pip3 is not available"
    echo "Installing pip3..."
    sudo apt install -y python3-pip
fi

# Install Python dependencies
echo -e "${BLUE}[INFO]${NC} Installing Python dependencies..."
pip3 install pymavlink

# Check if installation was successful
if python3 -c "import pymavlink" 2>/dev/null; then
    echo -e "${GREEN}[INFO]${NC} pymavlink installed successfully"
else
    echo -e "${RED}[ERROR]${NC} Failed to install pymavlink"
    exit 1
fi

# Get network information
echo
echo -e "${BLUE}[INFO]${NC} Detecting network configuration..."

# Get WSL2 IP
WSL_IP=$(hostname -I | awk '{print $1}')
echo -e "${GREEN}[INFO]${NC} WSL2 IP: $WSL_IP"

# Get Windows host IP (gateway)
WINDOWS_IP=$(ip route | grep default | awk '{print $3}')
echo -e "${GREEN}[INFO]${NC} Windows host IP: $WINDOWS_IP"

# Update wsl_forwarder.py with detected Windows IP
echo
echo -e "${BLUE}[INFO]${NC} Updating wsl_forwarder.py with detected IP..."

if [ -f "wsl_forwarder.py" ]; then
    sed -i "s/WINDOWS_HOST = '.*'/WINDOWS_HOST = '$WINDOWS_IP'/" wsl_forwarder.py
    echo -e "${GREEN}[INFO]${NC} Updated WINDOWS_HOST to $WINDOWS_IP"
else
    echo -e "${YELLOW}[WARNING]${NC} wsl_forwarder.py not found in current directory"
fi

# Check if PX4 is available
echo
echo -e "${BLUE}[INFO]${NC} Checking PX4 installation..."
if [ -d "~/PX4-Autopilot" ] || [ -d "../PX4-Autopilot" ] || [ -d "../../PX4-Autopilot" ]; then
    echo -e "${GREEN}[INFO]${NC} PX4-Autopilot directory found"
elif command -v px4 &> /dev/null; then
    echo -e "${GREEN}[INFO]${NC} PX4 binary found in PATH"
else
    echo -e "${YELLOW}[WARNING]${NC} PX4 not found in common locations"
    echo "If you haven't installed PX4, follow these steps:"
    echo "1. git clone https://github.com/PX4/PX4-Autopilot.git"
    echo "2. cd PX4-Autopilot"
    echo "3. bash ./Tools/setup/ubuntu.sh"
    echo "4. make px4_sitl gazebo_iris"
fi

# Test MAVLink connection capability
echo
echo -e "${BLUE}[INFO]${NC} Testing network connectivity..."

# Test if can bind to required ports
if python3 -c "
import socket
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('0.0.0.0', 14541))
    s.close()
    print('Port 14541: OK')
except:
    print('Port 14541: FAILED - Port may be in use')

try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
    s.connect(('127.0.0.1', 14540))
    s.close()
    print('PX4 port 14540: Reachable')
except:
    print('PX4 port 14540: Not reachable (PX4 not running)')
"; then
    echo -e "${GREEN}[INFO]${NC} Port tests completed"
fi

# Create a simple test script
echo
echo -e "${BLUE}[INFO]${NC} Creating test script..."
cat > test_px4_connection.py << 'EOF'
#!/usr/bin/env python3
"""
Quick test script to verify PX4 connection
"""
import sys
import time
sys.path.insert(0, '.')

try:
    from pymavlink import mavutil
    
    print("Attempting to connect to PX4...")
    m = mavutil.mavlink_connection('udp:0.0.0.0:14540')
    print("Waiting for heartbeat...")
    m.wait_heartbeat(timeout=10)
    print("✅ SUCCESS: Connected to PX4!")
    print(f"System ID: {m.target_system}, Component ID: {m.target_component}")
    
except Exception as e:
    print(f"❌ FAILED: {e}")
    print("Make sure PX4 SITL is running: make px4_sitl gazebo_iris")
    sys.exit(1)
EOF

chmod +x test_px4_connection.py
echo -e "${GREEN}[INFO]${NC} Created test script: test_px4_connection.py"

echo
echo "================================================================"
echo "                        Setup Complete!"
echo "================================================================"
echo
echo -e "${GREEN}Configuration Summary:${NC}"
echo "- WSL2 IP: $WSL_IP"
echo "- Windows Host: $WINDOWS_IP"
echo "- MAVLink listening: 0.0.0.0:14541"
echo "- PX4 connection: 127.0.0.1:14540"
echo
echo -e "${GREEN}Next steps:${NC}"
echo "1. Start PX4 SITL: make px4_sitl gazebo_iris"
echo "2. Test connection: python3 test_px4_connection.py"
echo "3. Run forwarder: python3 wsl_forwarder.py"
echo "4. Run Windows relay: python windows/atak_relay_gui.py"
echo
echo "Check README.md for complete usage instructions."
echo