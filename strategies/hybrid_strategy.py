import pandas as pd
import numpy as np
from datetime import datetime, timezone
from abc import ABC, abstractmethod
from .chart_patterns import ChartPatternRecognizer

DEFAULT_TIMEFRAME_NAME = "H1"


class BaseStrategy(ABC):
    """คลาสพื้นฐานสำหรับทุกกลยุทธ์การเทรด"""

    def __init__(self, params):
        self.params = params

    @abstractmethod
    def analyze(self, df, timeframe_name=None, role="signal"):
        """Return a normalized analysis result."""
        pass


class HybridStrategy(BaseStrategy):
    """EMA/RSI + SMC + Trend Line + Support/Resistance + Price Pattern ensemble."""

    def __init__(self, params):
        super().__init__(params)
        self.chart_patterns = ChartPatternRecognizer(params.get("atr_period", 14))
        self.technique_weights = {}

    def set_technique_weights(self, technique_weights):
        self.technique_weights = technique_weights or {}

    @staticmethod
    def _clip_confidence(value):
        return float(max(0.0, min(0.95, value)))

    def _technique_weight(self, technique_name, role):
        base = float(self.technique_weights.get(technique_name, 1.0))
        role_boosts = {
            "entry": {
                "SMC": 1.25,
                "SupplyDemand": 1.3,
                "OrderBlock": 1.25,
                "FVG": 1.2,
                "MarketStructure": 1.15,
                "SupportResistance": 1.2,
                "PricePattern": 1.15,
                "TrendLine": 0.95,
                "EMA_RSI": 0.9,
                "InstitutionalIndicators": 1.0,
            },
            "scalp": {
                "SMC": 1.1,
                "SupplyDemand": 1.2,
                "OrderBlock": 1.15,
                "FVG": 1.15,
                "MarketStructure": 1.0,
                "SupportResistance": 1.1,
                "PricePattern": 1.25,
                "TrendLine": 0.85,
                "EMA_RSI": 0.95,
                "InstitutionalIndicators": 1.15,
            },
            "signal": {
                "SMC": 1.1,
                "SupplyDemand": 1.15,
                "OrderBlock": 1.1,
                "FVG": 1.05,
                "MarketStructure": 1.15,
                "SupportResistance": 1.05,
                "PricePattern": 1.0,
                "TrendLine": 1.05,
                "EMA_RSI": 1.05,
                "InstitutionalIndicators": 1.1,
            },
            "trend": {
                "SMC": 0.85,
                "SupplyDemand": 0.9,
                "OrderBlock": 0.9,
                "FVG": 0.85,
                "MarketStructure": 1.2,
                "SupportResistance": 0.9,
                "PricePattern": 0.85,
                "TrendLine": 1.25,
                "EMA_RSI": 1.2,
                "InstitutionalIndicators": 1.2,
            },
        }
        return base * role_boosts.get(role, role_boosts["signal"]).get(technique_name, 1.0)

    def calculate_rsi(self, prices, period=14):
        deltas = pd.Series(prices).diff()
        gain = (deltas.where(deltas > 0, 0)).rolling(window=period).mean()
        loss = (-deltas.where(deltas < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    def calculate_ema(self, prices, period):
        return pd.Series(prices).ewm(span=period, adjust=False).mean()

    def calculate_bollinger(self, prices, period=20, std_multiplier=2.0):
        series = pd.Series(prices)
        mid = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = mid + std * std_multiplier
        lower = mid - std * std_multiplier
        return mid, upper, lower

    def calculate_atr(self, df, period=14):
        if len(df) < period + 2:
            return 0.0
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)
        prev_close = close.shift(1)
        tr = np.maximum(high - low, np.maximum((high - prev_close).abs(), (low - prev_close).abs()))
        atr = tr.rolling(window=period).mean().iloc[-1]
        return float(atr) if np.isfinite(atr) else 0.0

    def calculate_vwap(self, df):
        volume_col = "tick_volume" if "tick_volume" in df.columns else "volume"
        if volume_col not in df.columns:
            return float(df["close"].astype(float).iloc[-1])
        typical_price = (df["high"].astype(float) + df["low"].astype(float) + df["close"].astype(float)) / 3
        volume = df[volume_col].astype(float).replace(0, np.nan).fillna(1)
        vwap = (typical_price * volume).cumsum() / volume.cumsum()
        value = vwap.iloc[-1]
        return float(value) if np.isfinite(value) else float(df["close"].astype(float).iloc[-1])

    def _strategy_style(self, timeframe_name, role):
        if role == "scalp" or timeframe_name in ("M1", "M5", "M15"):
            return "scalp"
        if role == "trend" or timeframe_name in ("H4", "D1", "W1"):
            return "swing"
        return "day"

    def _session_context(self, role):
        session_cfg = self.params.get("session_filter", {})
        now_utc = datetime.now(timezone.utc)
        hour = now_utc.hour + now_utc.minute / 60
        golden_start, golden_end = session_cfg.get("golden_window_utc", [13, 17])
        asian_start, asian_end = session_cfg.get("asian_session_utc", [22, 7])
        in_golden = golden_start <= hour < golden_end
        in_asian = hour >= asian_start or hour < asian_end if asian_start > asian_end else asian_start <= hour < asian_end
        if in_golden:
            return {
                "name": "NYLON overlap",
                "confidence_adjustment": float(session_cfg.get("golden_window_boost", 0.05)),
                "reason": "Peak London-New York liquidity window",
            }
        if in_asian and role in ("scalp", "entry"):
            return {
                "name": "Asian session",
                "confidence_adjustment": -float(session_cfg.get("asian_scalp_penalty", 0.06)),
                "reason": "Lower liquidity; scalp entries require stronger confirmation",
            }
        return {"name": "Normal session", "confidence_adjustment": 0.0, "reason": "No special session filter"}

    def _volume_spike(self, df):
        volume_col = "tick_volume" if "tick_volume" in df.columns else "volume"
        if volume_col not in df.columns or len(df) < 5:
            return False, 1.0
        volume = df[volume_col].astype(float)
        recent_avg = float(volume.iloc[-4:-1].mean())
        current = float(volume.iloc[-1])
        ratio = current / max(recent_avg, 1.0)
        return ratio >= float(self.params.get("volume_spike_multiplier", 1.5)), ratio

    def _institutional_indicator_result(self, df):
        close_prices = df["close"].astype(float).values
        current_price = float(close_prices[-1])
        ema_periods = self.params.get("ema_periods", [9, 21, 50, 200])
        emas = {period: float(self.calculate_ema(close_prices, period).iloc[-1]) for period in ema_periods}
        ema9 = emas.get(9, current_price)
        ema21 = emas.get(21, current_price)
        ema50 = emas.get(50, current_price)
        ema200 = emas.get(200, current_price)
        vwap = self.calculate_vwap(df)
        bb_mid, bb_upper, bb_lower = self.calculate_bollinger(
            close_prices,
            self.params.get("bollinger_period", 20),
            self.params.get("bollinger_std", 2.0),
        )
        bb_mid_last = float(bb_mid.iloc[-1]) if np.isfinite(bb_mid.iloc[-1]) else current_price
        bb_upper_last = float(bb_upper.iloc[-1]) if np.isfinite(bb_upper.iloc[-1]) else current_price
        bb_lower_last = float(bb_lower.iloc[-1]) if np.isfinite(bb_lower.iloc[-1]) else current_price
        band_width = (bb_upper_last - bb_lower_last) / max(bb_mid_last, 1)
        volume_spike, volume_ratio = self._volume_spike(df)
        psych_step = float(self.params.get("psychological_level_step", 50))
        nearest_psych = round(current_price / psych_step) * psych_step if psych_step else current_price
        near_psych = abs(current_price - nearest_psych) <= max(current_price * 0.001, 1.0)

        bullish_stack = current_price > vwap and ema9 > ema21 > ema50 > ema200
        bearish_stack = current_price < vwap and ema9 < ema21 < ema50 < ema200
        volatility_expanding = band_width > 0.008

        if bullish_stack:
            confidence = 0.58 + (0.08 if volume_spike else 0.0) + (0.05 if volatility_expanding else 0.0)
            entry = max(vwap, min(ema21, current_price))
            return {
                "pattern": "InstitutionalIndicators",
                "confidence": self._clip_confidence(confidence),
                "bias": "BUY",
                "entry": float(entry),
                "levels": {
                    "vwap": vwap,
                    "ema9": ema9,
                    "ema21": ema21,
                    "ema50": ema50,
                    "ema200": ema200,
                    "nearest_psych": nearest_psych,
                    "volume_ratio": volume_ratio,
                },
                "reasoning": (
                    "EMA 9/21/50/200 bullish stack with price above VWAP"
                    + (" and volume spike" if volume_spike else "")
                    + (" near psychological level" if near_psych else "")
                ),
            }

        if bearish_stack:
            confidence = 0.56 + (0.08 if volume_spike else 0.0) + (0.04 if volatility_expanding else 0.0)
            entry = min(vwap, max(ema21, current_price))
            return {
                "pattern": "InstitutionalIndicators",
                "confidence": self._clip_confidence(confidence),
                "bias": "SELL",
                "entry": float(entry),
                "levels": {
                    "vwap": vwap,
                    "ema9": ema9,
                    "ema21": ema21,
                    "ema50": ema50,
                    "ema200": ema200,
                    "nearest_psych": nearest_psych,
                    "volume_ratio": volume_ratio,
                },
                "reasoning": (
                    "EMA 9/21/50/200 bearish stack with price below VWAP"
                    + (" and volume spike" if volume_spike else "")
                    + (" near psychological level" if near_psych else "")
                ),
            }

        return {
            "pattern": "InstitutionalIndicators",
            "confidence": 0.0,
            "bias": "NEUTRAL",
            "entry": current_price,
            "levels": {
                "vwap": vwap,
                "ema9": ema9,
                "ema21": ema21,
                "ema50": ema50,
                "ema200": ema200,
                "bb_upper": bb_upper_last,
                "bb_lower": bb_lower_last,
                "volume_ratio": volume_ratio,
            },
            "reasoning": "EMA/VWAP/Bollinger/Volume do not align cleanly",
        }

    def _ema_rsi_result(self, df):
        close_prices = df["close"].astype(float).values
        current_price = float(close_prices[-1])
        ema_period = self.params.get("ema_period", 200)
        ema_periods = self.params.get("ema_periods", [9, 21, 50, 200])
        emas = {period: float(self.calculate_ema(close_prices, period).iloc[-1]) for period in ema_periods}
        ema = float(emas.get(ema_period, self.calculate_ema(close_prices, ema_period).iloc[-1]))
        rsi = float(self.calculate_rsi(close_prices).iloc[-1])
        atr = self.calculate_atr(df, self.params.get("atr_period", 14))
        pullback_tolerance = max(atr * 0.5, current_price * 0.001)
        bull_regime = self.params.get("market_regime", {}).get("name") == "2026_structural_bull"

        result = {
            "pattern": "EMA_RSI",
            "confidence": 0.0,
            "bias": "NEUTRAL",
            "entry": current_price,
            "levels": {"ema": ema, "rsi": rsi, **{f"ema{period}": value for period, value in emas.items()}},
            "reasoning": "EMA/RSI has no clean pullback signal",
        }

        if current_price > ema:
            if rsi <= self.params.get("rsi_buy_threshold", 40):
                result.update(
                    {
                        "confidence": 0.78 if bull_regime else 0.74,
                        "bias": "BUY",
                        "entry": max(ema, current_price - pullback_tolerance),
                        "reasoning": f"Structural bull pullback: price above EMA {ema_period} and RSI {rsi:.2f}",
                    }
                )
            elif rsi <= self.params.get("rsi_buy_threshold", 40) + 6:
                result.update(
                    {
                        "confidence": 0.56,
                        "bias": "BUY",
                        "entry": max(ema, current_price - pullback_tolerance),
                        "reasoning": f"Bullish trend; RSI {rsi:.2f} is approaching buy pullback zone",
                    }
                )
        elif current_price < ema:
            if rsi >= max(self.params.get("rsi_sell_threshold", 60), 70 if bull_regime else 60):
                result.update(
                    {
                        "confidence": 0.58 if bull_regime else 0.74,
                        "bias": "SELL",
                        "entry": min(ema, current_price + pullback_tolerance),
                        "reasoning": f"Countertrend warning: price below EMA {ema_period} and RSI {rsi:.2f} is extended",
                    }
                )
            elif rsi >= self.params.get("rsi_sell_threshold", 60) - 6:
                result.update(
                    {
                        "confidence": 0.56,
                        "bias": "SELL",
                        "entry": min(ema, current_price + pullback_tolerance),
                        "reasoning": f"Bearish trend; RSI {rsi:.2f} is approaching sell pullback zone",
                    }
                )

        return result

    def _apply_context_adjustments(self, combined, current_price, atr, role, timeframe_name, indicator_result):
        confidence = float(combined["confidence"])
        direction = combined["direction"]
        session_context = self._session_context(role)
        regime = self.params.get("market_regime", {})
        context_notes = [session_context["reason"]]

        if direction in ("BUY", "SELL"):
            confidence += session_context["confidence_adjustment"]
            ema200 = indicator_result.get("levels", {}).get("ema200", current_price)
            bull_regime = regime.get("name") == "2026_structural_bull"
            if bull_regime and direction == "BUY" and current_price >= ema200:
                confidence += float(regime.get("bull_bias_boost", 0.05))
                context_notes.append("2026 structural bull regime supports buy-the-dip logic")
            elif bull_regime and direction == "SELL" and current_price >= ema200:
                confidence -= float(regime.get("counter_trend_sell_penalty", 0.04))
                context_notes.append("Sell is counter to structural bull regime while above EMA200")

            high_atr_threshold = float(regime.get("high_atr_daily_threshold", 40))
            if atr >= high_atr_threshold and role in ("scalp", "entry"):
                confidence -= 0.03
                context_notes.append("ATR is elevated; lower timeframe entries need extra room")

        combined["confidence"] = self._clip_confidence(confidence)
        combined["context_summary"] = f"{session_context['name']} | " + " | ".join(context_notes)
        return combined

    def _combine_techniques(self, current_price, atr, technique_results, role):
        scores = {"BUY": 0.0, "SELL": 0.0}
        total_signal_weight = 0.0
        entry_candidates = {"BUY": [], "SELL": []}
        active_reasons = []
        summary_parts = []

        for name, result in technique_results.items():
            bias = result.get("bias", "NEUTRAL")
            confidence = float(result.get("confidence", 0.0) or 0.0)
            if confidence <= 0:
                continue

            summary_parts.append(f"{name}:{bias} {confidence:.2f}")
            if bias not in ("BUY", "SELL"):
                continue

            weight = self._technique_weight(name, role)
            score = confidence * weight
            scores[bias] += score
            total_signal_weight += score
            active_reasons.append(f"{name} {bias} ({confidence:.2f}) - {result.get('reasoning', '')}")

            entry = result.get("entry")
            if entry is not None and np.isfinite(float(entry)):
                entry_candidates[bias].append((float(entry), score))

        if scores["BUY"] == 0 and scores["SELL"] == 0:
            return {
                "direction": "WAIT",
                "confidence": 0.45,
                "best_entry": current_price,
                "reasoning": "No technique has a strong directional edge",
                "technique_summary": "No active technique",
            }

        direction = "BUY" if scores["BUY"] >= scores["SELL"] else "SELL"
        opposite = "SELL" if direction == "BUY" else "BUY"
        dominant = scores[direction]
        opposing = scores[opposite]
        alignment = dominant / max(dominant + opposing, 0.0001)
        strength = min(1.0, dominant / max(total_signal_weight, 1.0))
        conflict_penalty = min(0.2, opposing / max(dominant + opposing, 0.0001) * 0.25)
        confidence = self._clip_confidence(0.45 + alignment * 0.35 + strength * 0.18 - conflict_penalty)

        if entry_candidates[direction]:
            weighted_sum = sum(price * weight for price, weight in entry_candidates[direction])
            weight_sum = sum(weight for _, weight in entry_candidates[direction])
            best_entry = weighted_sum / weight_sum
        else:
            best_entry = current_price

        return {
            "direction": direction,
            "confidence": confidence,
            "best_entry": float(best_entry),
            "reasoning": " | ".join(active_reasons) if active_reasons else "Directional score formed from weak confirmations",
            "technique_summary": "; ".join(summary_parts) if summary_parts else "No active technique",
            "direction_scores": scores,
        }

    def _hold_recommendation(self, timeframe_name, role, direction, confidence, atr, current_price, best_entry, style):
        distance_pct = abs(current_price - best_entry) / max(current_price, 1) * 100
        if style == "swing" or role == "trend" or timeframe_name in ("H4", "D1") or confidence >= 0.86:
            return f"Long hold bias ({timeframe_name}): structural/trend context is strong; trail after 1R and reassess on H1/H4 closes."
        if style == "scalp" or role == "entry" or timeframe_name in ("M1", "M5", "M15", "M30"):
            if distance_pct <= 0.08:
                return f"Short hold/scalp ({timeframe_name}): entry is close; target quick liquidity/5-15 dollar movement and exit if momentum fades."
            return f"Wait-for-entry ({timeframe_name}): price is {distance_pct:.2f}% away from the ideal zone."
        if atr / max(current_price, 1) * 100 > 0.35:
            return f"Medium hold ({timeframe_name}): volatility is high; reduce hold time or wait for cleaner retest."
        return f"Medium hold ({timeframe_name}): signal timeframe is balanced; reassess every 1 minute."

    def _risk_plan(self, style, direction, best_entry, sl, tp, atr):
        risk_cfg = self.params.get("risk", {})
        risk_pct = min(float(risk_cfg.get("risk_per_trade_pct", 1.0)), float(risk_cfg.get("max_risk_per_trade_pct", 2.0)))
        stop_distance = abs(best_entry - sl) if sl is not None else 0.0
        target_distance = abs(tp - best_entry) if tp is not None else 0.0
        rr = target_distance / stop_distance if stop_distance else 0.0
        size_factor = 1.0
        if atr >= float(risk_cfg.get("reduce_lot_when_atr_above", 40)):
            size_factor = float(risk_cfg.get("lot_reduction_factor", 0.5))
        return {
            "style": style,
            "risk_pct": risk_pct,
            "stop_distance": stop_distance,
            "target_distance": target_distance,
            "rr": rr,
            "size_factor": size_factor,
            "text": (
                f"{style.upper()} risk: hard SL {stop_distance:.2f}, target {target_distance:.2f}, "
                f"R:R {rr:.2f}, risk {risk_pct:.1f}%"
                + (f", reduce size to {size_factor:.2f}x due to high ATR" if size_factor < 1 else "")
            ),
        }

    def calculate_macd(self, prices):
        params = self.params.get("macd_params", [12, 26, 9])
        fast = pd.Series(prices).ewm(span=params[0], adjust=False).mean()
        slow = pd.Series(prices).ewm(span=params[1], adjust=False).mean()
        macd = fast - slow
        signal = macd.ewm(span=params[2], adjust=False).mean()
        hist = macd - signal
        return macd.iloc[-1], signal.iloc[-1], hist.iloc[-1]

    def _fibonacci_result(self, current_price):
        fib_cfg = self.params.get("fib_levels", {})
        low = fib_cfg.get("anchor_low", 4402)
        high = fib_cfg.get("anchor_high", 5598)
        diff = high - low
        levels = {
            "23.6%": high - 0.236 * diff,
            "38.2%": high - 0.382 * diff,
            "50.0%": high - 0.5 * diff,
            "61.8%": high - 0.618 * diff,
            "78.6%": high - 0.786 * diff
        }
        targets = fib_cfg.get("targets", {})
        
        # Check proximity to key strategic levels from the PDF
        nearest_level = min(targets.items(), key=lambda x: abs(current_price - x[1]))
        tolerance = current_price * 0.0015
        
        bias = "NEUTRAL"
        confidence = 0.0
        if abs(current_price - targets.get("primary_support", 5141)) <= tolerance:
            bias, confidence = "BUY", 0.68
        elif abs(current_price - targets.get("psych_zone", 5000)) <= tolerance:
            bias, confidence = "BUY", 0.65
        elif abs(current_price - targets.get("key_support_s1", 4645)) <= tolerance:
            bias, confidence = "BUY", 0.72
        elif abs(current_price - targets.get("breakout_trigger", 4760)) <= tolerance:
            bias, confidence = "BUY" if current_price > targets["breakout_trigger"] else "SELL", 0.62

        return {
            "pattern": "Fibonacci",
            "confidence": confidence,
            "bias": bias,
            "entry": targets.get(nearest_level[0]),
            "levels": {**levels, **targets},
            "reasoning": f"Price near strategic Fibonacci level: {nearest_level[0]} ({nearest_level[1]:.2f})" if confidence > 0 else "No strategic Fib level nearby"
        }

    def analyze(self, df, timeframe_name=None, role="signal"):
        timeframe = timeframe_name or DEFAULT_TIMEFRAME_NAME
        style = self._strategy_style(timeframe, role)
        close_prices = df["close"].astype(float).values
        current_price = float(close_prices[-1])
        atr = self.calculate_atr(df, self.params.get("atr_period", 14))
        point_val = float(self.params.get("point_value", 0.01))
        sl_points = float(self.params.get("stop_loss_points", 500))
        tp_points = float(self.params.get("take_profit_points", 1000))
        risk_reward_ratio = float(self.params.get("risk_reward_ratio", 1.8))
        risk_cfg = self.params.get("risk", {})

        pattern_result = self.chart_patterns.analyze(df)
        technique_results = {
            "EMA_RSI": self._ema_rsi_result(df),
            "Fibonacci": self._fibonacci_result(current_price)
        }
        indicator_result = self._institutional_indicator_result(df)
        
        # Momentum check with MACD
        macd, macd_sig, macd_hist = self.calculate_macd(close_prices)
        momentum_confirm = (macd_hist > 0 and macd > macd_sig) # Bullish momentum
        
        technique_results["InstitutionalIndicators"] = indicator_result
        technique_results.update(pattern_result["details"])

        combined = self._combine_techniques(current_price, atr, technique_results, role)
        
        # Boost confidence if MACD confirms the direction
        if combined["direction"] == "BUY" and momentum_confirm:
            combined["confidence"] = self._clip_confidence(combined["confidence"] + 0.05)
            combined["reasoning"] += " | MACD confirms bullish momentum"
        elif combined["direction"] == "SELL" and not momentum_confirm:
            combined["confidence"] = self._clip_confidence(combined["confidence"] + 0.05)
            combined["reasoning"] += " | MACD confirms bearish momentum"

        combined = self._apply_context_adjustments(combined, current_price, atr, role, timeframe, indicator_result)
        direction = combined["direction"]
        confidence = combined["confidence"]
        best_entry = float(combined["best_entry"])

        if direction == "WAIT":
            signal = "WAIT"
            sl, tp = None, None
        else:
            signal = direction if confidence >= self.params.get("confidence_threshold", 0.75) else f"PREDICT_{direction}"
            fixed_sl_distance = sl_points * point_val
            fixed_tp_distance = tp_points * point_val
            stop_multiplier = float(risk_cfg.get(f"atr_stop_multiplier_{style}", risk_cfg.get("atr_stop_multiplier_day", 1.35)))
            target_multiplier = float(
                risk_cfg.get(f"atr_take_profit_multiplier_{style}", risk_cfg.get("atr_take_profit_multiplier_day", 1.8))
            )
            atr_sl_distance = atr * stop_multiplier if atr > 0 else fixed_sl_distance
            sl_distance = max(fixed_sl_distance, atr_sl_distance)
            if style == "scalp":
                scalp_targets = self.params.get("scalp_target_points", [500, 1500])
                min_scalp_target = min(scalp_targets) * point_val
                max_scalp_target = max(scalp_targets) * point_val
                tp_distance = max(min_scalp_target, min(max_scalp_target, max(atr * target_multiplier, sl_distance * 1.1)))
            else:
                tp_distance = max(fixed_tp_distance, atr * target_multiplier if atr > 0 else 0, sl_distance * risk_reward_ratio)
            if direction == "BUY":
                sl = best_entry - sl_distance
                tp = best_entry + tp_distance
            else:
                sl = best_entry + sl_distance
                tp = best_entry - tp_distance

        zone_width = max(atr * 0.25 if atr > 0 else point_val * 50, point_val * 50)
        entry_zone = (best_entry - zone_width, best_entry + zone_width)
        hold_recommendation = self._hold_recommendation(timeframe, role, direction, confidence, atr, current_price, best_entry, style)
        risk_plan = self._risk_plan(style, direction, best_entry, sl, tp, atr)

        return {
            "signal": signal,
            "direction": direction,
            "reasoning": combined["reasoning"],
            "entry": best_entry,
            "best_entry": best_entry,
            "current_price": current_price,
            "entry_zone": entry_zone,
            "sl": sl,
            "tp": tp,
            "technique": "HybridStrategy+SMC+OB+FVG+BOS+TrendLine+SR+PricePattern+VWAP",
            "timeframe": timeframe,
            "timeframe_role": role,
            "strategy_style": style,
            "confidence": confidence,
            "hold_recommendation": hold_recommendation,
            "risk_plan": risk_plan,
            "context_summary": combined.get("context_summary", ""),
            "atr": atr,
            "technique_details": technique_results,
            "technique_summary": combined["technique_summary"] + " | " + combined.get("context_summary", ""),
            "direction_scores": combined.get("direction_scores", {"BUY": 0.0, "SELL": 0.0}),
        }


class SMCStrategy(BaseStrategy):
    """Compatibility wrapper for older imports."""

    def analyze(self, df, timeframe_name=None, role="entry"):
        recognizer = ChartPatternRecognizer()
        result = recognizer.detect_smc(df)
        price = float(df["close"].iloc[-1])
        direction = result["bias"] if result["bias"] in ("BUY", "SELL") else "WAIT"
        return {
            "signal": direction,
            "reasoning": result["reasoning"],
            "entry": result["entry"] or price,
            "sl": None,
            "tp": None,
            "technique": "SMC",
            "timeframe": timeframe_name or DEFAULT_TIMEFRAME_NAME,
            "confidence": result["confidence"],
            "hold_recommendation": "Short hold; SMC needs retest confirmation",
        }
