import sys
import socket
import struct
import threading
import subprocess
import json
import os
import ctypes
from datetime import datetime

# Set Windows taskbar app ID so the custom icon shows instead of Python's
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('pheratech.atak_relay.1')
except Exception:
    pass

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QGroupBox, QLabel, QLineEdit, QPushButton, QTextEdit,
    QCheckBox, QStyle, QSystemTrayIcon, QMenu, QMessageBox, QSpinBox,
    QSplitter, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QFont, QColor, QTextCharFormat, QIcon

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'relay_config.json')

# Known PX4 custom mode values from ATAK
PX4_MODES = {
    0x81010003: 'MANUAL',
    0x81010304: 'HOLD',
    0x81010604: 'LAND',
}

MAVLINK_COMMANDS = {
    16: 'NAV_WAYPOINT',
    20: 'NAV_RETURN_TO_LAUNCH',
    21: 'NAV_LAND',
    22: 'NAV_TAKEOFF',
    34: 'NAV_ORBIT',
    176: 'DO_SET_MODE',
    192: 'DO_REPOSITION',
    252: 'DO_ORBIT',
    400: 'COMPONENT_ARM_DISARM',
}


class LogSignals(QObject):
    """Thread-safe signal emitter for logging."""
    log = pyqtSignal(str, str)  # message, level
    stats_update = pyqtSignal(dict)


class ATAKRelayGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.relay_active = False
        self.sock_gcs = None
        self.sock_atak = None
        self.signals = LogSignals()
        self.signals.log.connect(self._append_log)

        # Stats
        self.stats = {
            'atak_to_wsl': 0,
            'wsl_to_atak': 0,
            'commands': 0,
            'heartbeats': 0,
        }

        self._init_ui()
        self._load_config()

        # Stats refresh timer
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self._refresh_stats_display)
        self.stats_timer.start(1000)

    # ── UI Construction ──────────────────────────────────────────────

    def _init_ui(self):
        self.setWindowTitle('ATAK-PX4 Relay Control')
        self.setMinimumSize(850, 620)

        # Load custom icon for window title bar and taskbar
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app_icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(6)

        # Top row: network config + status side by side
        top_splitter = QHBoxLayout()
        top_splitter.addWidget(self._build_network_config(), stretch=3)
        top_splitter.addWidget(self._build_status_panel(), stretch=1)
        root.addLayout(top_splitter)

        # Controls
        root.addWidget(self._build_controls())

        # Console (takes remaining space)
        root.addWidget(self._build_console(), stretch=1)

    def _build_network_config(self):
        group = QGroupBox('Network Configuration')
        grid = QGridLayout(group)

        grid.addWidget(QLabel('ATAK IP:'), 0, 0)
        self.atak_ip_input = QLineEdit('192.168.1.6')
        grid.addWidget(self.atak_ip_input, 0, 1)

        grid.addWidget(QLabel('WSL2 IP:'), 1, 0)
        self.wsl2_ip_input = QLineEdit('172.19.216.248')
        grid.addWidget(self.wsl2_ip_input, 1, 1)

        grid.addWidget(QLabel('ATAK Port:'), 0, 2)
        self.atak_port_input = QSpinBox()
        self.atak_port_input.setRange(1024, 65535)
        self.atak_port_input.setValue(14550)
        grid.addWidget(self.atak_port_input, 0, 3)

        grid.addWidget(QLabel('Listen Port:'), 1, 2)
        self.listen_port_input = QSpinBox()
        self.listen_port_input.setRange(1024, 65535)
        self.listen_port_input.setValue(14560)
        grid.addWidget(self.listen_port_input, 1, 3)

        grid.addWidget(QLabel('WSL2 Port:'), 2, 2)
        self.wsl2_port_input = QSpinBox()
        self.wsl2_port_input.setRange(1024, 65535)
        self.wsl2_port_input.setValue(14541)
        grid.addWidget(self.wsl2_port_input, 2, 3)

        detect_btn = QPushButton('Auto-Detect WSL2 IP')
        detect_btn.clicked.connect(self._auto_detect_wsl_ip)
        grid.addWidget(detect_btn, 2, 0, 1, 2)

        return group

    def _build_status_panel(self):
        group = QGroupBox('Status')
        layout = QVBoxLayout(group)

        self.status_label = QLabel('Stopped')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(
            'font-size: 14px; font-weight: bold; color: #cc0000; padding: 4px;'
        )
        layout.addWidget(self.status_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        self.stats_atak_label = QLabel('ATAK → WSL: 0')
        self.stats_wsl_label = QLabel('WSL → ATAK: 0')
        self.stats_cmds_label = QLabel('Commands: 0')
        self.stats_hb_label = QLabel('Heartbeats: 0')

        for lbl in (self.stats_atak_label, self.stats_wsl_label,
                     self.stats_cmds_label, self.stats_hb_label):
            lbl.setStyleSheet('font-size: 11px;')
            layout.addWidget(lbl)

        layout.addStretch()
        return group

    def _build_controls(self):
        group = QGroupBox('Controls')
        layout = QHBoxLayout(group)

        self.start_btn = QPushButton('Start Relay')
        self.start_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.start_btn.clicked.connect(self._start_relay)
        layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton('Stop Relay')
        self.stop_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_btn.clicked.connect(self._stop_relay)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)

        layout.addStretch()

        save_btn = QPushButton('Save Config')
        save_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        save_btn.clicked.connect(self._save_config)
        layout.addWidget(save_btn)

        clear_btn = QPushButton('Clear Console')
        clear_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogResetButton))
        clear_btn.clicked.connect(lambda: self.console.clear())
        layout.addWidget(clear_btn)

        return group

    def _build_console(self):
        group = QGroupBox('Message Monitor')
        layout = QVBoxLayout(group)

        # Filters
        filter_row = QHBoxLayout()
        self.show_heartbeats = QCheckBox('Heartbeats')
        self.show_manual_ctrl = QCheckBox('Manual Control')
        self.show_commands = QCheckBox('Commands')
        self.show_commands.setChecked(True)
        self.show_set_mode = QCheckBox('Set Mode')
        self.show_set_mode.setChecked(True)
        self.show_raw = QCheckBox('Raw Hex')

        for cb in (self.show_heartbeats, self.show_manual_ctrl,
                    self.show_commands, self.show_set_mode, self.show_raw):
            filter_row.addWidget(cb)

        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Console
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont('Consolas', 10))
        self.console.setStyleSheet(
            'background-color: #1e1e1e; color: #d4d4d4; border: 1px solid #333;'
        )
        self.console.document().setMaximumBlockCount(2000)
        layout.addWidget(self.console)

        return group

    # ── Logging ──────────────────────────────────────────────────────

    def _log(self, message, level='info'):
        self.signals.log.emit(message, level)

    def _append_log(self, message, level):
        colors = {
            'info': '#d4d4d4',
            'command': '#569cd6',
            'mode': '#c586c0',
            'warn': '#ce9178',
            'error': '#f44747',
            'success': '#6a9955',
            'hex': '#808080',
        }
        ts = datetime.now().strftime('%H:%M:%S')
        color = colors.get(level, '#d4d4d4')
        self.console.append(
            f'<span style="color:#666">[{ts}]</span> '
            f'<span style="color:{color}">{message}</span>'
        )

    # ── Stats ────────────────────────────────────────────────────────

    def _refresh_stats_display(self):
        self.stats_atak_label.setText(f"ATAK → WSL: {self.stats['atak_to_wsl']}")
        self.stats_wsl_label.setText(f"WSL → ATAK: {self.stats['wsl_to_atak']}")
        self.stats_cmds_label.setText(f"Commands: {self.stats['commands']}")
        self.stats_hb_label.setText(f"Heartbeats: {self.stats['heartbeats']}")

    # ── Config ───────────────────────────────────────────────────────

    def _save_config(self):
        cfg = {
            'atak_ip': self.atak_ip_input.text(),
            'wsl2_ip': self.wsl2_ip_input.text(),
            'atak_port': self.atak_port_input.value(),
            'listen_port': self.listen_port_input.value(),
            'wsl2_port': self.wsl2_port_input.value(),
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=2)
        self._log('Configuration saved', 'success')

    def _load_config(self):
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, 'r') as f:
                cfg = json.load(f)
            self.atak_ip_input.setText(cfg.get('atak_ip', '192.168.1.6'))
            self.wsl2_ip_input.setText(cfg.get('wsl2_ip', '172.19.216.248'))
            self.atak_port_input.setValue(cfg.get('atak_port', 14550))
            self.listen_port_input.setValue(cfg.get('listen_port', 14560))
            self.wsl2_port_input.setValue(cfg.get('wsl2_port', 14541))
            self._log('Loaded saved configuration', 'success')
        except Exception as e:
            self._log(f'Failed to load config: {e}', 'error')

    # ── Auto-Detect ──────────────────────────────────────────────────

    def _auto_detect_wsl_ip(self):
        try:
            result = subprocess.run(
                ['wsl', 'hostname', '-I'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                ip = result.stdout.strip().split()[0]
                self.wsl2_ip_input.setText(ip)
                self._log(f'Auto-detected WSL2 IP: {ip}', 'success')
            else:
                self._log('WSL2 detection failed', 'error')
        except FileNotFoundError:
            self._log('WSL not installed or not in PATH', 'error')
        except subprocess.TimeoutExpired:
            self._log('WSL2 detection timed out', 'error')
        except Exception as e:
            self._log(f'WSL2 detection error: {e}', 'error')

    # ── Relay Engine ─────────────────────────────────────────────────

    def _start_relay(self):
        atak_ip = self.atak_ip_input.text().strip()
        wsl2_ip = self.wsl2_ip_input.text().strip()
        atak_port = self.atak_port_input.value()
        listen_port = self.listen_port_input.value()
        wsl2_port = self.wsl2_port_input.value()

        if not atak_ip or not wsl2_ip:
            self._log('ATAK IP and WSL2 IP are required', 'error')
            return

        try:
            self.sock_gcs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock_gcs.bind(('0.0.0.0', listen_port))

            self.sock_atak = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock_atak.bind(('0.0.0.0', atak_port))
        except OSError as e:
            self._log(f'Failed to bind sockets: {e}', 'error')
            self._cleanup_sockets()
            return

        self.relay_active = True

        # Freeze config while running
        for w in (self.atak_ip_input, self.wsl2_ip_input,
                  self.atak_port_input, self.listen_port_input,
                  self.wsl2_port_input):
            w.setEnabled(False)

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText('Running')
        self.status_label.setStyleSheet(
            'font-size: 14px; font-weight: bold; color: #22aa22; padding: 4px;'
        )

        # Reset stats
        for k in self.stats:
            self.stats[k] = 0

        threading.Thread(target=self._wsl_to_atak_loop, daemon=True,
                         args=(atak_ip, atak_port)).start()
        threading.Thread(target=self._atak_to_wsl_loop, daemon=True,
                         args=(wsl2_ip, wsl2_port)).start()

        self._log(f'Relay started  ATAK={atak_ip}:{atak_port}  WSL2={wsl2_ip}:{wsl2_port}', 'success')

    def _stop_relay(self):
        self.relay_active = False
        self._cleanup_sockets()

        for w in (self.atak_ip_input, self.wsl2_ip_input,
                  self.atak_port_input, self.listen_port_input,
                  self.wsl2_port_input):
            w.setEnabled(True)

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText('Stopped')
        self.status_label.setStyleSheet(
            'font-size: 14px; font-weight: bold; color: #cc0000; padding: 4px;'
        )
        self._log('Relay stopped', 'warn')

    def _cleanup_sockets(self):
        for s in (self.sock_gcs, self.sock_atak):
            if s:
                try:
                    s.close()
                except Exception:
                    pass
        self.sock_gcs = None
        self.sock_atak = None

    # ── WSL2 → ATAK thread ──────────────────────────────────────────

    def _wsl_to_atak_loop(self, atak_ip, atak_port):
        while self.relay_active:
            try:
                data, addr = self.sock_gcs.recvfrom(4096)
                self.sock_atak.sendto(data, (atak_ip, atak_port))
                self.stats['wsl_to_atak'] += 1
            except OSError:
                break

    # ── ATAK → WSL2 thread ──────────────────────────────────────────

    def _atak_to_wsl_loop(self, wsl2_ip, wsl2_port):
        while self.relay_active:
            try:
                data, addr = self.sock_atak.recvfrom(4096)
                self.sock_gcs.sendto(data, (wsl2_ip, wsl2_port))
                self.stats['atak_to_wsl'] += 1
                self._decode_atak_message(data)
            except OSError:
                break

    # ── MAVLink Decoder ──────────────────────────────────────────────

    def _decode_atak_message(self, data):
        length = len(data)

        # ── MAVLink v1 Heartbeat (17 bytes, starts with 0xfe) ────────
        if length == 17 and data[0] == 0xFE:
            self.stats['heartbeats'] += 1
            if self.show_heartbeats.isChecked():
                self._log('ATAK → WSL: HEARTBEAT (17 bytes)', 'info')
            return

        # ── MAVLink v2 Manual Control (23 bytes, msg id 69) ──────────
        if length == 23 and data[0] == 0xFD:
            msgid = int.from_bytes(data[7:10], 'little')
            if msgid == 69:
                self.stats['heartbeats'] += 1
                if self.show_manual_ctrl.isChecked():
                    payload = data[10:21]
                    x, y, z, r = struct.unpack_from('<4h', payload, 0)
                    self._log(
                        f'ATAK → WSL: MANUAL_CONTROL  x={x} y={y} z={z} r={r}',
                        'info'
                    )
                return

        # ── MAVLink v2 messages ──────────────────────────────────────
        if data[0] == 0xFD:
            payload_len = data[1]
            msgid = int.from_bytes(data[7:10], 'little')
            payload = data[10:10 + payload_len]

            # SET_MODE (msg id 11)
            if msgid == 11:
                self.stats['commands'] += 1
                if self.show_set_mode.isChecked():
                    if len(payload) >= 6:
                        custom_mode = struct.unpack_from('<I', payload, 0)[0]
                        base_mode = payload[4]
                        target_sys = payload[5]
                        mode_name = PX4_MODES.get(custom_mode, f'0x{custom_mode:08X}')
                        self._log(
                            f'ATAK → WSL: SET_MODE → {mode_name}  '
                            f'(target={target_sys}, base={base_mode})',
                            'mode'
                        )
                    else:
                        self._log(f'ATAK → WSL: SET_MODE ({length} bytes)', 'mode')
                if self.show_raw.isChecked():
                    self._log_hex(data)
                return

            # COMMAND_LONG (msg id 76)
            if msgid == 76:
                self.stats['commands'] += 1
                if self.show_commands.isChecked():
                    self._decode_command_long(payload, length)
                if self.show_raw.isChecked():
                    self._log_hex(data)
                return

            # COMMAND_INT (msg id 75)
            if msgid == 75:
                self.stats['commands'] += 1
                if self.show_commands.isChecked():
                    self._decode_command_int(payload, length)
                if self.show_raw.isChecked():
                    self._log_hex(data)
                return

            # Other MAVLink messages
            self.stats['commands'] += 1
            if self.show_commands.isChecked():
                self._log(
                    f'ATAK → WSL: MAVLink msg_id={msgid}  ({length} bytes)',
                    'info'
                )
                if self.show_raw.isChecked():
                    self._log_hex(data)
            return

        # ── MAVLink v1 non-heartbeat ─────────────────────────────────
        if data[0] == 0xFE:
            msgid = data[5]
            self.stats['commands'] += 1
            if self.show_commands.isChecked():
                self._log(
                    f'ATAK → WSL: MAVLink v1 msg_id={msgid}  ({length} bytes)',
                    'info'
                )
                if self.show_raw.isChecked():
                    self._log_hex(data)

    def _decode_command_long(self, payload, length):
        if len(payload) < 32:
            self._log(f'ATAK → WSL: COMMAND_LONG  ({length} bytes, payload too short)', 'command')
            return
        params = struct.unpack('<7f H 2B', payload[:32])
        p1, p2, p3, p4, p5, p6, p7, command, tgt_sys, tgt_comp = params
        cmd_name = MAVLINK_COMMANDS.get(command, f'UNKNOWN({command})')

        details = f'ATAK → WSL: COMMAND_LONG  {cmd_name}'

        if command == 400:
            details += f'  {"ARM" if p1 == 1 else "DISARM"}'
        elif command == 22:
            details += f'  alt={p7:.1f}m'
        elif command == 192:
            details += f'  alt={p7:.1f}m'
        elif command == 176:
            details += f'  mode={int(p2)}'
        else:
            details += f'  params=[{p1:.1f},{p2:.1f},{p3:.1f},{p4:.1f},{p5:.1f},{p6:.1f},{p7:.1f}]'

        self._log(details, 'command')

    def _decode_command_int(self, payload, length):
        if len(payload) < 32:
            self._log(f'ATAK → WSL: COMMAND_INT  ({length} bytes, payload too short)', 'command')
            return
        params = struct.unpack('<4f 2l f H 2B', payload[:32])
        p1, p2, p3, p4, x, y, z, command, tgt_sys, tgt_comp = params
        cmd_name = MAVLINK_COMMANDS.get(command, f'UNKNOWN({command})')

        lat = x / 1e7 if x != 0 else 0
        lon = y / 1e7 if y != 0 else 0

        details = f'ATAK → WSL: COMMAND_INT  {cmd_name}'

        if command == 34 or command == 252:
            details += f'  radius={p1:.1f} vel={p2:.1f}'
        elif command == 192:
            details += f'  alt={z:.1f}m  lat={lat:.6f} lon={lon:.6f}'
        elif command == 21:
            details += f'  LAND'
        elif command == 16:
            details += f'  alt={z:.1f}m  lat={lat:.6f} lon={lon:.6f}'
        else:
            details += f'  params=[{p1:.1f},{p2:.1f},{p3:.1f},{p4:.1f}] pos=({lat:.6f},{lon:.6f},{z:.1f})'

        self._log(details, 'command')

    def _log_hex(self, data):
        lines = []
        for i in range(0, len(data), 16):
            lines.append(' '.join(f'{b:02x}' for b in data[i:i + 16]))
        self._log('  ' + '\n  '.join(lines), 'hex')

    # ── Window close ─────────────────────────────────────────────────

    def closeEvent(self, event):
        self.relay_active = False
        self._cleanup_sockets()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = ATAKRelayGUI()
    window.show()
    sys.exit(app.exec_())
