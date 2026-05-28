import asyncio
import json
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple

from data.mt5_client import MT5Client
from data.news_fetcher import NewsFetcher
from strategies.hybrid_strategy import HybridStrategy
from alerts.discord_bot import DiscordBot
from learning.database import SignalDatabase
from learning.optimizer import LearningOptimizer
from data.storage import SignalStorage
from learning.adaptive_weights import AdaptiveWeighting
from config.runtime import load_settings

logger = logging.getLogger("GoldAI.Main")
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class GoldAIEngine:
    """ตัวขับเคลื่อนหลักของระบบ Gold AI (Signal-Only Edition)"""

    def __init__(self) -> None:
        self.project_root: str = project_root
        self.config: Dict[str, Any] = load_settings(self.project_root)
        data_dir: str = os.path.join(self.project_root, "data")

        self.mt5: MT5Client = MT5Client(
            self.config["symbol"],
            login=self.config.get("mt5_login"),
            password=self.config.get("mt5_password"),
            server=self.config.get("mt5_server")
        )
        self.news: NewsFetcher = NewsFetcher()
        self.bot: DiscordBot = DiscordBot(self.config.get("discord_bot_token", ""), self.config.get("discord_webhook_url", ""))
        self.db: SignalDatabase = SignalDatabase(os.path.join(data_dir, "signals_history.db"))
        self.optimizer: LearningOptimizer = LearningOptimizer(
            learned_params_path=os.path.join(data_dir, "learned_params.json"),
        )
        self.strategy: HybridStrategy = HybridStrategy(self.config["params"])
        self.storage: SignalStorage = SignalStorage(os.path.join(data_dir, "self_generated_data.db"))
        self.adaptive_weights: AdaptiveWeighting = AdaptiveWeighting(
            storage_path=os.path.join(data_dir, "self_generated_data.db"),
            weights_path=os.path.join(data_dir, "technique_weights.json"),
            signal_db_path=os.path.join(data_dir, "signals_history.db"),
            initial_weights=self.config.get("technique_weights"),
        )

        # --- Signal Layer Config ---
        self.analysis_timeframes: List[Dict[str, Any]] = self.config["analysis_timeframes"]
        self.higher_timeframe_name: str = self.config.get("higher_timeframe_name", "H4")
        self.setup_confidence_threshold: float = float(self.config.get("setup_confidence_threshold", 0.62))
        self.confidence_threshold: float = float(self.config.get("confidence_threshold", 0.75))
        self.trigger_confidence_threshold: float = float(self.config.get("trigger_confidence_threshold", 0.82))
        self.sure_shot_threshold: float = float(self.config.get("sure_shot_threshold", 0.88))
        self.point_value: float = float(self.config.get("point_value", 0.01))
        self.entry_tolerance_points: float = float(self.config.get("entry_tolerance_points", 120))
        self.signal_cooldown: timedelta = timedelta(minutes=float(self.config.get("signal_cooldown_minutes", 30)))
        self.max_signal_age_minutes: float = float(self.config.get("max_signal_age_minutes", 180))

        # Config news lookback/lookahead
        self.news_lookback_minutes: float = float(self.config.get("news_lookback_minutes", 30))
        self.news_lookahead_minutes: float = float(self.config.get("news_lookahead_minutes", 90))

        self.last_alert_times: Dict[str, datetime] = {}

    def _fmt_price(self, value: Optional[float]) -> str:
        return f"{float(value):.2f}" if value is not None else "N/A"

    def _alert_key(self, decision: Dict[str, Any]) -> str:
        return f"{decision['mode']}:{decision['direction']}:{decision['timeframe']}"

    def _should_send_alert(self, decision: Dict[str, Any]) -> bool:
        key = self._alert_key(decision)
        last_sent = self.last_alert_times.get(key)
        now = datetime.now(timezone.utc)
        if last_sent and now - last_sent < self.signal_cooldown:
            return False
        self.last_alert_times[key] = now
        return True

    def _save_timeframe_analysis(self, result: Dict[str, Any], news_alert: str) -> None:
        features = {
            "current_price": float(result["current_price"]),
            "best_entry": float(result["best_entry"]),
            "entry_zone_low": float(result["entry_zone"][0]),
            "entry_zone_high": float(result["entry_zone"][1]),
            "atr": float(result.get("atr", 0.0)),
        }
        decision_metrics = {
            "technique_weights": self.adaptive_weights.get_all_weights(),
            "direction_scores": result.get("direction_scores", {}),
            "technique_summary": result.get("technique_summary", ""),
            "timeframe_role": result.get("timeframe_role", "signal"),
            "strategy_style": result.get("strategy_style", "day"),
            "risk_plan": result.get("risk_plan", {}),
            "context_summary": result.get("context_summary", ""),
            "news_alert": news_alert,
        }
        self.storage.save_analysis(
            symbol=self.config["symbol"],
            timeframe=result["timeframe"],
            technique=result["technique"],
            signal_direction=result["signal"],
            confidence=float(result["confidence"]),
            features=features,
            decision_metrics=decision_metrics,
            hold_recommendation=result["hold_recommendation"],
        )

    def _combine_timeframe_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        scores = {"BUY": 0.0, "SELL": 0.0}
        entry_candidates: Dict[str, List[Tuple[float, float]]] = {"BUY": [], "SELL": []}
        matching_results: Dict[str, List[Tuple[Dict[str, Any], float]]] = {"BUY": [], "SELL": []}
        current_price = results[0]["current_price"]
        timeframe_votes = []

        for result in results:
            direction = result.get("direction", "WAIT")
            confidence = float(result.get("confidence", 0.0))
            tf_weight = float(result.get("timeframe_weight", 1.0))
            timeframe_votes.append(f"{result['timeframe']}:{direction} {confidence:.2f}")

            if direction in ("BUY", "SELL") and confidence > 0:
                score = confidence * tf_weight
                scores[direction] += score
                entry_candidates[direction].append((float(result["best_entry"]), score))
                matching_results[direction].append((result, score))

        if scores["BUY"] == 0 and scores["SELL"] == 0:
            primary = max(results, key=lambda r: r.get("confidence", 0.0))
            return {
                **primary,
                "direction": "WAIT",
                "signal": "WAIT",
                "mode": "WAIT",
                "confidence": 0.45,
                "timeframe_votes": "; ".join(timeframe_votes),
                "reasoning": "No timeframe has a strong directional edge",
            }

        direction = "BUY" if scores["BUY"] >= scores["SELL"] else "SELL"
        opposite = "SELL" if direction == "BUY" else "BUY"
        dominant = scores[direction]
        opposing = scores[opposite]
        alignment = dominant / max(dominant + opposing, 0.0001)
        primary, primary_score = max(matching_results[direction], key=lambda item: item[1])

        weighted_entry = sum(entry * score for entry, score in entry_candidates[direction]) / sum(
            score for _, score in entry_candidates[direction]
        )
        avg_confidence = sum(result["confidence"] * score for result, score in matching_results[direction]) / sum(
            score for _, score in matching_results[direction]
        )
        consensus_bonus = 0.04 if len(matching_results[direction]) >= 2 else 0.0
        confidence = min(0.95, avg_confidence * 0.65 + alignment * 0.3 + consensus_bonus)

        sl_distance = abs(primary["best_entry"] - primary["sl"]) if primary.get("sl") is not None else 0.0
        tp_distance = abs(primary.get("tp", 0) - primary["best_entry"]) if primary.get("tp") is not None else 0.0
        if direction == "BUY":
            sl = weighted_entry - sl_distance if sl_distance else primary.get("sl")
            tp = weighted_entry + tp_distance if tp_distance else primary.get("tp")
        else:
            sl = weighted_entry + sl_distance if sl_distance else primary.get("sl")
            tp = weighted_entry - tp_distance if tp_distance else primary.get("tp")

        zone_width = max(
            abs(primary["entry_zone"][1] - primary["entry_zone"][0]) / 2,
            self.entry_tolerance_points * self.point_value,
        )
        entry_zone = (weighted_entry - zone_width, weighted_entry + zone_width)
        technique_summary = f"TF votes: {'; '.join(timeframe_votes)} | {primary.get('technique_summary', '')}"

        hold_recommendation = primary["hold_recommendation"]
        risk_plan = dict(primary.get("risk_plan", {}))
        if risk_plan and sl is not None and tp is not None:
            stop_distance = abs(weighted_entry - sl)
            target_distance = abs(tp - weighted_entry)
            rr = target_distance / stop_distance if stop_distance else 0.0
            risk_plan.update(
                {
                    "stop_distance": stop_distance,
                    "target_distance": target_distance,
                    "rr": rr,
                    "text": (
                        f"{risk_plan.get('style', primary.get('strategy_style', 'day')).upper()} risk: "
                        f"hard SL {stop_distance:.2f}, target {target_distance:.2f}, "
                        f"R:R {rr:.2f}, risk {risk_plan.get('risk_pct', 1.0):.1f}%"
                    ),
                }
            )
        active_techniques = set()
        for result, _ in matching_results[direction]:
            for name, details in result.get("technique_details", {}).items():
                if details.get("bias") == direction and float(details.get("confidence", 0.0) or 0.0) > 0:
                    active_techniques.add(name)

        trend_results = [result for result, _ in matching_results[direction] if result.get("timeframe_role") == "trend"]
        if trend_results and confidence >= self.confidence_threshold:
            hold_recommendation = (
                f"Longer hold allowed: trend timeframe confirms {direction}. "
                "Keep 1-minute monitoring and trail risk after price reaches 1R."
            )
        elif primary.get("timeframe_role") == "entry":
            hold_recommendation = (
                f"Short hold preferred: entry timeframe leads {direction}. "
                "Use the best-entry zone and exit faster if confirmation disappears."
            )

        return {
            "signal": direction if confidence >= self.confidence_threshold else f"SETUP_{direction}",
            "direction": direction,
            "reasoning": primary["reasoning"],
            "entry": weighted_entry,
            "best_entry": weighted_entry,
            "current_price": current_price,
            "entry_zone": entry_zone,
            "sl": sl,
            "tp": tp,
            "technique": primary["technique"],
            "timeframe": primary["timeframe"],
            "timeframe_role": primary.get("timeframe_role", "signal"),
            "strategy_style": primary.get("strategy_style", "day"),
            "confidence": confidence,
            "hold_recommendation": hold_recommendation,
            "risk_plan": risk_plan,
            "context_summary": primary.get("context_summary", ""),
            "atr": primary.get("atr", 0.0),
            "technique_summary": technique_summary,
            "active_techniques": sorted(active_techniques),
            "timeframe_votes": "; ".join(timeframe_votes),
            "direction_scores": scores,
            "primary_result": primary,
        }

    def _apply_news_and_double_check(self, combined: Dict[str, Any], high_impact_news: List[Dict[str, Any]]) -> Dict[str, Any]:
        direction = combined["direction"]
        confidence = float(combined["confidence"])
        reasons = [combined["reasoning"]]
        block_trigger = False

        primary_by_timeframe = {
            item["timeframe"]: item for item in combined.get("all_timeframe_results", [])
        }
        higher_result = primary_by_timeframe.get(self.higher_timeframe_name)
        if higher_result and direction in ("BUY", "SELL"):
            higher_direction = higher_result.get("direction")
            higher_confidence = float(higher_result.get("confidence", 0.0))
            if higher_direction in ("BUY", "SELL") and higher_direction != direction and higher_confidence >= 0.62:
                confidence = max(0.1, confidence - 0.18)
                block_trigger = True
                reasons.append(
                    f"Double-check: {self.higher_timeframe_name} is opposite ({higher_direction} {higher_confidence:.2f})"
                )
            elif higher_direction == direction and higher_confidence >= 0.62:
                confidence = min(0.95, confidence + 0.04)
                reasons.append(f"Double-check: {self.higher_timeframe_name} confirms {direction}")
            else:
                reasons.append(f"Double-check: {self.higher_timeframe_name} is neutral")

        watched_currencies = set(self.config.get("news_currencies", ["USD"]))
        relevant_news = [
            news for news in high_impact_news if news.get("currency") in watched_currencies
        ]
        if relevant_news:
            penalty = float(self.config.get("news_confidence_penalty", 0.08))
            confidence = max(0.1, confidence - penalty)
            reasons.append(f"News filter: high-impact {relevant_news[0]['currency']} news reduces confidence")

        combined["confidence"] = confidence
        combined["reasoning"] = " | ".join(reasons)
        combined["block_trigger"] = block_trigger
        return combined

    def _build_signal_decision(self, combined: Dict[str, Any]) -> Dict[str, Any]:
        direction = combined["direction"]
        confidence = float(combined["confidence"])
        current_price = float(combined["current_price"])
        best_entry = float(combined["best_entry"])
        zone_low, zone_high = combined["entry_zone"]
        atr = float(combined.get("atr", 0.0))

        dynamic_tolerance = max(self.entry_tolerance_points * self.point_value, atr * 0.5)
        within_ideal_zone = zone_low - (dynamic_tolerance * 0.5) <= current_price <= zone_high + (dynamic_tolerance * 0.5)
        momentum_tolerance = dynamic_tolerance * 2.0
        within_momentum_zone = zone_low - momentum_tolerance <= current_price <= zone_high + momentum_tolerance

        decision = {
            **combined,
            "mode": "WAIT",
            "signal": "WAIT",
            "ready_to_enter": False,
            "distance_to_entry": abs(current_price - best_entry),
        }

        if direction not in ("BUY", "SELL"):
            return decision

        if confidence >= self.sure_shot_threshold and not combined.get("block_trigger"):
            if within_momentum_zone:
                decision["mode"] = "SURE_SHOT"
                decision["signal"] = direction
                decision["ready_to_enter"] = True
                return decision

        if confidence >= self.trigger_confidence_threshold and not combined.get("block_trigger"):
            if within_ideal_zone:
                decision["mode"] = "ENTRY_TRIGGER"
                decision["signal"] = direction
                decision["ready_to_enter"] = True
                return decision
            else:
                decision["mode"] = "STRONG_SETUP"
                decision["signal"] = f"STRONG_{direction}"
                return decision

        if confidence >= self.setup_confidence_threshold:
            decision["mode"] = "SETUP"
            decision["signal"] = f"SETUP_{direction}"

        return decision

    def _news_alert_text(self, high_impact_news: List[Dict[str, Any]]) -> str:
        if not high_impact_news:
            return "No major news"
        first = high_impact_news[0]
        return f"⚠️ High Impact News: {first.get('event', 'Unknown event')} ({first.get('currency', 'N/A')})"

    async def run_analysis_cycle(self) -> None:
        """Main analysis loop that triggers signals immediately upon confidence match"""
        logger.info("🔍 Analyzing market...")

        self.strategy.set_technique_weights(self.adaptive_weights.get_all_weights())
        try:
            high_impact_news = self.news.get_high_impact_news(
                lookback_mins=self.news_lookback_minutes,
                lookahead_mins=self.news_lookahead_minutes
            )
        except TypeError:
            high_impact_news = self.news.get_high_impact_news()
        news_alert = self._news_alert_text(high_impact_news)

        timeframe_results = []
        for timeframe_config in self.analysis_timeframes:
            df = self.mt5.get_rates(timeframe_config["value"])
            if df is None or df.empty:
                logger.warning(f"Failed to get market data for {timeframe_config['name']}")
                continue

            result = self.strategy.analyze(
                df,
                timeframe_name=timeframe_config["name"],
                role=timeframe_config.get("role", "signal"),
            )
            result["timeframe_weight"] = float(timeframe_config.get("weight", 1.0))
            result["timeframe_value"] = timeframe_config["value"]
            timeframe_results.append(result)
            self._save_timeframe_analysis(result, news_alert)

        if not timeframe_results:
            logger.error("No market data available for analysis")
            return

        combined = self._combine_timeframe_results(timeframe_results)
        combined["all_timeframe_results"] = timeframe_results
        combined = self._apply_news_and_double_check(combined, high_impact_news)

        final_decision = self._build_signal_decision(combined)

        if final_decision["mode"] == "WAIT":
            logger.info(
                f"📊 No strong signal (direction={final_decision['direction']}, "
                f"confidence={final_decision['confidence']:.2f})"
            )
            return

        if not self.config.get("discord_webhook_url"):
            logger.warning("⚠️ Signal calculated but DISCORD_WEBHOOK_URL is not configured.")
            return

        if not self._should_send_alert(final_decision):
            logger.info(f"⏳ Signal on cooldown: {final_decision['signal']}")
            return

        confidence_label = "High" if final_decision["confidence"] >= 0.85 else "Medium"

        mode_label = {
            "ENTRY_TRIGGER": "🎯 ENTRY NOW",
            "STRONG_SETUP": "🔥 STRONG SETUP",
            "SURE_SHOT": "🚀 SURE-SHOT",
            "SETUP": "🔔 SETUP"
        }.get(final_decision["mode"], "INFO")

        sent = self.bot.send_signal_card(
            self.config["symbol"],
            final_decision["signal"],
            final_decision["entry"] if final_decision["mode"] in ("ENTRY_TRIGGER", "SURE_SHOT") else None,
            final_decision["sl"],
            final_decision["tp"],
            final_decision["reasoning"] + f" | Confidence: {final_decision['confidence']:.2f}",
            confidence=confidence_label if final_decision["mode"] in ("ENTRY_TRIGGER", "SURE_SHOT") else "Setup",
            news=news_alert,
            mode=mode_label,
            timeframe=final_decision["timeframe"],
            current_price=final_decision["current_price"],
            ideal_entry=final_decision["best_entry"],
            entry_zone=final_decision["entry_zone"],
            hold_recommendation=final_decision["hold_recommendation"],
            risk_plan=final_decision.get("risk_plan", {}),
            technique_summary=final_decision["technique_summary"],
        )

        if sent:
            self.db.save_signal(
                self.config["symbol"],
                final_decision["direction"],
                final_decision["current_price"],
                final_decision["sl"],
                final_decision["tp"],
                final_decision["technique"],
                {
                    **self.config["params"],
                    "timeframe": final_decision["timeframe"],
                    "confidence": final_decision["confidence"],
                    "mode": final_decision["mode"],
                    "active_techniques": final_decision.get("active_techniques", []),
                },
            )
            logger.info(f"🚀 Signal Sent: {mode_label} {final_decision['direction']} | Conf: {final_decision['confidence']:.2f}")

    async def monitor_signals(self) -> None:
        """ติดตามผลลัพธ์ของสัญญาณเพื่อนำไปปรับปรุงน้ำหนัก (Adaptive Weighting)"""
        self.db.expire_stale_signals(self.max_signal_age_minutes)

        current_price = self.mt5.get_current_price()
        if not current_price:
            return
        ask, bid = current_price

        pending = self.db.get_pending_signals()
        for sig in pending:
            sig_id, symbol, direction, entry, sl, tp, strategy, params_json, ts, status, outcome = sig
            try:
                params_used = json.loads(params_json) if params_json else {}
            except json.JSONDecodeError:
                params_used = {}
            active_techniques = params_used.get("active_techniques") or [strategy]

            if direction == "BUY":
                if bid <= sl:
                    self.db.update_signal_outcome(sig_id, "FAILED", outcome=-1)
                    self.optimizer.analyze_and_optimize(sig, bid)
                    for technique in active_techniques:
                        self.adaptive_weights.update_performance(technique, direction, -1)
                    logger.info(f"📉 Signal {sig_id} FAILED (Hit SL)")
                elif bid >= tp:
                    self.db.update_signal_outcome(sig_id, "SUCCESS", outcome=1)
                    for technique in active_techniques:
                        self.adaptive_weights.update_performance(technique, direction, 1)
                    logger.info(f"📈 Signal {sig_id} SUCCESS (Hit TP)!")

            elif direction == "SELL":
                if ask >= sl:
                    self.db.update_signal_outcome(sig_id, "FAILED", outcome=-1)
                    self.optimizer.analyze_and_optimize(sig, ask)
                    for technique in active_techniques:
                        self.adaptive_weights.update_performance(technique, direction, -1)
                    logger.info(f"📉 Signal {sig_id} FAILED (Hit SL)")
                elif ask <= tp:
                    self.db.update_signal_outcome(sig_id, "SUCCESS", outcome=1)
                    for technique in active_techniques:
                        self.adaptive_weights.update_performance(technique, direction, 1)
                    logger.info(f"📈 Signal {sig_id} SUCCESS (Hit TP)!")

    async def main_loop(self) -> None:
        """Loop หลักสำหรับการส่งสัญญาณ"""
        if not self.mt5.connect():
            logger.critical("Failed to connect to MT5. Exiting.")
            return

        broker_point = self.mt5.get_point()
        if broker_point:
            self.point_value = broker_point
            self.config["params"]["point_value"] = broker_point
            self.strategy.params["point_value"] = broker_point

        bot_task = None
        if self.config.get("discord_bot_token"):
            bot_task = asyncio.create_task(self.bot.start())

        try:
            while True:
                try:
                    if not self.mt5.ensure_connection():
                        await asyncio.sleep(30)
                        continue

                    await self.run_analysis_cycle()
                    await self.monitor_signals()
                except Exception as e:
                    logger.exception(f"Unexpected error in main cycle: {e}")

                await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info("Main loop cancelled.")
        finally:
            if bot_task:
                bot_task.cancel()
            self.mt5.shutdown()
