import os
import sys
import logging

from config.runtime import load_settings
from data.mt5_client import MT5Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TestMT5Connection")


def test_mt5_connection():
    """Signal-only project: verify MT5 connectivity and price feed (no orders)."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    config = load_settings(project_root)
    symbol = config.get("symbol", "XAUUSD")

    client = MT5Client(
        symbol,
        login=config.get("mt5_login"),
        password=config.get("mt5_password"),
        server=config.get("mt5_server"),
    )
    if not client.connect():
        logger.error("MT5 connection failed")
        return False

    try:
        prices = client.get_current_price()
        if not prices:
            logger.error("Could not read current price for %s", symbol)
            return False

        ask, bid = prices
        point = client.get_point()
        first_tf = config["analysis_timeframes"][0]["value"]
        rates = client.get_rates(first_tf, count=10)
        logger.info("Connected to %s | ask=%.2f bid=%.2f point=%s", symbol, ask, bid, point)
        logger.info("Latest bars fetched: %s rows", 0 if rates is None else len(rates))
        return True
    finally:
        client.shutdown()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ok = test_mt5_connection()
    sys.exit(0 if ok else 1)
