#!/usr/bin/env python3
"""
Setup test SQLite database — mirrors SQL Server table dbo.tCutBundCard
Run this once to create sample data for Mac testing.
On Windows production, the app connects to SQL Server 2008 instead.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'factory_test.db')

def setup():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Mirror the SQL Server table structure
    c.execute('''
        CREATE TABLE IF NOT EXISTS tCutBundCard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            CardNo TEXT UNIQUE NOT NULL,
            SizeName TEXT NOT NULL DEFAULT '',
            CutQty INTEGER NOT NULL DEFAULT 0
        )
    ''')

    # Sample data — includes real RFID cards from hardware
    cards = [
        # ─── Real cards (from your RFID reader) ──────────
        ('0012556611', 'M',   6),
        ('0005199482', 'XL',  4),
        # ─── Test cards ──────────────────────────────────
        ('100001', 'S',   5),
        ('100002', 'M',   3),
        ('100003', 'L',   8),
        ('100004', 'XL',  10),
        ('100005', 'XXL', 2),
        ('100006', 'S',   15),
        ('100007', 'M',   0),   # zero qty — should not print
        ('100008', 'L',   7),
        ('100009', 'XL',  12),
        ('100010', 'XXL', 1),
    ]

    for card_no, size, qty in cards:
        c.execute('''
            INSERT OR REPLACE INTO tCutBundCard (CardNo, SizeName, CutQty)
            VALUES (?, ?, ?)
        ''', (card_no, size, qty))

    conn.commit()
    conn.close()

    print("✅ Test database created:", DB_PATH)
    print()
    print("📋 Sample cards (dbo.tCutBundCard):")
    print(f"  {'CardNo':<10} {'SizeName':<10} {'CutQty':<8}")
    print(f"  {'─'*10} {'─'*10} {'─'*8}")
    for card_no, size, qty in cards:
        print(f"  {card_no:<10} {size:<10} {qty:<8}")

if __name__ == '__main__':
    setup()
