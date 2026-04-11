@echo off
echo ================================================================
echo           ATAK-PX4 Bridge - Windows Setup Script
echo ================================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo [INFO] Python found: 
python --version

:: Check if pip is available
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] pip is not available
    echo Please ensure pip is installed with Python
    pause
    exit /b 1
)

echo [INFO] Installing Python dependencies...
pip install pymavlink

:: Get WSL2 IP address
echo.
echo [INFO] Detecting WSL2 IP address...
for /f "tokens=2 delims=:" %%a in ('wsl hostname -I') do set WSL_IP=%%a
set WSL_IP=%WSL_IP: =%

if "%WSL_IP%"=="" (
    echo [WARNING] Could not auto-detect WSL2 IP address
    echo You'll need to manually configure WSL2_IP in wsl_to_atak_relay.py
    set WSL_IP=192.168.xxx.xxx
) else (
    echo [INFO] WSL2 IP detected: %WSL_IP%
)

:: Get Windows IP address (for ATAK connection reference)
echo.
echo [INFO] Detecting Windows IP address...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr "IPv4" ^| findstr "192.168"') do set WIN_IP=%%a
set WIN_IP=%WIN_IP: =%

if "%WIN_IP%"=="" (
    echo [WARNING] Could not detect Windows IP address
    echo Configure ATAK to connect to your Windows IP on port 14550
) else (
    echo [INFO] Windows IP detected: %WIN_IP%
    echo [INFO] Configure ATAK to connect to: %WIN_IP%:14550
)

:: Update the wsl_to_atak_relay.py with detected IPs
echo.
echo [INFO] Updating wsl_to_atak_relay.py with detected IP addresses...

if exist wsl_to_atak_relay.py (
    powershell -Command "(Get-Content wsl_to_atak_relay.py) -replace \"WSL2_IP = '.*'\", \"WSL2_IP = '%WSL_IP%'\" | Set-Content wsl_to_atak_relay.py"
    echo [INFO] Updated WSL2_IP to %WSL_IP%
) else (
    echo [WARNING] wsl_to_atak_relay.py not found in current directory
)

:: Check Windows Firewall
echo.
echo [INFO] Checking Windows Firewall...
netsh advfirewall firewall show rule name="ATAK Bridge" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Adding Windows Firewall rule for ports 14550, 14560, 14541...
    netsh advfirewall firewall add rule name="ATAK Bridge" dir=in action=allow protocol=UDP localport=14550,14560,14541 >nul 2>&1
    if %errorlevel% equ 0 (
        echo [INFO] Firewall rules added successfully
    ) else (
        echo [WARNING] Failed to add firewall rules. You may need to run as Administrator
        echo [WARNING] Manually allow UDP ports 14550, 14560, 14541 in Windows Firewall
    )
) else (
    echo [INFO] Firewall rules already exist
)

echo.
echo ================================================================
echo                        Setup Complete!
echo ================================================================
echo.
echo Configuration Summary:
echo - WSL2 IP: %WSL_IP%
echo - Windows IP: %WIN_IP%
echo - ATAK connection: %WIN_IP%:14550
echo.
echo Next steps:
echo 1. Setup WSL2 environment: run wsl/setup_wsl.sh in WSL2
echo 2. Start PX4 SITL in WSL2
echo 3. Run: python atak_relay_gui.py
echo.
echo Check README.md for complete usage instructions.
echo.
pause