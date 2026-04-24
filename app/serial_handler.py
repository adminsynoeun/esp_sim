#!/usr/bin/env python3
"""
Serial communication handler for ESP32-C3.

Protocol:
  ESP → App:   CARD:<card_number>\n
  App → ESP:   CUT:<qty>:<size_name>\n   (qty=0 means not found)
"""


def _safe_print(*args, **kwargs):
    """Print that won't crash when stdout is None (silent EXE mode)."""
    try:
        print(*args, **kwargs)
    except Exception:
        pass

import serial
import serial.tools.list_ports
import threading
import time


class SerialHandler:
    """Manages serial connection to ESP32-C3."""

    def __init__(self, port=None, baud=115200):
        self.port = port
        self.baud = baud
        self.ser = None
        self.running = False
        self.on_card_received = None   # Callback: fn(card_no) → called when ESP sends card
        self._thread = None

    @staticmethod
    def list_ports():
        """List all available serial ports."""
        ports = serial.tools.list_ports.comports()
        result = []
        for p in ports:
            result.append({
                'device': p.device,
                'description': p.description,
                'hwid': p.hwid,
            })
        return result

    def connect(self, port=None):
        """Open serial connection."""
        if port:
            self.port = port

        if not self.port:
            raise ValueError("No port specified")

        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            time.sleep(2)  # Wait for ESP to boot after serial open
            # Flush any boot messages
            if self.ser.in_waiting:
                self.ser.read(self.ser.in_waiting)
            print(f"  📡 Serial connected: {self.port} @ {self.baud}")
            return True
        except serial.SerialException as e:
            print(f"  ❌ Serial error: {e}")
            return False

    def disconnect(self):
        """Close serial connection."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("  📡 Serial disconnected")

    def auto_connect(self):
        """Try all ports, connect to the one that replies PONG to PING."""
        ports = self.list_ports()
        print("  🔍 Auto-detecting ESP32...")

        for p in ports:
            dev = p['device']
            print(f"    Trying {dev} ({p['description']})...")
            try:
                test = serial.Serial(dev, self.baud, timeout=2)
                time.sleep(2)  # Wait for ESP boot
                # Flush boot messages
                if test.in_waiting:
                    test.read(test.in_waiting)
                # Send PING
                test.write(b"PING\n")
                time.sleep(0.5)
                # Read response
                response = ""
                if test.in_waiting:
                    response = test.read(test.in_waiting).decode('utf-8', errors='ignore').strip()
                if "PONG" in response:
                    print(f"    ✅ Found ESP32 on {dev}!")
                    self.ser = test
                    self.port = dev
                    return dev
                else:
                    test.close()
                    print(f"    ❌ No PONG from {dev}")
            except Exception as e:
                print(f"    ❌ {dev}: {e}")

        print("  ❌ ESP32 not found on any port")
        return None

    def send_cut(self, qty, size_name=""):
        """Send cut command to ESP: CUT:<qty>\n"""
        if not self.ser or not self.ser.is_open:
            print("  ❌ Serial not connected")
            return False

        msg = f"CUT:{qty}\n"
        try:
            self.ser.write(msg.encode())
            self.ser.flush()
            print(f"  📤 Sent: {msg.strip()}")
            return True
        except Exception as e:
            print(f"  ❌ Send error: {e}")
            return False

    def start_listening(self, callback):
        """Start background thread to listen for incoming data."""
        self.on_card_received = callback
        self.running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def _listen_loop(self):
        """Background loop reading serial data."""
        while self.running:
            try:
                if self.ser and self.ser.is_open and self.ser.in_waiting:
                    raw = self.ser.readline()
                    try:
                        line = raw.decode('utf-8').strip()
                    except UnicodeDecodeError:
                        continue

                    if line.startswith("CARD:"):
                        card_no = line.split(":", 1)[1].strip()
                        if self.on_card_received:
                            # ── Isolate callback so its exceptions never kill the loop ──
                            try:
                                self.on_card_received(card_no)
                            except Exception as cb_err:
                                _safe_print(f"  ❌ Card callback error: {cb_err}")

                time.sleep(0.01)

            except serial.SerialException:
                _safe_print("  ❌ Serial connection lost")
                self.running = False
                break
            except Exception as e:
                _safe_print(f"  ❌ Listen error: {e}")
                time.sleep(0.1)

    @property
    def is_connected(self):
        return self.ser is not None and self.ser.is_open
