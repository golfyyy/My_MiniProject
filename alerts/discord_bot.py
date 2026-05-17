import discord
from discord.ext import commands
import requests

class SignalFormatter:
    """เปลี่ยนข้อมูล Signal ให้เป็นรูปแบบการ์ดที่สวยงามใน Discord"""
    @staticmethod
    def _fmt_price(value):
        return f"${float(value):.2f}" if value is not None else "N/A"

    @staticmethod
    def _limit(text, length=1000):
        text = str(text or "N/A")
        return text if len(text) <= length else text[: length - 3] + "..."

    @staticmethod
    def format_signal(
        symbol,
        signal,
        entry,
        sl,
        tp,
        reasoning,
        confidence="Medium",
        news="No major news",
        mode="ENTRY_TRIGGER",
        timeframe="N/A",
        current_price=None,
        ideal_entry=None,
        entry_zone=None,
        hold_recommendation="N/A",
        risk_plan=None,
        technique_summary="N/A",
    ):
        # สร้าง Embed แบบดิบเพื่อใช้กับ Webhook (เนื่องจาก Webhook ไม่รองรับ discord.Embed object โดยตรง)
        is_buy = "BUY" in signal
        is_sell = "SELL" in signal
        direction_text = "🟢 BUY" if is_buy else "🔴 SELL" if is_sell else "🟡 WAIT"
        color = 65280 if is_buy else 16711680 if is_sell else 16798080
        mode_descriptions = {
            "ENTRY_TRIGGER": "🎯 เข้าเทรดได้ — ราคาอยู่ในโซนที่เหมาะสม",
            "🎯 ENTRY NOW": "🎯 เข้าเทรดได้ — ราคาอยู่ในโซนที่เหมาะสม",
            "STRONG_SETUP": "🔥 ทิศทางแรง — รอราคาเข้าโซน",
            "🔥 STRONG SETUP": "🔥 ทิศทางแรง — รอราคาเข้าโซน",
            "SURE_SHOT": "🚀 โมเมนตัมสูง — พิจารณาเข้าทันที",
            "🚀 SURE-SHOT": "🚀 โมเมนตัมสูง — พิจารณาเข้าทันที",
            "SETUP": "🔔 เตรียมตัว — เริ่มเฝ้าระวัง",
            "🔔 SETUP": "🔔 เตรียมตัว — เริ่มเฝ้าระวัง",
        }
        mode_label = mode_descriptions.get(mode, str(mode))
        if entry_zone:
            zone_text = f"{SignalFormatter._fmt_price(entry_zone[0])} - {SignalFormatter._fmt_price(entry_zone[1])}"
        else:
            zone_text = "N/A"
        risk_text = "N/A"
        if isinstance(risk_plan, dict):
            risk_text = risk_plan.get("text", "N/A")
        elif risk_plan:
            risk_text = str(risk_plan)

        embed = {
            "title": f"🚨 GOLD AI SIGNAL: {symbol} 🚨",
            "description": f"**Mode**: {mode_label}\n**Direction**: {direction_text}",
            "color": color,
            "fields": [
                {"name": "Best Entry", "value": SignalFormatter._fmt_price(ideal_entry or entry), "inline": True},
                {"name": "Current Price", "value": SignalFormatter._fmt_price(current_price or entry), "inline": True},
                {"name": "Timeframe", "value": str(timeframe), "inline": True},
                {"name": "Entry Zone", "value": zone_text, "inline": True},
                {"name": "Stop Loss", "value": SignalFormatter._fmt_price(sl), "inline": True},
                {"name": "Take Profit", "value": SignalFormatter._fmt_price(tp), "inline": True},
                {"name": "Confidence", "value": f"{confidence}", "inline": True},
                {"name": "Hold Plan", "value": SignalFormatter._limit(hold_recommendation, 500), "inline": True},
                {"name": "Risk Plan", "value": SignalFormatter._limit(risk_text, 500), "inline": False},
                {"name": "Technique Mix", "value": SignalFormatter._limit(technique_summary), "inline": False},
                {"name": "Reasoning", "value": SignalFormatter._limit(reasoning), "inline": False},
                {"name": "News Impact", "value": SignalFormatter._limit(news), "inline": False},
            ],
            "footer": {"text": "Gold AI Self-Learning System | Signal-Only Mode"}
        }
        return embed

class DiscordBot:
    """จัดการการส่งข้อความและคำสั่งใน Discord"""
    def __init__(self, token, webhook_url):
        self.token = token
        self.webhook_url = webhook_url
        self.intents = discord.Intents.default()
        self.intents.message_content = True
        self.bot = commands.Bot(command_prefix='!', intents=self.intents)

    def send_signal_card(self, symbol, signal, entry, sl, tp, reasoning, confidence="Medium", news="No major news", **kwargs):
        """ส่งสัญญาณการเทรดในรูปแบบ Embed Card"""
        if not self.webhook_url:
            print("Discord webhook is not configured; skipping signal notification.")
            return False

        embed_data = SignalFormatter.format_signal(symbol, signal, entry, sl, tp, reasoning, confidence, news, **kwargs)

        payload = {"embeds": [embed_data]}
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code != 204:
                print(f"❌ Discord Webhook Error: {response.status_code}")
                return False
            return True
        except Exception as e:
            print(f"❌ Discord Webhook Exception: {e}")
            return False

    async def start(self):
        if not self.token:
            print("Discord bot token is not configured; command bot is disabled.")
            return
        await self.bot.start(self.token)

    def get_bot_instance(self):
        return self.bot
