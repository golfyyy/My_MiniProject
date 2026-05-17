import json
import os
from pathlib import Path


def load_dotenv(project_root):
    env_path = Path(project_root) / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _merge_learned_params(settings, project_root):
    learned_path = Path(project_root) / "data" / "learned_params.json"
    if not learned_path.exists():
        return settings

    try:
        with learned_path.open("r", encoding="utf-8") as f:
            learned = json.load(f)
        learned_params = learned.get("params", {})
        if isinstance(learned_params, dict):
            settings.setdefault("params", {})
            settings["params"].update(learned_params)
    except (json.JSONDecodeError, OSError):
        pass
    return settings


def load_settings(project_root):
    project_root = Path(project_root)
    settings_path = project_root / "config" / "settings.json"
    load_dotenv(project_root)

    with settings_path.open("r", encoding="utf-8") as f:
        settings = json.load(f)

    env_overrides = {
        "discord_webhook_url": "DISCORD_WEBHOOK_URL",
        "discord_bot_token": "DISCORD_BOT_TOKEN",
        "mt5_login": "MT5_LOGIN",
        "mt5_password": "MT5_PASSWORD",
        "mt5_server": "MT5_SERVER",
    }
    for setting_key, env_key in env_overrides.items():
        env_value = os.getenv(env_key)
        if env_value:
            settings[setting_key] = env_value

    settings.setdefault("timeframe_name", "H1")
    settings.setdefault("higher_timeframe", 16388)
    settings.setdefault("higher_timeframe_name", "H4")
    settings.setdefault("point_value", 0.01)
    settings.setdefault("entry_tolerance_points", 120)
    settings.setdefault("setup_confidence_threshold", 0.62)
    settings.setdefault("confidence_threshold", 0.75)
    settings.setdefault("trigger_confidence_threshold", 0.82)
    settings.setdefault("sure_shot_threshold", 0.88)
    settings.setdefault("signal_cooldown_minutes", 30)
    settings.setdefault("max_signal_age_minutes", 180)
    settings.setdefault("trading_enabled", False)
    settings.setdefault("news_currencies", ["USD"])
    settings.setdefault("news_confidence_penalty", 0.08)
    settings.setdefault(
        "market_regime",
        {
            "name": "2026_structural_bull",
            "bull_bias_boost": 0.05,
            "counter_trend_sell_penalty": 0.04,
            "high_atr_daily_threshold": 40,
            "reduce_size_above_atr": True,
        },
    )
    settings.setdefault(
        "session_filter",
        {
            "golden_window_utc": [13, 17],
            "asian_session_utc": [22, 7],
            "golden_window_boost": 0.05,
            "asian_scalp_penalty": 0.06,
        },
    )
    settings.setdefault(
        "risk",
        {
            "risk_per_trade_pct": 1.0,
            "max_risk_per_trade_pct": 2.0,
            "atr_stop_multiplier_scalp": 1.0,
            "atr_stop_multiplier_day": 1.35,
            "atr_stop_multiplier_swing": 1.7,
            "atr_take_profit_multiplier_scalp": 1.2,
            "atr_take_profit_multiplier_day": 1.8,
            "atr_take_profit_multiplier_swing": 2.5,
            "reduce_lot_when_atr_above": 40,
            "lot_reduction_factor": 0.5,
        },
    )

    params = settings.setdefault("params", {})
    params.setdefault("stop_loss_points", settings.get("stop_loss_points", 500))
    params.setdefault("take_profit_points", settings.get("take_profit_points", 1000))
    params.setdefault("point_value", settings["point_value"])
    params.setdefault("atr_period", 14)
    params.setdefault("risk_reward_ratio", 1.8)
    params.setdefault("confidence_threshold", settings["confidence_threshold"])
    params.setdefault("ema_periods", [9, 21, 50, 200])
    params.setdefault("bollinger_period", 20)
    params.setdefault("bollinger_std", 2.0)
    params.setdefault("volume_spike_multiplier", 1.5)
    params.setdefault("scalp_target_points", [500, 1500])
    params.setdefault("psychological_level_step", 50)
    params.setdefault("market_regime", settings["market_regime"])
    params.setdefault("session_filter", settings["session_filter"])
    params.setdefault("risk", settings["risk"])

    if "analysis_timeframes" not in settings:
        settings["analysis_timeframes"] = [
            {
                "name": "M5",
                "value": 5,
                "role": "scalp",
                "weight": 0.85,
            },
            {
                "name": settings["timeframe_name"],
                "value": settings["timeframe"],
                "role": "signal",
                "weight": 1.0,
            },
            {
                "name": settings["higher_timeframe_name"],
                "value": settings["higher_timeframe"],
                "role": "trend",
                "weight": 1.35,
            },
        ]

    settings = _merge_learned_params(settings, project_root)
    return settings
