import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

logger = logging.getLogger("GoldAI.NewsFetcher")


class NewsFetcher:
    """ดึงข้อมูลข่าวสารจาก Forex Factory"""
    def __init__(self):
        self.url = "https://www.forexfactory.com/calendar"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self._cache_until = datetime.min
        self._cache = []

    def get_high_impact_news(self):
        """
        ดึงข่าวที่มีผลกระทบสูง (High Impact/Red Folder)
        """
        if datetime.now() < self._cache_until:
            return self._cache

        try:
            response = requests.get(self.url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                return self._cache

            soup = BeautifulSoup(response.content, 'html.parser')
            high_impact_events = []

            # ค้นหาแถวของข่าว
            events = soup.find_all('tr', class_='calendar__row')
            for event in events:
                # ตรวจสอบ impact cell
                impact_cell = event.find('td', class_='calendar__impact')
                impact_class = " ".join(impact_cell.get("class", [])) if impact_cell else ""
                impact_text = impact_cell.get_text(" ", strip=True).lower() if impact_cell else ""
                title_text = " ".join(tag.get("title", "") for tag in impact_cell.find_all(True)) if impact_cell else ""
                is_high_impact = "high" in impact_class.lower() or "high" in impact_text or "high" in title_text.lower()
                if impact_cell and is_high_impact:
                    currency_cell = event.find('td', class_='calendar__currency')
                    event_cell = event.find('td', class_='calendar__event')
                    time_cell = event.find('td', class_='calendar__time')
                    currency = currency_cell.text.strip() if currency_cell else "N/A"
                    event_name = event_cell.text.strip() if event_cell else "Unknown event"
                    time_val = time_cell.text.strip() if time_cell else "N/A"
                    high_impact_events.append({
                        "currency": currency,
                        "event": event_name,
                        "time": time_val,
                        "impact": "High"
                    })

            self._cache = high_impact_events
            self._cache_until = datetime.now() + timedelta(minutes=5)
            return high_impact_events
        except Exception as e:
            logger.warning("News fetch failed, using cache if available: %s", e)
            return self._cache
