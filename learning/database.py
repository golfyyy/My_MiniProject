import sqlite3
import json
from datetime import datetime, timedelta

class SignalDatabase:
    """จัดการการเก็บข้อมูลสัญญาณและประวัติการเทรดเพื่อการเรียนรู้"""
    def __init__(self, db_path="data/signals_history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # ตารางเก็บสัญญาณที่ส่งออกไป
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    direction TEXT,
                    entry_price REAL,
                    sl REAL,
                    tp REAL,
                    strategy TEXT,
                    params_used TEXT,
                    timestamp DATETIME,
                    status TEXT DEFAULT 'PENDING',
                    outcome REAL DEFAULT NULL
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp)')
            # ตารางเก็บสถิติการเรียนรู้
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS learning_stats (
                    param_name TEXT PRIMARY KEY,
                    current_value REAL,
                    win_rate REAL,
                    last_updated DATETIME
                )
            ''')
            conn.commit()

    def save_signal(self, symbol, direction, entry, sl, tp, strategy, params):
        """บันทึกสัญญาณที่ส่งออกไปเพื่อติดตามผล"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO signals (symbol, direction, entry_price, sl, tp, strategy, params_used, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, direction, entry, sl, tp, strategy, json.dumps(params), datetime.now()))
            conn.commit()
            return cursor.lastrowid

    def update_signal_outcome(self, signal_id, status, outcome=None):
        """อัปเดตผลลัพธ์ของสัญญาณ (TP/SL/EXPIRED)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE signals SET status = ?, outcome = ? WHERE id = ?
            ''', (status, outcome, signal_id))
            conn.commit()

    def expire_stale_signals(self, max_age_minutes):
        """Mark old pending signals as expired before live monitoring."""
        if not max_age_minutes:
            return 0

        cutoff = datetime.now() - timedelta(minutes=float(max_age_minutes))
        expired_ids = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, timestamp FROM signals WHERE status = "PENDING"')
            for signal_id, ts in cursor.fetchall():
                try:
                    timestamp = datetime.fromisoformat(str(ts))
                except ValueError:
                    continue
                if timestamp < cutoff:
                    expired_ids.append(signal_id)

            if expired_ids:
                cursor.executemany(
                    'UPDATE signals SET status = "EXPIRED", outcome = 0 WHERE id = ?',
                    [(signal_id,) for signal_id in expired_ids],
                )
                conn.commit()
        return len(expired_ids)

    def get_pending_signals(self):
        """ดึงสัญญาณที่ยังไม่รู้ผลลัพธ์"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM signals WHERE status = "PENDING"')
            return cursor.fetchall()
