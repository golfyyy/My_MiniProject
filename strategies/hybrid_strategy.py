import pandas as pd
import numpy as np
from datetime import datetime, timezone
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple, Set
from .chart_patterns import ChartPatternRecognizer

DEFAULT_TIMEFRAME_NAME: str = "H1"


class BaseStrategy(ABC):
    """คลาสพื้นฐานสำหรับทุกกลยุทธ์การเทรด"""

    def __init__(self, params: Dict[str, Any]) -> None:
        self.params: Dict[str, Any] = params

    @abstractmethod
    def analyze(self, df: pd.DataFrame, timeframe_name: Optional[str] = None, role: str = "signal") -> Dict[str, Any]:
        """Return a normalized analysis result."""
        pass


class HybridStrategy(BaseStrategy):
    """EMA/RSI + SMC + Trend Line + Support/Resistance + Price Pattern ensemble."""

    def __init__(self, params: Dict[str, Any]) -> None:
        super().__init__(params)
        self.chart_patterns: ChartPatternRecognizer = ChartPatternRecognizer(params.get("atr_period", 14))
        self.technique_weights: Dict[str, float] = {}

        # --- Parameters & Constants Configuration ---
        self.role_boosts: Dict[str, Dict[str, float]] = params.get("role_boosts", {
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
        })

        # Tolerance multipliers
        self.pullback_atr_multiplier: float = float(params.get("pullback_atr_multiplier", 0.5))
        self.pullback_pct_multiplier: float = float(params.get("pullback_pct_multiplier", 0.001))

        # Institutional Indicator Confidence Configuration
        self.inst_bull_base_confidence: float = float(params.get("inst_bull_base_confidence", 0.58))
        self.inst_bear_base_confidence: float = float(params.get("inst_bear_base_confidence", 0.56))
        self.inst_volume_spike_boost: float = float(params.get("inst_volume_spike_boost", 0.08))
        self.inst_volatility_expanding_boost: float = float(params.get("inst_volatility_expanding_boost", 0.05))
        self.inst_bear_volatility_boost: float = float(params.get("inst_bear_volatility_boost", 0.04))
        self.bollinger_volatility_threshold: float = float(params.get("bollinger_volatility_threshold", 0.008))

        # EMA/RSI Confidence Configuration
        self.ema_rsi_bull_regime_confidence: float = float(params.get("ema_rsi_bull_regime_confidence", 0.78))
        self.ema_rsi_base_bull_confidence: float = float(params.get("ema_rsi_base_bull_confidence", 0.74))
        self.ema_rsi_approaching_bull_confidence: float = float(params.get("ema_rsi_approaching_bull_confidence", 0.56))
        self.ema_rsi_bear_regime_confidence: float = float(params.get("ema_rsi_bear_regime_confidence", 0.58))
        self.ema_rsi_base_bear_confidence: float = float(params.get("ema_rsi_base_bear_confidence", 0.74))
        self.ema_rsi_approaching_bear_confidence: float = float(params.get("ema_rsi_approaching_bear_confidence", 0.56))

        # Combine parameters
        self.comb_base_confidence: float = float(params.get("comb_base_confidence", 0.45))
        self.comb_alignment_weight: float = float(params.get("comb_alignment_weight", 0.35))
        self.comb_strength_weight: float = float(params.get("comb_strength_weight", 0.18))
        self.comb_conflict_max_penalty: float = float(params.get("comb_conflict_max_penalty", 0.2))
        self.comb_conflict_ratio_multiplier: float = float(params.get("comb_conflict_ratio_multiplier", 0.25))

        # MACD Confirmation boost
        self.macd_confirm_boost: float = float(params.get("macd_confirm_boost", 0.05))

        # Fibonacci strategic confidences
        self.fib_primary_support_confidence: float = float(params.get("fib_primary_support_confidence", 0.68))
        self.fib_psych_zone_confidence: float = float(params.get("fib_psych_zone_confidence", 0.65))
        self.fib_key_support_confidence: float = float(params.get("fib_key_support_confidence", 0.72))
        self.fib_breakout_confidence: float = float(params.get("fib_breakout_confidence", 0.62))
        self.fib_proximity_tolerance_pct: float = float(params.get("fib_proximity_tolerance_pct", 0.0015))

        # Hold Recommendation parameters
        self.hold_scalp_proximity_pct: float = float(params.get("hold_scalp_proximity_pct", 0.08))
        self.hold_atr_volatility_pct: float = float(params.get("hold_atr_volatility_pct", 0.35))

        # Entry Zone configuration
        self.entry_zone_atr_multiplier: float = float(params.get("entry_zone_atr_multiplier", 0.25))
        self.entry_zone_min_points: float = float(params.get("entry_zone_min_points", 50))

    def set_technique_weights(self, technique_weights: Dict[str, float]) -> None:
        self.technique_weights = technique_weights or {}

    @staticmethod
    def _clip_confidence(value: float) -> float:
        return float(max(0.0, min(0.95, value)))

    def _technique_weight(self, technique_name: str, role: str) -> float:
        base = float(self.technique_weights.get(technique_name, 1.0))
        return base * self.role_boosts.get(role, self.role_boosts["signal"]).get(technique_name, 1.0)

    def calculate_rsi(self, prices: np.ndarray, period: int = 14) -> pd.Series:
        deltas = pd.Series(prices).diff()
        gain = (deltas.where(deltas > 0, 0)).rolling(window=period).mean()
        loss = (-deltas.where(deltas < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    def calculate_ema(self, prices: np.ndarray, period: int) -> pd.Series:
        return pd.Series(prices).ewm(span=period, adjust=False).mean()

    def calculate_bollinger(self, prices: np.ndarray, period: int = 20, std_multiplier: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        series = pd.Series(prices)
        mid = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = mid + std * std_multiplier
        lower = mid - std * std_multiplier
        return mid, upper, lower

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        if len(df) < period + 2:
            return 0.0
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)
        prev_close = close.shift(1)
        tr = np.maximum(high - low, np.maximum((high - prev_close).abs(), (low - prev_close).abs()))
        atr = tr.rolling(window=period).mean().iloc[-1]
        return float(atr) if np.isfinite(atr) else 0.0

    def calculate_vwap(self, df: pd.DataFrame) -> float:
        volume_col = "tick_volume" if "tick_volume" in df.columns else "volume"
        if volume_col not in df.columns:
            return float(df["close"].astype(float).iloc[-1])
        typical_price = (df["high"].astype(float) + df["low"].astype(float) + df["close"].astype(float)) / 3
        volume = df[volume_col].astype(float).replace(0, np.nan).fillna(1)
        vwap = (typical_price * volume).cumsum() / volume.cumsum()
        value = vwap.iloc[-1]
        return float(value) if np.isfinite(value) else float(df["close"].astype(float).iloc[-1])

    def _strategy_style(self, timeframe_name: str, role: str) -> str:
        if role == "scalp" or timeframe_name in ("M1", "M5", "M15"):
            return "scalp"
        if role == "trend" or timeframe_name in ("H4", "D1", "W1"):
            return "swing"
        return "day"

    def _session_context(self, role: str) -> Dict[str, Any]:
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

    def _volume_spike(self, df: pd.DataFrame) -> Tuple[bool, float]:
        volume_col = "tick_volume" if "tick_volume" in df.columns else "volume"
        if volume_col not in df.columns or len(df) < 5:
            return False, 1.0
        volume = df[volume_col].astype(float)
        recent_avg = float(volume.iloc[-4:-1].mean())
        current = float(volume.iloc[-1])
        ratio = current / max(recent_avg, 1.0)
        return ratio >= float(self.params.get("volume_spike_multiplier", 1.5)), ratio

    def _institutional_indicator_result(self, df: pd.DataFrame) -> Dict[str, Any]:
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
        volatility_expanding = band_width > self.bollinger_volatility_threshold

        if bullish_stack:
            confidence = self.inst_bull_base_confidence + (self.inst_volume_spike_boost if volume_spike else 0.0) + (self.inst_volatility_expanding_boost if volatility_expanding else 0.0)
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
            confidence = self.inst_bear_base_confidence + (self.inst_volume_spike_boost if volume_spike else 0.0) + (self.inst_bear_volatility_boost if volatility_expanding else 0.0)
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

    def _ema_rsi_result(self, df: pd.DataFrame) -> Dict[str, Any]:
        close_prices = df["close"].astype(float).values
        current_price = float(close_prices[-1])
        ema_period = self.params.get("ema_period", 200)
        ema_periods = self.params.get("ema_periods", [9, 21, 50, 200])
        emas = {period: float(self.calculate_ema(close_prices, period).iloc[-1]) for period in ema_periods}
        ema = float(emas.get(ema_period, self.calculate_ema(close_prices, ema_period).iloc[-1]))
        rsi = float(self.calculate_rsi(close_prices).iloc[-1])
        atr = self.calculate_atr(df, self.params.get("atr_period", 14))
        pullback_tolerance = max(atr * self.pullback_atr_multiplier, current_price * self.pullback_pct_multiplier)
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
                        "confidence": self.ema_rsi_bull_regime_confidence if bull_regime else self.ema_rsi_base_bull_confidence,
                        "bias": "BUY",
                        "entry": max(ema, current_price - pullback_tolerance),
                        "reasoning": f"Structural bull pullback: price above EMA {ema_period} and RSI {rsi:.2f}",
                    }
                )
            elif rsi <= self.params.get("rsi_buy_threshold", 40) + 6:
                result.update(
                    {
                        "confidence": self.ema_rsi_approaching_bull_confidence,
                        "bias": "BUY",
                        "entry": max(ema, current_price - pullback_tolerance),
                        "reasoning": f"Bullish trend; RSI {rsi:.2f} is approaching buy pullback zone",
                    }
                )
        elif current_price < ema:
            if rsi >= max(self.params.get("rsi_sell_threshold", 60), 70 if bull_regime else 60):
                result.update(
                    {
                        "confidence": self.ema_rsi_bear_regime_confidence if bull_regime else self.ema_rsi_base_bear_confidence,
                        "bias": "SELL",
                        "entry": min(ema, current_price + pullback_tolerance),
                        "reasoning": f"Countertrend warning: price below EMA {ema_period} and RSI {rsi:.2f} is extended",
                    }
                )
            elif rsi >= self.params.get("rsi_sell_threshold", 60) - 6:
                result.update(
                    {
                        "confidence": self.ema_rsi_approaching_bear_confidence,
                        "bias": "SELL",
                        "entry": min(ema, current_price + pullback_tolerance),
                        "reasoning": f"Bearish trend; RSI {rsi:.2f} is approaching sell pullback zone",
                    }
                )

        return result

    def _apply_context_adjustments(
        self,
        combined: Dict[str, Any],
        current_price: float,
        atr: float,
        role: str,
        timeframe_name: str,
        indicator_result: Dict[str, Any]
    ) -> Dict[str, Any]:
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

    def _combine_techniques(self, current_price: float, atr: float, technique_results: Dict[str, Dict[str, Any]], role: str) -> Dict[str, Any]:
        scores = {"BUY": 0.0, "SELL": 0.0}
        total_signal_weight = 0.0
        entry_candidates: Dict[str, List[Tuple[float, float]]] = {"BUY": [], "SELL": []}
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
        conflict_penalty = min(self.comb_conflict_max_penalty, opposing / max(dominant + opposing, 0.0001) * self.comb_conflict_ratio_multiplier)
        confidence = self._clip_confidence(self.comb_base_confidence + alignment * self.comb_alignment_weight + strength * self.comb_strength_weight - conflict_penalty)

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

    def _hold_recommendation(
        self,
        timeframe_name: str,
        role: str,
        direction: str,
        confidence: float,
        atr: float,
        current_price: float,
        best_entry: float,
        style: str
    ) -> str:
        distance_pct = abs(current_price - best_entry) / max(current_price, 1) * 100
        if style == "swing" or role == "trend" or timeframe_name in ("H4", "D1") or confidence >= 0.86:
            return f"Long hold bias ({timeframe_name}): structural/trend context is strong; trail after 1R and reassess on H1/H4 closes."
        if style == "scalp" or role == "entry" or timeframe_name in ("M1", "M5", "M15", "M30"):
            if distance_pct <= self.hold_scalp_proximity_pct:
                return f"Short hold/scalp ({timeframe_name}): entry is close; target quick liquidity/5-15 dollar movement and exit if momentum fades."
            return f"Wait-for-entry ({timeframe_name}): price is {distance_pct:.2f}% away from the ideal zone."
        if atr / max(current_price, 1) * 100 > self.hold_atr_volatility_pct:
            return f"Medium hold ({timeframe_name}): volatility is high; reduce hold time or wait for cleaner retest."
        return f"Medium hold ({timeframe_name}): signal timeframe is balanced; reassess every 1 minute."

    def _risk_plan(self, style: str, direction: str, best_entry: float, sl: Optional[float], tp: Optional[float], atr: float) -> Dict[str, Any]:
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

    def calculate_macd(self, prices: np.ndarray) -> Tuple[float, float, float]:
        params = self.params.get("macd_params", [12, 26, 9])
        fast = pd.Series(prices).ewm(span=params[0], adjust=False).mean()
        slow = pd.Series(prices).ewm(span=params[1], adjust=False).mean()
        macd = fast - slow
        signal = macd.ewm(span=params[2], adjust=False).mean()
        hist = macd - signal
        return float(macd.iloc[-1]), float(signal.iloc[-1]), float(hist.iloc[-1])

    def _fibonacci_result(self, current_price: float) -> Dict[str, Any]:
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

        nearest_level = min(targets.items(), key=lambda x: abs(current_price - x[1]))
        tolerance = current_price * self.fib_proximity_tolerance_pct

        bias = "NEUTRAL"
        confidence = 0.0
        if abs(current_price - targets.get("primary_support", 5141)) <= tolerance:
            bias, confidence = "BUY", self.fib_primary_support_confidence
        elif abs(current_price - targets.get("psych_zone", 5000)) <= tolerance:
            bias, confidence = "BUY", self.fib_psych_zone_confidence
        elif abs(current_price - targets.get("key_support_s1", 4645)) <= tolerance:
            bias, confidence = "BUY", self.fib_key_support_confidence
        elif abs(current_price - targets.get("breakout_trigger", 4760)) <= tolerance:
            bias, confidence = "BUY" if current_price > targets["breakout_trigger"] else "SELL", self.fib_breakout_confidence

        return {
            "pattern": "Fibonacci",
            "confidence": confidence,
            "bias": bias,
            "entry": targets.get(nearest_level[0]),
            "levels": {**levels, **targets},
            "reasoning": f"Price near strategic Fibonacci level: {nearest_level[0]} ({nearest_level[1]:.2f})" if confidence > 0 else "No strategic Fib level nearby"
        }

    def analyze(self, df: pd.DataFrame, timeframe_name: Optional[str] = None, role: str = "signal") -> Dict[str, Any]:
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

        macd, macd_sig, macd_hist = self.calculate_macd(close_prices)
        momentum_confirm = (macd_hist > 0 and macd > macd_sig)

        technique_results["InstitutionalIndicators"] = indicator_result
        technique_results.update(pattern_result["details"])

        combined = self._combine_techniques(current_price, atr, technique_results, role)

        if combined["direction"] == "BUY" and momentum_confirm:
            combined["confidence"] = self._clip_confidence(combined["confidence"] + self.macd_confirm_boost)
            combined["reasoning"] += " | MACD confirms bullish momentum"
        elif combined["direction"] == "SELL" and not momentum_confirm:
            combined["confidence"] = self._clip_confidence(combined["confidence"] + self.macd_confirm_boost)
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

        zone_width = max(atr * self.entry_zone_atr_multiplier if atr > 0 else point_val * self.entry_zone_min_points, point_val * self.entry_zone_min_points)
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

    def analyze(self, df: pd.DataFrame, timeframe_name: Optional[str] = None, role: str = "entry") -> Dict[str, Any]:
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
