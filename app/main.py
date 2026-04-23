#!/usr/bin/env python3
"""
RFID Cut Station — Desktop App
Connects ESP32-C3 (RFID + Motor + LCD) to SQL database.

Architecture:
  ESP32-C3  ←→  USB Serial  ←→  This App  ←→  SQL Database
                                     ↕
                              Web Dashboard (browser)

Usage:
  python3 main.py                      # Uses config.ini (default: SQLite)
  python3 main.py --sqlserver           # Force SQL Server mode
  python3 main.py --port /dev/ttyUSB0   # Force serial port

Config:
  Edit config.ini for per-machine settings (DB, COM port, station name).
"""

import http.server
import json
import os
import sys
import threading
import time
import webbrowser
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from db_handler import DatabaseHandler, CFG, CONFIG_PATH, load_config
from serial_handler import SerialHandler
import configparser

# ─── READ FROM config.ini ────────────────────────────────
STATION_NAME = CFG.get('machine', 'name')
WEB_PORT = CFG.getint('dashboard', 'web_port')
BAUD_RATE = CFG.getint('serial', 'baud')
CONFIG_PORT = CFG.get('serial', 'port').strip()
CONFIG_DB_MODE = CFG.get('database', 'mode').strip().lower()
# ─────────────────────────────────────────────────────────

# Global state
app_state = {
    'serial_connected': False,
    'serial_port': '',
    'db_mode': 'sqlite',
    'station_name': STATION_NAME,
    'activity_log': [],       # Recent card taps
    'last_card': None,
    'last_size': '',
    'last_qty': 0,
    'total_scans': 0,
    'total_cuts': 0,
    'status': 'Ready',
}

db = None
serial_handler = None


def log_activity(card_no, size_name, cut_qty, status='ok'):
    """Add entry to activity log."""
    entry = {
        'time': datetime.now().strftime('%H:%M:%S'),
        'card': card_no,
        'size': size_name,
        'qty': cut_qty,
        'status': status,
    }
    app_state['activity_log'].insert(0, entry)
    # Keep last 50
    if len(app_state['activity_log']) > 50:
        app_state['activity_log'] = app_state['activity_log'][:50]


def on_card_received(card_no):
    """Called when ESP32 sends a card number via serial."""
    global app_state

    print(f"\n📥 Card received: {card_no}")
    app_state['total_scans'] += 1
    app_state['status'] = f'Processing card {card_no}...'

    # Query database
    result = db.lookup_card(card_no)

    if result is None:
        print(f"  ❌ Card {card_no} NOT FOUND")
        serial_handler.send_cut(0, "NOT FOUND")
        log_activity(card_no, '—', 0, 'not_found')
        app_state['status'] = f'Card {card_no} not found'
        app_state['last_card'] = card_no
        app_state['last_size'] = '—'
        app_state['last_qty'] = 0
        return

    size_name, cut_qty = result
    print(f"  ✅ Card {card_no} → Size: {size_name}, CutQty: {cut_qty}")

    # Send to ESP
    serial_handler.send_cut(cut_qty, size_name)

    # Update state
    app_state['total_cuts'] += cut_qty
    app_state['last_card'] = card_no
    app_state['last_size'] = size_name
    app_state['last_qty'] = cut_qty
    app_state['status'] = f'Cutting {cut_qty}x {size_name}'

    log_activity(card_no, size_name, cut_qty, 'ok')


# ─── WEB SERVER ──────────────────────────────────────────

# Support PyInstaller bundled EXE
def _base_path():
    """Get base path — works for both normal Python and PyInstaller EXE."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS  # PyInstaller temp folder
    return os.path.dirname(__file__)

HTML_PATH = os.path.join(_base_path(), 'dashboard.html')


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for the web dashboard."""

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == '/' or parsed.path == '/index.html':
            self._serve_html()

        elif parsed.path == '/api/state':
            self._json_response(app_state)

        elif parsed.path == '/api/ports':
            ports = SerialHandler.list_ports()
            self._json_response(ports)

        elif parsed.path == '/api/settings':
            # Return current config.ini values
            cfg = load_config()
            settings = {
                'machine_name': cfg.get('machine', 'name'),
                'db_mode': cfg.get('database', 'mode'),
                'db_host': cfg.get('database', 'host'),
                'db_port': cfg.get('database', 'port'),
                'db_database': cfg.get('database', 'database'),
                'db_user': cfg.get('database', 'user'),
                'db_password': cfg.get('database', 'password'),
                'db_table': cfg.get('database', 'table', fallback='tCutBundCard'),
                'db_card_col': cfg.get('database', 'card_column', fallback='CardNo'),
                'db_size_col': cfg.get('database', 'size_column', fallback='SizeName'),
                'db_qty_col': cfg.get('database', 'qty_column', fallback='CutQty'),
                'serial_port': cfg.get('serial', 'port'),
                'serial_baud': cfg.get('serial', 'baud'),
                'web_port': cfg.get('dashboard', 'web_port'),
            }
            self._json_response(settings)

        elif parsed.path == '/api/cards':
            cards = db.get_all_cards()
            self._json_response([
                {'CardNo': c[0], 'SizeName': c[1], 'CutQty': c[2]}
                for c in cards
            ])

        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len).decode('utf-8') if content_len else '{}'

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        if parsed.path == '/api/connect':
            port = data.get('port', '')
            if port:
                success = serial_handler.connect(port)
                if success:
                    serial_handler.start_listening(on_card_received)
                    app_state['serial_connected'] = True
                    app_state['serial_port'] = port
                    app_state['status'] = f'Connected to {port}'
                    self._json_response({'ok': True})
                else:
                    self._json_response({'ok': False, 'error': f'Cannot open {port}'})
            else:
                self._json_response({'ok': False, 'error': 'No port specified'})

        elif parsed.path == '/api/disconnect':
            serial_handler.disconnect()
            app_state['serial_connected'] = False
            app_state['serial_port'] = ''
            app_state['status'] = 'Disconnected'
            self._json_response({'ok': True})

        elif parsed.path == '/api/simulate':
            # Simulate a card tap (for testing without hardware)
            card_no = data.get('card', '')
            if card_no:
                on_card_received(card_no)
                self._json_response({'ok': True})
            else:
                self._json_response({'ok': False, 'error': 'No card number'})

        elif parsed.path == '/api/settings':
            # Save settings to config.ini
            cfg = configparser.ConfigParser()
            cfg.read(CONFIG_PATH, encoding='utf-8')
            for section in ['machine', 'database', 'serial', 'dashboard']:
                if not cfg.has_section(section):
                    cfg.add_section(section)
            cfg.set('machine', 'name', data.get('machine_name', 'Cut Station 1'))
            cfg.set('database', 'mode', data.get('db_mode', 'sqlite'))
            cfg.set('database', 'host', data.get('db_host', ''))
            cfg.set('database', 'port', data.get('db_port', '1433'))
            cfg.set('database', 'database', data.get('db_database', ''))
            cfg.set('database', 'user', data.get('db_user', ''))
            cfg.set('database', 'password', data.get('db_password', ''))
            cfg.set('database', 'table', data.get('db_table', 'tCutBundCard'))
            cfg.set('database', 'card_column', data.get('db_card_col', 'CardNo'))
            cfg.set('database', 'size_column', data.get('db_size_col', 'SizeName'))
            cfg.set('database', 'qty_column', data.get('db_qty_col', 'CutQty'))
            cfg.set('serial', 'port', data.get('serial_port', ''))
            cfg.set('serial', 'baud', data.get('serial_baud', '115200'))
            cfg.set('dashboard', 'web_port', data.get('web_port', '8080'))
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                cfg.write(f)
            # Update runtime state
            app_state['station_name'] = data.get('machine_name', 'Cut Station 1')
            self._json_response({'ok': True, 'message': 'Settings saved. Restart app to apply DB changes.'})

        elif parsed.path == '/api/autoconnect':
            # Auto-detect ESP32 on any port
            if serial_handler.is_connected:
                serial_handler.disconnect()
            port = serial_handler.auto_connect()
            if port:
                serial_handler.start_listening(on_card_received)
                app_state['serial_connected'] = True
                app_state['serial_port'] = port
                app_state['status'] = f'Auto-connected to {port}'
                self._json_response({'ok': True, 'port': port})
            else:
                self._json_response({'ok': False, 'error': 'ESP32 not found on any port'})

        else:
            self.send_error(404)

    def _serve_html(self):
        try:
            with open(HTML_PATH, 'r', encoding='utf-8') as f:
                html = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode())
        except FileNotFoundError:
            self.send_error(500, 'dashboard.html not found')

    def _json_response(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


def start_web_server():
    """Start the dashboard web server."""
    server = http.server.HTTPServer(('0.0.0.0', WEB_PORT), DashboardHandler)
    server.allow_reuse_address = True
    server.socket.setsockopt(__import__('socket').SOL_SOCKET, __import__('socket').SO_REUSEADDR, 1)
    server.serve_forever()


# ─── MAIN ────────────────────────────────────────────────

def main():
    global db, serial_handler

    # CLI flags override config.ini
    use_sqlserver = '--sqlserver' in sys.argv or CONFIG_DB_MODE == 'sqlserver'
    port_arg = None

    for i, arg in enumerate(sys.argv):
        if arg == '--port' and i + 1 < len(sys.argv):
            port_arg = sys.argv[i + 1]

    # Fallback to config.ini port
    if not port_arg and CONFIG_PORT:
        port_arg = CONFIG_PORT

    print("=" * 55)
    print(f"  🏭 {STATION_NAME}")
    print("=" * 55)

    # Database
    db_mode = 'SQL Server' if use_sqlserver else 'SQLite (test)'
    app_state['db_mode'] = 'sqlserver' if use_sqlserver else 'sqlite'
    print(f"  Mode: {db_mode}")

    if use_sqlserver:
        db_host = CFG.get('database', 'host')
        db_name = CFG.get('database', 'database')
        print(f"  Target: {db_host}/{db_name}")

    try:
        db = DatabaseHandler(use_sqlserver=use_sqlserver)
    except Exception as e:
        print(f"\n❌ Database error: {e}")
        sys.exit(1)

    # Serial
    serial_handler = SerialHandler(port=port_arg, baud=BAUD_RATE)

    if port_arg:
        if serial_handler.connect():
            serial_handler.start_listening(on_card_received)
            app_state['serial_connected'] = True
            app_state['serial_port'] = port_arg
        else:
            print(f"  ⚠️  Could not open {port_arg}, continue without serial")

    # Web server
    print(f"  🌐 Dashboard: http://localhost:{WEB_PORT}")
    print("=" * 55)
    print()
    print("  Open the dashboard in your browser.")
    print("  Press Ctrl+C to stop.")
    print()

    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()

    # Open browser
    webbrowser.open(f'http://localhost:{WEB_PORT}')

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        serial_handler.disconnect()
        db.close()


if __name__ == '__main__':
    main()
