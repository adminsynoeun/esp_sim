#!/usr/bin/env python3
"""
Database handler — abstracts SQLite (Mac testing) vs SQL Server 2008 (Windows production).
Reads connection settings from config.ini so each machine can have its own data source.
"""

import sqlite3
import os
import sys
import configparser

# ─── LOAD CONFIG ─────────────────────────────────────────
def _app_dir():
    """Get the directory where config.ini lives.
    - Normal Python: same folder as this script
    - PyInstaller EXE: same folder as the .exe file
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(__file__)

CONFIG_PATH = os.path.join(_app_dir(), 'config.ini')

def load_config():
    """Load config.ini — returns defaults if file missing."""
    config = configparser.ConfigParser()

    defaults = {
        'machine': {'name': 'Cut Station'},
        'database': {
            'mode': 'sqlserver',
            'host': 'localhost',
            'port': '1433',
            'database': 'YourDatabaseName',
            'user': 'sa',
            'password': 'YourPassword',
        },
        'serial': {'port': '', 'baud': '115200'},
        'dashboard': {'web_port': '8080'},
    }

    # Set defaults
    for section, values in defaults.items():
        if not config.has_section(section):
            config.add_section(section)
        for key, val in values.items():
            config.set(section, key, val)

    # Override with file if exists
    if os.path.exists(CONFIG_PATH):
        config.read(CONFIG_PATH, encoding='utf-8')

    return config


CFG = load_config()

# SQLite path (next to EXE or next to script)
SQLITE_PATH = os.path.join(_app_dir(), 'factory_test.db')
# ─────────────────────────────────────────────────────────


class DatabaseHandler:
    """Handles DB queries for both SQLite (test) and SQL Server (production)."""

    def __init__(self, use_sqlserver=False):
        self.use_sqlserver = use_sqlserver
        self.conn = None

        # Configurable table/column names
        self.table = CFG.get('database', 'table', fallback='tCutBundCard')
        self.card_col = CFG.get('database', 'card_column', fallback='CardNo')
        self.size_col = CFG.get('database', 'size_column', fallback='SizeName')
        self.qty_col = CFG.get('database', 'qty_column', fallback='CutQty')
        self.time_col = CFG.get('database', 'insert_time_column', fallback='InsertTime')

        if use_sqlserver:
            self._connect_sqlserver()
        else:
            self._connect_sqlite()

    def _connect_sqlite(self):
        """Connect to local SQLite database (Mac testing)."""
        if not os.path.exists(SQLITE_PATH):
            raise FileNotFoundError(
                f"SQLite DB not found: {SQLITE_PATH}\n"
                "Run: python3 setup_db.py"
            )
        # SQLite in multi-thread mode
        self.conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        print(f"  🗄️  Connected to SQLite: {SQLITE_PATH}")

    def _connect_sqlserver(self):
        """Connect to SQL Server 2008 (Windows production) using config.ini settings."""
        try:
            import pyodbc

            host = CFG.get('database', 'host')
            port = CFG.get('database', 'port')
            database = CFG.get('database', 'database')
            user = CFG.get('database', 'user')
            password = CFG.get('database', 'password')

            # Try ODBC Driver 17 first, fallback to 13, then SQL Server native
            drivers = [
                'ODBC Driver 17 for SQL Server',
                'ODBC Driver 13 for SQL Server',
                'SQL Server',
            ]

            connected = False
            for driver in drivers:
                try:
                    conn_str = (
                        f"DRIVER={{{driver}}};"
                        f"SERVER={host},{port};"
                        f"DATABASE={database};"
                        f"UID={user};"
                        f"PWD={password};"
                    )
                    self.conn = pyodbc.connect(conn_str)
                    print(f"  🗄️  Connected to SQL Server: {host}/{database}")
                    print(f"       Driver: {driver}")
                    print(f"       Table: {self.table} ({self.card_col}, {self.size_col}, {self.qty_col})")
                    connected = True
                    break
                except Exception:
                    continue

            if not connected:
                raise Exception(
                    f"Cannot connect to SQL Server {host}/{database}\n"
                    "  Check config.ini and ensure ODBC drivers are installed."
                )

        except ImportError:
            print("❌ pyodbc not installed. Run: pip install pyodbc")
            raise
        except Exception as e:
            print(f"❌ SQL Server connection failed: {e}")
            raise

    def lookup_card(self, card_no):
        """
        Query card data from configured table.
        Always picks the most-recently-inserted row (ORDER BY insert_time_col DESC)
        so that if a CardNo appears more than once the latest record wins.
        Returns: (SizeName, CutQty) or None if not found.
        """
        try:
            cursor = self.conn.cursor()

            if self.use_sqlserver:
                query = (
                    f"SELECT TOP 1 {self.size_col}, {self.qty_col} "
                    f"FROM dbo.{self.table} "
                    f"WHERE {self.card_col} = ? "
                    f"ORDER BY [{self.time_col}] DESC"
                )
            else:
                query = (
                    f"SELECT {self.size_col}, {self.qty_col} "
                    f"FROM {self.table} "
                    f"WHERE {self.card_col} = ? "
                    f'ORDER BY "{self.time_col}" DESC '
                    f"LIMIT 1"
                )

            cursor.execute(query, (card_no,))
            row = cursor.fetchone()

            if row is None:
                return None

            return (row[0], row[1])

        except Exception as e:
            print(f"  ❌ DB query error: {e}")
            return None

    def get_all_cards(self):
        """Get all cards for the dashboard display, newest first (ORDER BY insert_time_col DESC)."""
        try:
            cursor = self.conn.cursor()

            if self.use_sqlserver:
                query = (
                    f"SELECT {self.card_col}, {self.size_col}, {self.qty_col} "
                    f"FROM dbo.{self.table} "
                    f"ORDER BY [{self.time_col}] DESC"
                )
            else:
                query = (
                    f"SELECT {self.card_col}, {self.size_col}, {self.qty_col} "
                    f"FROM {self.table} "
                    f'ORDER BY "{self.time_col}" DESC'
                )

            cursor.execute(query)
            rows = cursor.fetchall()
            return [(r[0], r[1], r[2]) for r in rows]

        except Exception as e:
            print(f"  ❌ DB query error: {e}")
            return []

    def close(self):
        if self.conn:
            self.conn.close()
