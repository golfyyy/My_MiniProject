import asyncio
import json
import os
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class MT5Client:
    def __init__(self, symbol, login=None, password=None, server=None):
        self.symbol = symbol
        self.connected = False

    def connect(self):
        self.connected = True
        print("Mock MT5: Connected")
        return True

    def ensure_connection(self):
        return self.connected

    def shutdown(self):
        print("Mock MT5: Shutdown")
        self.connected = False

    def get_point(self):
        return 0.01

    def get_rates(self, timeframe, count=300):
        import numpy as np
        import pandas as pd

        close = 2300 + np.cumsum(np.random.normal(0, 1.5, count))
        open_ = close + np.random.normal(0, 0.8, count)
        high = np.maximum(open_, close) + np.abs(np.random.normal(0.8, 0.4, count))
        low = np.minimum(open_, close) - np.abs(np.random.normal(0.8, 0.4, count))
        df = pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": np.random.rand(count) * 100,
            }
        )
        df["time"] = pd.date_range(end=pd.Timestamp.now(), periods=count, freq="1min")
        return df

    def get_current_price(self):
        import numpy as np

        ask = float(np.random.rand() * 1000 + 1000)
        bid = ask - float(np.random.rand() * 0.5)
        return ask, bid


class NewsFetcher:
    def get_high_impact_news(self, *args, **kwargs):
        return []



class DiscordBot:
    def __init__(self, token, webhook_url):
        self.token = token
        self.webhook_url = webhook_url

    def send_signal_card(self, symbol, signal, entry, sl, tp, reasoning, confidence="Medium", news="No major news", **kwargs):
        print(f"Mock Discord: {symbol} {signal} entry={entry} mode={kwargs.get('mode')}")
        return True

    async def start(self):
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass


sys.modules["data.mt5_client"] = sys.modules[__name__]
sys.modules["data.news_fetcher"] = sys.modules[__name__]
sys.modules["alerts.discord_bot"] = sys.modules[__name__]

from main import GoldAIEngine
from learning.adaptive_weights import AdaptiveWeighting
from learning.database import SignalDatabase
from learning.optimizer import LearningOptimizer
from data.storage import SignalStorage


async def test_engine():
    print("Creating GoldAIEngine with mocked dependencies...")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        engine = GoldAIEngine()
        engine.db = SignalDatabase(os.path.join(tmpdir, "signals_history.db"))
        engine.storage = SignalStorage(os.path.join(tmpdir, "self_generated_data.db"))
        engine.optimizer = LearningOptimizer(learned_params_path=os.path.join(tmpdir, "learned_params.json"))
        engine.adaptive_weights = AdaptiveWeighting(
            storage_path=os.path.join(tmpdir, "self_generated_data.db"),
            weights_path=os.path.join(tmpdir, "technique_weights.json"),
            signal_db_path=os.path.join(tmpdir, "signals_history.db"),
            initial_weights=engine.config.get("technique_weights"),
        )

        original_sleep = asyncio.sleep

        async def short_sleep(seconds):
            if seconds > 10:
                await original_sleep(1)
            else:
                await original_sleep(seconds)

        asyncio.sleep = short_sleep
        try:
            engine.mt5.connect()
            bot_task = asyncio.create_task(engine.bot.start())
            for i in range(2):
                print(f"\n--- Cycle {i + 1} ---")
                await engine.run_analysis_cycle()
                await engine.monitor_signals()
                await asyncio.sleep(60)
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
        finally:
            engine.mt5.shutdown()
            asyncio.sleep = original_sleep
    print("\nTest completed successfully.")


if __name__ == "__main__":
    asyncio.run(test_engine())
