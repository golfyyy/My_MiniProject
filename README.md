# Gold AI Hybrid Bot — Signal Edition

**English** | [ภาษาไทย](#ภาษาไทย)

A **signal-only** XAUUSD (gold) analysis system for MetaTrader 5. It combines multiple timeframes and techniques (SMC, order blocks, FVG, EMA/RSI, chart patterns), then sends layered trade alerts to **Discord**. It does **not** place orders automatically.

Repository: [github.com/golfyyy/My_MiniProject](https://github.com/golfyyy/My_MiniProject)

---

## Features

- **Signal-only mode** — no auto-trading; you decide entries manually
- **Multi-timeframe analysis** — M5, M15, H1, H4 with weighted voting
- **Layered signals** — SETUP → STRONG SETUP → ENTRY NOW → SURE-SHOT
- **Dynamic entry zones** — ATR-based zones instead of a single perfect price
- **News filter** — reduces confidence around high-impact Forex Factory events
- **Self-learning** — tracks TP/SL outcomes and adjusts technique weights and RSI thresholds locally

---

## Requirements

| Item | Notes |
|------|--------|
| **OS** | Windows (MT5 Python API is Windows-oriented) |
| **Python** | 3.10+ recommended |
| **MetaTrader 5** | Installed, logged in (Demo or Live) |
| **Discord** | Webhook URL (required for alerts) |
| **Broker** | Symbol `XAUUSD` (or change in config) |

---

## Quick start

### 1. Clone the repository

```powershell
git clone https://github.com/golfyyy/My_MiniProject.git
cd My_MiniProject
```

Or download ZIP from GitHub → **Code** → **Download ZIP**, then extract.

### 2. Install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configure secrets (local only — never commit)

```powershell
copy .env.example .env
copy config\settings.json.example config\settings.json
```

Edit **`.env`**:

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_BOT_TOKEN=          # optional — for Discord bot commands
MT5_LOGIN=                  # optional if MT5 is already logged in
MT5_PASSWORD=
MT5_SERVER=
```

Edit **`config/settings.json`** for thresholds, timeframes, and risk parameters (see [Configuration](#configuration)).

### 4. Run MetaTrader 5

- Open MT5 and log in to your account
- Ensure **XAUUSD** is visible in Market Watch
- Algo trading button does not need to be on for **signal-only** mode, but MT5 must be running

### 5. Start the bot

```powershell
python main.py
```

Logs are written to `logs/gold_ai.log` and the console.

---

## Signal types (Discord)

| Mode | When it fires |
|------|----------------|
| 🔔 **SETUP** | Minimum confidence met; start watching |
| 🔥 **STRONG SETUP** | High confidence, price not yet in the ideal entry zone |
| 🎯 **ENTRY NOW** | High confidence + price in the optimal zone |
| 🚀 **SURE-SHOT** | Very high confidence (≥ 0.88) + price in momentum zone |

Default thresholds (editable in `config/settings.json`):

- `setup_confidence_threshold`: 0.62  
- `trigger_confidence_threshold`: 0.82  
- `sure_shot_threshold`: 0.88  

---

## Configuration

| File | Purpose |
|------|---------|
| `config/settings.json` | Main settings (copy from `.example`; **gitignored**) |
| `.env` | Discord webhook/token, optional MT5 credentials (**gitignored**) |
| `data/technique_weights.json` | Learned technique weights (auto-created, **gitignored**) |
| `data/learned_params.json` | Learned RSI adjustments (auto-created, **gitignored**) |

Key settings in `settings.json`:

- `analysis_timeframes` — which TFs to analyze and their weights  
- `signal_cooldown_minutes` — minimum time between similar alerts (default 30)  
- `trading_enabled` — must stay `false` for signal-only operation  

---

## Project structure

```
My_MiniProject/
├── main.py                 # Main engine loop
├── config/
│   ├── runtime.py          # Loads settings + .env + learned params
│   └── settings.json.example
├── data/
│   ├── mt5_client.py       # MT5 connection & bars
│   ├── news_fetcher.py     # Forex Factory high-impact news
│   └── storage.py          # Analysis history DB
├── strategies/
│   ├── hybrid_strategy.py  # Ensemble strategy
│   └── chart_patterns.py   # SMC, S/R, patterns
├── alerts/
│   └── discord_bot.py      # Discord webhook embeds
├── learning/
│   ├── database.py         # Signal outcome tracking
│   ├── adaptive_weights.py # Technique weight learning
│   └── optimizer.py        # RSI threshold tuning
└── test_*.py               # Local tests
```

---

## Tests

```powershell
python test_init.py              # Strategy smoke test (no MT5)
python test_run.py               # Engine cycle with mocks
python test_auto_connection.py   # MT5 connection + live price
python test_discord.py           # Plain webhook message
python test_signal.py            # Full signal card to Discord
```

---

## Files you must NOT upload to GitHub

These are listed in `.gitignore`:

- `.env`
- `config/settings.json`
- `*.db`, `logs/*.log`
- `data/technique_weights.json`, `data/learned_params.json`

If a token was ever committed, **rotate** your Discord webhook and MT5 password immediately.

---

## Disclaimer

This software is for **educational and research purposes**. Trading gold involves substantial risk. Past signal performance does not guarantee future results. The authors are not responsible for any financial losses.

---

<a id="ภาษาไทย"></a>

# Gold AI Hybrid Bot — โหมดสัญญาณ (Signal Edition)

[English](#gold-ai-hybrid-bot--signal-edition) | **ภาษาไทย**

ระบบวิเคราะห์สัญญาณทองคำ **XAUUSD** ผ่าน **MetaTrader 5** แบบ **ส่งสัญญาณอย่างเดียว (Signal-Only)** ไม่เปิดออเดอร์อัตโนมัติ รวมหลายไทม์เฟรมและเทคนิค (SMC, Order Block, FVG, EMA/RSI, แพทเทิร์น) แล้วแจ้งเตือนไป **Discord**

Repo: [github.com/golfyyy/My_MiniProject](https://github.com/golfyyy/My_MiniProject)

---

## จุดเด่น

- **ปลอดภัย** — ไม่เทรดอัตโนมัติ คุณเป็นคนตัดสินใจเข้าเอง
- **วิเคราะห์หลาย TF** — M5, M15, H1, H4 โหวตรวมกัน
- **สัญญาณแบบชั้น** — SETUP → STRONG SETUP → ENTRY NOW → SURE-SHOT
- **โซนเข้าแบบ Dynamic** — ใช้ ATR กำหนดความกว้างโซน
- **กรองข่าว** — ลดความมั่นใจช่วงข่าวแรง (Forex Factory)
- **เรียนรู้จากผลสัญญาณ** — ปรับน้ำหนักเทคนิคและ RSI จาก TP/SL ในเครื่อง

---

## สิ่งที่ต้องมี

| รายการ | หมายเหตุ |
|--------|----------|
| **Windows** | ไลบรารี MT5 ใช้กับ Windows เป็นหลัก |
| **Python** | แนะนำ 3.10 ขึ้นไป |
| **MetaTrader 5** | ติดตั้งและ Login แล้ว |
| **Discord** | Webhook URL (จำเป็นสำหรับแจ้งเตือน) |
| **โบรกเกอร์** | สัญลักษณ์ XAUUSD (หรือแก้ใน config) |

---

## วิธีโหลดและติดตั้ง

### 1. โหลดโปรเจกต์

**แบบ Git:**

```powershell
git clone https://github.com/golfyyy/My_MiniProject.git
cd My_MiniProject
```

**แบบ ZIP:** ที่ GitHub → **Code** → **Download ZIP** แล้วแตกไฟล์

### 2. ติดตั้งไลบรารี

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. ตั้งค่า (เก็บในเครื่องเท่านั้น — ห้าม commit)

```powershell
copy .env.example .env
copy config\settings.json.example config\settings.json
```

แก้ไฟล์ **`.env`**:

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_BOT_TOKEN=          # ไม่บังคับ
MT5_LOGIN=                  # ไม่บังคับ ถ้า login MT5 ไว้แล้ว
MT5_PASSWORD=
MT5_SERVER=
```

แก้ **`config/settings.json`** ตามต้องการ (เกณฑ์ confidence, ไทม์เฟรม, ความเสี่ยง)

### 4. เปิด MetaTrader 5

- Login บัญชี Demo หรือ Real
- มีสัญลักษณ์ **XAUUSD** ใน Market Watch
- โหมดสัญญาณไม่จำเป็นต้องเปิดปุ่ม Algo Trading แต่ MT5 ต้องเปิดอยู่

### 5. รันบอท

```powershell
python main.py
```

บันทึก log ที่ `logs/gold_ai.log` และแสดงบนหน้าจอ

---

## ความหมายสัญญาณใน Discord

| สัญญาณ | ความหมาย |
|--------|----------|
| 🔔 **SETUP** | เริ่มมีเงื่อนไข — เตรียมเฝ้าดู |
| 🔥 **STRONG SETUP** | มั่นใจสูง แต่ราคายังไม่ถึงโซนเข้าที่ดีที่สุด |
| 🎯 **ENTRY NOW** | ราคาอยู่ในโซนเข้า + เงื่อนไขครบ |
| 🚀 **SURE-SHOT** | มั่นใจมาก (≥ 0.88) + โมเมนตัมดี |

ค่าเริ่มต้นใน `config/settings.json`:

- `setup_confidence_threshold`: 0.62  
- `trigger_confidence_threshold`: 0.82  
- `sure_shot_threshold`: 0.88  

---

## ไฟล์ตั้งค่า

| ไฟล์ | หน้าที่ |
|------|--------|
| `config/settings.json` | ตั้งค่าหลัก (คัดลอกจาก `.example`) |
| `.env` | Webhook / Token / MT5 (ถ้าต้องการ) |
| `data/technique_weights.json` | น้ำหนักเทคนิคที่เรียนรู้แล้ว (สร้างอัตโนมัติ) |
| `data/learned_params.json` | ค่า RSI ที่ปรับแล้ว (สร้างอัตโนมัติ) |

---

## โครงสร้างโปรเจกต์

```
My_MiniProject/
├── main.py                 # ลูปหลักวิเคราะห์และส่งสัญญาณ
├── config/                 # การตั้งค่า
├── data/                   # MT5, ข่าว, ฐานข้อมูลวิเคราะห์
├── strategies/             # กลยุทธ์ Hybrid + แพทเทิร์น
├── alerts/                 # Discord
├── learning/               # ติดตามผลสัญญาณ + ปรับน้ำหนัก
└── test_*.py               # ทดสอบ
```

---

## ทดสอบระบบ

```powershell
python test_init.py
python test_run.py
python test_auto_connection.py
python test_discord.py
python test_signal.py
```

---

## ไฟล์ที่ห้ามอัป GitHub

- `.env`, `config/settings.json`  
- `*.db`, `logs/*.log`  
- `data/technique_weights.json`, `data/learned_params.json`  

ถ้าเผลออัป Token ขึ้น GitHub ให้เปลี่ยน Webhook และรหัส MT5 ทันที

---

## คำเตือน

โปรแกรมนี้มีไว้เพื่อ **การศึกษาและทดลอง** การเทรดทองมีความเสี่ยงสูง ผลสัญญาณในอดีตไม่รับประกันผลในอนาคต ผู้พัฒนาไม่รับผิดชอบต่อความเสียหายทางการเงิน

---

## License

No license file is included yet. Use and modify at your own responsibility.
