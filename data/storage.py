import json
import sqlite3
import os
from datetime import datetime, timezone
from typing import List, Dict, Any

class SignalStorage:
    """Stores self-generated data for each analysis cycle to enable self-improvement."""
    def __init__(self, db_path: str = "data/self_generated_data.db") -> None:
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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analysis_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    symbol TEXT,
                    timeframe TEXT,
                    technique TEXT,
                    signal_direction TEXT,
                    confidence REAL,
                    features TEXT,          -- JSON string of indicator values
                    decision_metrics TEXT,  -- JSON string of weights, etc.
                    hold_recommendation TEXT
                )
            ''')
            conn.commit()

    def save_analysis(
        self,
        symbol: str,
        timeframe: str,
        technique: str,
        signal_direction: str,
        confidence: float,
        features: dict,
        decision_metrics: dict,
        hold_recommendation: str
    ) -> None:
        """Save one analysis cycle's data."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO analysis_data (timestamp, symbol, timeframe, technique, signal_direction, confidence, features, decision_metrics, hold_recommendation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now(timezone.utc).isoformat(),
                symbol,
                timeframe,
                technique,
                signal_direction,
                confidence,
                json.dumps(features),
                json.dumps(decision_metrics),
                hold_recommendation
            ))
            conn.commit()

    def get_recent_data(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Retrieve recent analysis data for learning."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, symbol, timeframe, technique, signal_direction, confidence, features, decision_metrics, hold_recommendation
                FROM analysis_data
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            # Convert JSON strings back to dicts
            data = []
            for row in rows:
                ts, sym, tf, tech, sig_dir, conf, feat_json, dec_json, hold = row
                data.append({
                    'timestamp': ts,
                    'symbol': sym,
                    'timeframe': tf,
                    'technique': tech,
                    'signal_direction': sig_dir,
                    'confidence': conf,
                    'features': json.loads(feat_json) if feat_json else {},
                    'decision_metrics': json.loads(dec_json) if dec_json else {},
                    'hold_recommendation': hold
                })
            return data