import logging
import requests
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

logger = logging.getLogger("GoldAI.NewsFetcher")


class NewsFetcher:
    """ดึงข้อมูลข่าวสารจาก Forex Factory API (JSON feed)"""
    def __init__(self) -> None:
        self.url: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        self._cache_until: datetime = datetime.min.replace(tzinfo=timezone.utc)
        self._cache: List[Dict[str, Any]] = []

    def get_high_impact_news(self, lookback_mins: float = 30.0, lookahead_mins: float = 90.0) -> List[Dict[str, Any]]:
        """
        ดึงข่าวที่มีผลกระทบสูง (High Impact) ที่อยู่ในช่วงเวลาพิจารณา
        """
        now = datetime.now(timezone.utc)

        if now < self._cache_until:
            all_events = self._cache
        else:
            try:
                response = requests.get(self.url, timeout=10)
                if response.status_code == 200:
                    self._cache = response.json()
                    self._cache_until = now + timedelta(minutes=5)
                    all_events = self._cache
                else:
                    logger.warning("News fetch failed with status %s, using cache", response.status_code)
                    all_events = self._cache
            except Exception as e:
                logger.warning("News fetch failed, using cache if available: %s", e)
                all_events = self._cache

        high_impact_events: List[Dict[str, Any]] = []
        for event in all_events:
            # Check impact
            impact = event.get("impact", "")
            if impact.lower() != "high":
                continue

            # Parse event date (e.g. "2026-05-26T21:30:00-04:00")
            date_str = event.get("date")
            if not date_str:
                continue

            try:
                event_date = datetime.fromisoformat(date_str)
                if event_date.tzinfo is None:
                    event_date = event_date.replace(tzinfo=timezone.utc)
                else:
                    event_date = event_date.astimezone(timezone.utc)
            except ValueError:
                continue

            # Check if event is within lookback and lookahead window
            start_window = now - timedelta(minutes=lookback_mins)
            end_window = now + timedelta(minutes=lookahead_mins)

            if start_window <= event_date <= end_window:
                high_impact_events.append({
                    "currency": event.get("country", "N/A"),
                    "event": event.get("title", "Unknown event"),
                    "time": event_date.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "impact": "High"
                })

        return high_impact_events

