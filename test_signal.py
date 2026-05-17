import os
import sys
from alerts.discord_bot import DiscordBot
from config.runtime import load_settings

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def test_discord_signal():
    config = load_settings(os.path.dirname(os.path.abspath(__file__)))
    if not config.get("discord_webhook_url"):
        print("❌ ไม่พบ DISCORD_WEBHOOK_URL ใน .env หรือ config/settings.json")
        return

    print("🚀 กำลังทดสอบส่ง Signal Card ไปยัง Discord...")

    # สร้าง Instance ของ DiscordBot
    bot = DiscordBot(config["discord_bot_token"], config["discord_webhook_url"])

    # จำลองข้อมูลสัญญาณ
    symbol = config["symbol"]
    signal = "BUY"
    entry = 2325.50
    sl = 2315.00
    tp = 2345.00
    reasoning = "✅ TEST SIGNAL: Price rejected 4H Order Block + RSI Oversold. (This is a test message)"
    confidence = "High (Test)"
    news = "⚠️ TEST: High Impact News expected in 1 hour"

    # ส่งการ์ด
    bot.send_signal_card(symbol, signal, entry, sl, tp, reasoning, confidence, news)

    print("✅ ส่งคำสั่งทดสอบแล้ว! โปรดเช็คใน Discord ของคุณว่าได้รับ 'Signal Card' หรือไม่")

if __name__ == "__main__":
    test_discord_signal()
