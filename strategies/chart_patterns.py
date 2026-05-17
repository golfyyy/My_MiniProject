import numpy as np


class ChartPatternRecognizer:
    """Recognizes SMC, trend line, support/resistance, and price-action patterns."""

    def __init__(self, atr_period=14):
        self.atr_period = atr_period

    @staticmethod
    def _neutral(pattern, reason="No clear edge"):
        return {
            "pattern": pattern,
            "confidence": 0.0,
            "bias": "NEUTRAL",
            "entry": None,
            "levels": {},
            "reasoning": reason,
        }

    @staticmethod
    def _clip_confidence(value):
        return float(max(0.0, min(0.95, value)))

    @staticmethod
    def _atr(df, period=14):
        if len(df) < period + 2:
            return 0.0
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)
        prev_close = close.shift(1)
        tr = np.maximum(high - low, np.maximum((high - prev_close).abs(), (low - prev_close).abs()))
        atr = tr.rolling(window=period).mean().iloc[-1]
        return float(atr) if np.isfinite(atr) else 0.0

    def _get_fractals(self, df, window=2):
        """
        Detects swing points using fractal logic.
        A swing high is a high that is higher than 'window' candles to its left and right.
        """
        highs = df["high"].astype(float).values
        lows = df["low"].astype(float).values
        swing_highs = []
        swing_lows = []

        for i in range(window, len(df) - window):
            # Swing High: Higher than neighbors
            is_high = True
            for j in range(i - window, i + window + 1):
                if j != i and highs[j] > highs[i]:
                    is_high = False
                    break
            if is_high:
                swing_highs.append((i, highs[i]))

            # Swing Low: Lower than neighbors
            is_low = True
            for j in range(i - window, i + window + 1):
                if j != i and lows[j] < lows[i]:
                    is_low = False
                    break
            if is_low:
                swing_lows.append((i, lows[i]))
        
        return swing_highs, swing_lows

    def detect_smc(self, df):
        """
        Professional SMC detection:
        - Uses fractal-based swing points instead of range max/min.
        - Confirms BOS/ChoCH using candle Close.
        - Validates liquidity sweeps with reclamation.
        """
        if len(df) < 50:
            return self._neutral("SMC", "Not enough candles for Professional SMC")

        high = df["high"].astype(float).values
        low = df["low"].astype(float).values
        close = df["close"].astype(float).values
        open_ = df["open"].astype(float).values
        atr = self._atr(df, self.atr_period)
        price = close[-1]

        s_highs, s_lows = self._get_fractals(df)
        if not s_highs or not s_lows:
            return self._neutral("SMC", "No clear fractal swings detected")

        # Get the most recent confirmed swing points
        last_swing_high = s_highs[-1][1]
        prev_swing_high = s_highs[-2][1] if len(s_highs) > 1 else last_swing_high
        last_swing_low = s_lows[-1][1]
        prev_swing_low = s_lows[-2][1] if len(s_lows) > 1 else last_swing_low

        # 1. Bullish Liquidity Sweep + Reclamation
        # Price dipped below last swing low and closed back above it
        bull_sweep = low[-1] < last_swing_low and close[-1] > last_swing_low
        
        # 2. Bullish ChoCH (Change of Character)
        # Price closed above the most recent swing high after a low was formed
        bull_choch = close[-1] > last_swing_high and low[-2] <= last_swing_low + max(atr * 0.2, price * 0.001)

        if bull_sweep or bull_choch:
            entry = max(last_swing_low, min(price, (low[-1] + close[-1]) / 2))
            confidence = 0.72 + (0.1 if bull_choch else 0.0) + (0.05 if close[-1] > open_[-1] else 0.0)
            return {
                "pattern": "SMC",
                "confidence": self._clip_confidence(confidence),
                "bias": "BUY",
                "entry": float(entry),
                "levels": {
                    "liquidity_low": last_swing_low,
                    "structure_high": last_swing_high,
                    "invalid_below": float(min(low[-1], last_swing_low) - atr * 0.3),
                },
                "reasoning": "Professional SMC: Bullish liquidity sweep or ChoCH confirmed by candle close",
            }

        # 3. Bearish Liquidity Sweep + Reclamation
        bear_sweep = high[-1] > last_swing_high and close[-1] < last_swing_high
        
        # 4. Bearish ChoCH
        bear_choch = close[-1] < last_swing_low and high[-2] >= last_swing_high - max(atr * 0.2, price * 0.001)

        if bear_sweep or bear_choch:
            entry = min(last_swing_high, max(price, (high[-1] + close[-1]) / 2))
            confidence = 0.72 + (0.1 if bear_choch else 0.0) + (0.05 if close[-1] < open_[-1] else 0.0)
            return {
                "pattern": "SMC",
                "confidence": self._clip_confidence(confidence),
                "bias": "SELL",
                "entry": float(entry),
                "levels": {
                    "liquidity_high": last_swing_high,
                    "structure_low": last_swing_low,
                    "invalid_above": float(max(high[-1], last_swing_high) + atr * 0.3),
                },
                "reasoning": "Professional SMC: Bearish liquidity sweep or ChoCH confirmed by candle close",
            }

        return self._neutral("SMC")

    def detect_order_blocks(self, df, lookback=40):
        """
        Detect a simple institutional order block:
        - bullish OB: last bearish candle before bullish displacement
        - bearish OB: last bullish candle before bearish displacement
        """
        if len(df) < lookback:
            return self._neutral("OrderBlock", "Not enough candles for order block")

        recent = df.tail(lookback)
        open_ = recent["open"].astype(float).values
        high = recent["high"].astype(float).values
        low = recent["low"].astype(float).values
        close = recent["close"].astype(float).values
        bodies = np.abs(close - open_)
        avg_body = max(float(np.mean(bodies[:-1])), 0.0001)
        atr = self._atr(df, self.atr_period)
        price = float(close[-1])
        prior_high = float(np.max(high[-12:-2]))
        prior_low = float(np.min(low[-12:-2]))
        bullish_displacement = close[-1] > prior_high and bodies[-1] > avg_body * 1.25
        bearish_displacement = close[-1] < prior_low and bodies[-1] > avg_body * 1.25

        if bullish_displacement:
            for i in range(len(recent) - 3, max(0, len(recent) - 18), -1):
                if close[i] < open_[i]:
                    entry = float((open_[i] + low[i]) / 2)
                    return {
                        "pattern": "BullishOrderBlock",
                        "confidence": 0.7,
                        "bias": "BUY",
                        "entry": entry,
                        "levels": {
                            "order_block_low": float(low[i]),
                            "order_block_high": float(open_[i]),
                            "invalid_below": float(low[i] - atr * 0.25),
                        },
                        "reasoning": "Bullish displacement after a bearish order block",
                    }

        if bearish_displacement:
            for i in range(len(recent) - 3, max(0, len(recent) - 18), -1):
                if close[i] > open_[i]:
                    entry = float((open_[i] + high[i]) / 2)
                    return {
                        "pattern": "BearishOrderBlock",
                        "confidence": 0.7,
                        "bias": "SELL",
                        "entry": entry,
                        "levels": {
                            "order_block_low": float(open_[i]),
                            "order_block_high": float(high[i]),
                            "invalid_above": float(high[i] + atr * 0.25),
                        },
                        "reasoning": "Bearish displacement after a bullish order block",
                    }

        return self._neutral("OrderBlock")

    def detect_fair_value_gap(self, df, lookback=30):
        """
        Three-candle Fair Value Gap detection.
        Bullish FVG exists when candle n low is above candle n-2 high.
        Bearish FVG exists when candle n high is below candle n-2 low.
        """
        if len(df) < lookback:
            return self._neutral("FVG", "Not enough candles for fair value gap")

        recent = df.tail(lookback)
        high = recent["high"].astype(float).values
        low = recent["low"].astype(float).values
        close = recent["close"].astype(float).values
        atr = self._atr(df, self.atr_period)
        price = float(close[-1])

        best_gap = None
        for i in range(2, len(recent)):
            if low[i] > high[i - 2]:
                gap_low = float(high[i - 2])
                gap_high = float(low[i])
                gap_size = gap_high - gap_low
                distance = abs(price - (gap_low + gap_high) / 2)
                if gap_size >= max(atr * 0.08, price * 0.0003):
                    best_gap = ("BUY", gap_low, gap_high, gap_size, distance)
            elif high[i] < low[i - 2]:
                gap_low = float(high[i])
                gap_high = float(low[i - 2])
                gap_size = gap_high - gap_low
                distance = abs(price - (gap_low + gap_high) / 2)
                if gap_size >= max(atr * 0.08, price * 0.0003):
                    best_gap = ("SELL", gap_low, gap_high, gap_size, distance)

        if not best_gap:
            return self._neutral("FVG")

        bias, gap_low, gap_high, gap_size, distance = best_gap
        entry = float((gap_low + gap_high) / 2)
        near_gap = distance <= max(atr * 0.8, gap_size * 2)
        confidence = 0.58 + (0.1 if near_gap else 0.0) + min(0.08, gap_size / max(atr, 0.0001) * 0.04)
        return {
            "pattern": "FairValueGap",
            "confidence": self._clip_confidence(confidence),
            "bias": bias,
            "entry": entry,
            "levels": {"fvg_low": gap_low, "fvg_high": gap_high, "gap_size": gap_size},
            "reasoning": f"{bias} fair value gap acts as a magnet for retest entry",
        }

    def detect_market_structure(self, df, lookback=50):
        """Detect BOS/ChoCH from recent swing structure with volume confirmation."""
        if len(df) < lookback:
            return self._neutral("MarketStructure", "Not enough candles for market structure")

        recent = df.tail(lookback)
        high = recent["high"].astype(float).values
        low = recent["low"].astype(float).values
        close = recent["close"].astype(float).values
        volume_col = "tick_volume" if "tick_volume" in df.columns else "volume"
        volume = recent[volume_col].astype(float).values if volume_col in df.columns else np.ones(len(recent))
        atr = self._atr(df, self.atr_period)
        price = float(close[-1])

        swing_highs = []
        swing_lows = []
        for i in range(2, len(recent) - 2):
            if high[i] >= np.max(high[i - 2 : i + 3]):
                swing_highs.append((i, high[i]))
            if low[i] <= np.min(low[i - 2 : i + 3]):
                swing_lows.append((i, low[i]))

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return self._neutral("MarketStructure", "No clean swing structure")

        prev_high = float(swing_highs[-1][1])
        prev_low = float(swing_lows[-1][1])
        earlier_high = float(swing_highs[-2][1])
        earlier_low = float(swing_lows[-2][1])
        bullish_context = prev_high > earlier_high and prev_low > earlier_low
        bearish_context = prev_high < earlier_high and prev_low < earlier_low

        # Volume confirmation for breakout
        vol_avg = np.mean(volume[-10:-1]) if len(volume) > 10 else 1.0
        vol_confirm = volume[-1] > vol_avg * 1.2

        if price > prev_high:
            pattern = "BullishBOS" if bullish_context else "BullishChoCH"
            confidence = 0.68 if bullish_context else 0.64
            if vol_confirm: confidence += 0.08
            return {
                "pattern": pattern,
                "confidence": self._clip_confidence(confidence),
                "bias": "BUY",
                "entry": float(prev_high),
                "levels": {"broken_high": prev_high, "structure_low": prev_low, "invalid_below": prev_low - atr * 0.25},
                "reasoning": f"{pattern}: close broke above recent swing high" + (" with volume support" if vol_confirm else ""),
            }

        if price < prev_low:
            pattern = "BearishBOS" if bearish_context else "BearishChoCH"
            confidence = 0.68 if bearish_context else 0.64
            if vol_confirm: confidence += 0.08
            return {
                "pattern": pattern,
                "confidence": self._clip_confidence(confidence),
                "bias": "SELL",
                "entry": float(prev_low),
                "levels": {"broken_low": prev_low, "structure_high": prev_high, "invalid_above": prev_high + atr * 0.25},
                "reasoning": f"{pattern}: close broke below recent swing low" + (" with volume support" if vol_confirm else ""),
            }

        return self._neutral("MarketStructure", "Structure has not broken")

    def detect_trend_lines(self, df, lookback=50):
        """
        Trend line bias from linear regression of recent lows/highs.
        Entry is projected support in an uptrend or projected resistance in a downtrend.
        """
        if len(df) < lookback:
            return self._neutral("TrendLine", "Not enough candles for trend line")

        subset = df.tail(lookback)
        x = np.arange(len(subset))
        lows = subset["low"].astype(float).values
        highs = subset["high"].astype(float).values
        closes = subset["close"].astype(float).values
        price = float(closes[-1])
        atr = self._atr(df, self.atr_period)
        tolerance = max(atr * 0.5, price * 0.001)

        slope_low, intercept_low = np.polyfit(x, lows, 1)
        slope_high, intercept_high = np.polyfit(x, highs, 1)
        projected_support = float(slope_low * (len(subset) - 1) + intercept_low)
        projected_resistance = float(slope_high * (len(subset) - 1) + intercept_high)
        channel_width = max(projected_resistance - projected_support, atr, price * 0.001)
        slope_strength = min(0.25, abs(slope_low + slope_high) / max(price, 1) * 250)

        if slope_low > 0 and slope_high > 0:
            near_support = abs(price - projected_support) <= tolerance * 1.5
            confidence = 0.56 + slope_strength + (0.12 if near_support else 0.0)
            return {
                "pattern": "TrendLine",
                "confidence": self._clip_confidence(confidence),
                "bias": "BUY",
                "entry": projected_support if near_support else max(projected_support, price - channel_width * 0.35),
                "levels": {
                    "trend_support": projected_support,
                    "trend_resistance": projected_resistance,
                    "channel_width": channel_width,
                },
                "reasoning": "Rising trend channel; best buy is near projected support",
            }

        if slope_low < 0 and slope_high < 0:
            near_resistance = abs(price - projected_resistance) <= tolerance * 1.5
            confidence = 0.56 + slope_strength + (0.12 if near_resistance else 0.0)
            return {
                "pattern": "TrendLine",
                "confidence": self._clip_confidence(confidence),
                "bias": "SELL",
                "entry": projected_resistance if near_resistance else min(projected_resistance, price + channel_width * 0.35),
                "levels": {
                    "trend_support": projected_support,
                    "trend_resistance": projected_resistance,
                    "channel_width": channel_width,
                },
                "reasoning": "Falling trend channel; best sell is near projected resistance",
            }

        return self._neutral("TrendLine", "Trend line slopes are mixed")

    def detect_support_resistance(self, df, window=20):
        """
        Identify nearby support/resistance from recent swing extremes.
        Bias is strongest when price is near a level or breaks/retests one.
        """
        if len(df) < window * 2:
            return self._neutral("SupportResistance", "Not enough candles for support/resistance")

        recent = df.tail(window * 3).iloc[:-1]
        highs = recent["high"].astype(float).values
        lows = recent["low"].astype(float).values
        price = float(df["close"].iloc[-1])
        atr = self._atr(df, self.atr_period)
        tolerance = max(atr * 0.6, price * 0.0015)

        swing_lows = []
        swing_highs = []
        for i in range(2, len(lows) - 2):
            if lows[i] <= np.min(lows[i - 2 : i + 3]):
                swing_lows.append(lows[i])
            if highs[i] >= np.max(highs[i - 2 : i + 3]):
                swing_highs.append(highs[i])

        range_low = float(np.percentile(lows, 15))
        range_high = float(np.percentile(highs, 85))
        below_price = np.array([level for level in swing_lows if level <= price])
        above_price = np.array([level for level in swing_highs if level >= price])
        support = float(np.max(below_price)) if len(below_price) else range_low
        resistance = float(np.min(above_price)) if len(above_price) else range_high

        if 0 <= price - support <= tolerance:
            return {
                "pattern": "SupportResistance",
                "confidence": 0.68,
                "bias": "BUY",
                "entry": support,
                "levels": {"support": support, "resistance": resistance, "range_low": range_low, "range_high": range_high},
                "reasoning": "Price is testing nearby support",
            }

        if 0 <= resistance - price <= tolerance:
            return {
                "pattern": "SupportResistance",
                "confidence": 0.68,
                "bias": "SELL",
                "entry": resistance,
                "levels": {"support": support, "resistance": resistance, "range_low": range_low, "range_high": range_high},
                "reasoning": "Price is testing nearby resistance",
            }

        if price > resistance + tolerance:
            return {
                "pattern": "SupportResistance",
                "confidence": 0.58,
                "bias": "BUY",
                "entry": resistance,
                "levels": {"breakout_level": resistance, "support": support},
                "reasoning": "Price broke above resistance; retest is preferred",
            }

        if price < support - tolerance:
            return {
                "pattern": "SupportResistance",
                "confidence": 0.58,
                "bias": "SELL",
                "entry": support,
                "levels": {"breakdown_level": support, "resistance": resistance},
                "reasoning": "Price broke below support; retest is preferred",
            }

        return self._neutral("SupportResistance", "Price is between clean support/resistance zones")

    def detect_price_patterns(self, df):
        """
        Detect compact price-action patterns: engulfing candles, rejection pins,
        double top/bottom, and simple breakouts.
        """
        if len(df) < 12:
            return self._neutral("PricePattern", "Not enough candles for price pattern")

        open_ = df["open"].astype(float).values
        high = df["high"].astype(float).values
        low = df["low"].astype(float).values
        close = df["close"].astype(float).values
        price = float(close[-1])
        atr = self._atr(df, self.atr_period)
        body = abs(close[-1] - open_[-1])
        candle_range = max(high[-1] - low[-1], price * 0.0001)
        upper_wick = high[-1] - max(open_[-1], close[-1])
        lower_wick = min(open_[-1], close[-1]) - low[-1]

        # Strength: Close relative to the candle's range
        close_strength = (close[-1] - low[-1]) / max(candle_range, 0.0001) if close[-1] > open_[-1] else (high[-1] - close[-1]) / max(candle_range, 0.0001)

        bull_engulf = close[-2] < open_[-2] and close[-1] > open_[-1] and close[-1] > open_[-2] and open_[-1] <= close[-2]
        bear_engulf = close[-2] > open_[-2] and close[-1] < open_[-1] and close[-1] < open_[-2] and open_[-1] >= close[-2]
        if bull_engulf:
            confidence = 0.66 + (0.08 if close_strength > 0.8 else 0.0)
            return {
                "pattern": "BullishEngulfing",
                "confidence": self._clip_confidence(confidence),
                "bias": "BUY",
                "entry": float((open_[-1] + close[-1]) / 2),
                "levels": {"pattern_low": float(low[-1]), "invalid_below": float(low[-1] - atr * 0.2)},
                "reasoning": "Bullish engulfing candle confirms buyer reaction" + (" with strong close" if close_strength > 0.8 else ""),
            }

        if bear_engulf:
            confidence = 0.66 + (0.08 if close_strength > 0.8 else 0.0)
            return {
                "pattern": "BearishEngulfing",
                "confidence": self._clip_confidence(confidence),
                "bias": "SELL",
                "entry": float((open_[-1] + close[-1]) / 2),
                "levels": {"pattern_high": float(high[-1]), "invalid_above": float(high[-1] + atr * 0.2)},
                "reasoning": "Bearish engulfing candle confirms seller reaction" + (" with strong close" if close_strength > 0.8 else ""),
            }

        if lower_wick > body * 2 and upper_wick < candle_range * 0.35 and close[-1] > open_[-1]:
            return {
                "pattern": "BullishPinBar",
                "confidence": 0.62,
                "bias": "BUY",
                "entry": float((low[-1] + close[-1]) / 2),
                "levels": {"rejection_low": float(low[-1])},
                "reasoning": "Bullish rejection wick suggests demand",
            }

        if upper_wick > body * 2 and lower_wick < candle_range * 0.35 and close[-1] < open_[-1]:
            return {
                "pattern": "BearishPinBar",
                "confidence": 0.62,
                "bias": "SELL",
                "entry": float((high[-1] + close[-1]) / 2),
                "levels": {"rejection_high": float(high[-1])},
                "reasoning": "Bearish rejection wick suggests supply",
            }

        recent_lows = low[-10:]
        recent_highs = high[-10:]
        low_sorted = np.sort(recent_lows)[:2]
        high_sorted = np.sort(recent_highs)[-2:]
        level_tolerance = max(atr * 0.35, price * 0.001)

        if abs(low_sorted[0] - low_sorted[1]) <= level_tolerance and close[-1] > close[-3]:
            return {
                "pattern": "DoubleBottom",
                "confidence": 0.6,
                "bias": "BUY",
                "entry": float(np.mean(low_sorted)),
                "levels": {"double_bottom": float(np.mean(low_sorted))},
                "reasoning": "Double bottom with buyer follow-through",
            }

        if abs(high_sorted[0] - high_sorted[1]) <= level_tolerance and close[-1] < close[-3]:
            return {
                "pattern": "DoubleTop",
                "confidence": 0.6,
                "bias": "SELL",
                "entry": float(np.mean(high_sorted)),
                "levels": {"double_top": float(np.mean(high_sorted))},
                "reasoning": "Double top with seller follow-through",
            }

        return self._neutral("PricePattern")

    def detect_supply_demand_zones(self, df, lookback=60):
        """
        Detect Institutional Supply and Demand Zones:
        - RBR (Rally-Base-Rally) / DBD (Drop-Base-Drop): Continuation
        - RBD (Rally-Base-Drop) / DBR (Drop-Base-Rally): Reversal
        Requires 'Clean Departure' (explosive move) and 'Compact Base' (3-5 candles).
        """
        if len(df) < lookback:
            return self._neutral("SupplyDemand", "Not enough candles")

        high = df["high"].astype(float).values
        low = df["low"].astype(float).values
        open_ = df["open"].astype(float).values
        close = df["close"].astype(float).values
        atr = self._atr(df, self.atr_period)
        price = close[-1]

        def is_explosive(i):
            body = abs(close[i] - open_[i])
            candle_range = high[i] - low[i]
            return body > atr * 1.5 or (body / max(candle_range, 0.0001) > 0.8 and candle_range > atr)

        def is_base(i):
            return abs(close[i] - open_[i]) < atr * 0.6

        zones = []
        # Search for zones in the last 'lookback' candles
        for i in range(lookback - 10, 5, -1):
            idx = len(df) - i
            # Check for 3-candle base (Compact Base)
            if is_base(idx) and is_base(idx-1) and is_base(idx-2):
                base_high = np.max(high[idx-2:idx+1])
                base_low = np.min(low[idx-2:idx+1])
                
                # Check for explosive departure (Clean Departure)
                if is_explosive(idx+1):
                    departure_up = close[idx+1] > open_[idx+1]
                    approach_up = close[idx-3] > open_[idx-3] if idx > 3 else departure_up
                    
                    bias = "BUY" if departure_up else "SELL"
                    pattern_type = ""
                    if approach_up and departure_up: pattern_type = "RBR"
                    elif not approach_up and not departure_up: pattern_type = "DBD"
                    elif approach_up and not departure_up: pattern_type = "RBD"
                    else: pattern_type = "DBR"

                    # Check freshness (has price returned to base since then?)
                    future_prices = low[idx+2:] if departure_up else high[idx+2:]
                    fresh = True
                    if len(future_prices) > 0:
                        if departure_up and np.min(future_prices) <= base_high: fresh = False
                        if not departure_up and np.max(future_prices) >= base_low: fresh = False
                    
                    if fresh:
                        zones.append({
                            "type": pattern_type,
                            "bias": bias,
                            "low": base_low,
                            "high": base_high,
                            "entry": base_high if bias == "BUY" else base_low,
                            "confidence": 0.75 + (0.1 if is_explosive(idx+2) else 0.0)
                        })

        if not zones:
            return self._neutral("SupplyDemand")

        # Pick the nearest fresh zone
        best_zone = min(zones, key=lambda z: abs(price - z["entry"]))
        return {
            "pattern": f"SupplyDemand_{best_zone['type']}",
            "confidence": self._clip_confidence(best_zone["confidence"]),
            "bias": best_zone["bias"],
            "entry": float(best_zone["entry"]),
            "levels": {"base_low": float(best_zone["low"]), "base_high": float(best_zone["high"])},
            "reasoning": f"Institutional {best_zone['type']} fresh zone detected with clean departure",
        }

    def analyze(self, df):
        """
        Run all pattern detections and return both the best pattern and all technique details.
        """
        results = {
            "SMC": self.detect_smc(df),
            "OrderBlock": self.detect_order_blocks(df),
            "FVG": self.detect_fair_value_gap(df),
            "MarketStructure": self.detect_market_structure(df),
            "SupplyDemand": self.detect_supply_demand_zones(df),
            "TrendLine": self.detect_trend_lines(df),
            "SupportResistance": self.detect_support_resistance(df),
            "PricePattern": self.detect_price_patterns(df),
        }
        best = max(results.values(), key=lambda x: x["confidence"])
        return {
            "pattern": best["pattern"],
            "confidence": best["confidence"],
            "bias": best["bias"],
            "entry": best["entry"],
            "reasoning": best["reasoning"],
            "details": results,
        }
