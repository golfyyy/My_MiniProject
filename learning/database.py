import sqlite3
import json
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Any, Optional

class SignalDatabase:
    """จัดการการเก็บข้อมูลสัญญาณและประวัติการเทรดเพื่อการเรียนรู้"""
    def __init__(self, db_path: str = "data/signals_history.db") -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """สร้างการเชื่อมต่อฐานข้อมูลพร้อมเปิดใช้งาน WAL mode"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
        except sqlite3.OperationalError:
            pass
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
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

    def save_signal(self, symbol: str, direction: str, entry: float, sl: float, tp: float, strategy: str, params: dict) -> int:
        """บันทึกสัญญาณที่ส่งออกไปเพื่อติดตามผล"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO signals (symbol, direction, entry_price, sl, tp, strategy, params_used, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, direction, entry, sl, tp, strategy, json.dumps(params), datetime.now(timezone.utc).isoformat()))
            conn.commit()
            return cursor.lastrowid

    def update_signal_outcome(self, signal_id: int, status: str, outcome: Optional[float] = None) -> None:
        """อัปเดตผลลัพธ์ของสัญญาณ (TP/SL/EXPIRED)"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE signals SET status = ?, outcome = ? WHERE id = ?
            ''', (status, outcome, signal_id))
            conn.commit()

    def expire_stale_signals(self, max_age_minutes: float) -> int:
        """Mark old pending signals as expired before live monitoring."""
        if not max_age_minutes:
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=float(max_age_minutes))
        expired_ids: List[int] = []
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, timestamp FROM signals WHERE status = "PENDING"')
            for signal_id, ts in cursor.fetchall():
                try:
                    timestamp = datetime.fromisoformat(str(ts))
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
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

    def get_pending_signals(self) -> List[Tuple[Any, ...]]:
        """ดึงสัญญาณที่ยังไม่รู้ผลลัพธ์"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM signals WHERE status = "PENDING"')
            return cursor.fetchall()

