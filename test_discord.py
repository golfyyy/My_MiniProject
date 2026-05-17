import requests
import sys
from config.runtime import load_settings

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def test_notification():
    config = load_settings(".")
    webhook_url = config.get("discord_webhook_url", "")
    if not webhook_url:
        print("❌ ไม่พบ DISCORD_WEBHOOK_URL ใน .env หรือ config/settings.json")
        return

    print("🚀 กำลังทดสอบส่งข้อความเข้า Discord...")
    payload = {"content": "🔔 ทดสอบการแจ้งเตือนจาก Python! ถ้าเห็นข้อความนี้แสดงว่าการเชื่อมต่อสำเร็จแล้ว 🎉"}

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 204:
            print("✅ ส่งข้อความสำเร็จ! โปรดเช็คใน Discord ของคุณ")
        else:
            print(f"❌ ส่งไม่สำเร็จ รหัสข้อผิดพลาด: {response.status_code}")
            print(f"รายละเอียด: {response.text}")
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการเชื่อมต่อ: {e}")

if __name__ == "__main__":
    test_notification()
