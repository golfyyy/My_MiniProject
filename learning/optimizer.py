import json
import os
from typing import Dict, Any, Optional


class LearningOptimizer:
    """Adjusts strategy parameters after failed signals without overwriting settings.json."""

    def __init__(self, learned_params_path: str = "data/learned_params.json") -> None:
        self.learned_params_path: str = learned_params_path

    def _load_learned(self) -> Dict[str, Any]:
        if not os.path.exists(self.learned_params_path):
            return {"params": {}}
        with open(self.learned_params_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"params": {}}
        data.setdefault("params", {})
        return data

    def _save_learned(self, data: Dict[str, Any]) -> None:
        learned_dir = os.path.dirname(self.learned_params_path)
        if learned_dir:
            os.makedirs(learned_dir, exist_ok=True)
        with open(self.learned_params_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    @staticmethod
    def _extract_direction(failed_signal: Any) -> Optional[str]:
        if isinstance(failed_signal, dict):
            return failed_signal.get("direction")
        if isinstance(failed_signal, (tuple, list)) and len(failed_signal) > 2:
            return failed_signal[2]
        return None

    def analyze_and_optimize(self, failed_signal: Any, current_price: float) -> str:
        """
        Analyze a losing signal and tighten RSI thresholds in learned_params.json.
        """
        del current_price  # reserved for future price-distance based tuning

        direction = self._extract_direction(failed_signal)
        if direction not in ("BUY", "SELL"):
            return "No optimization applied: unknown signal direction."

        learned = self._load_learned()
        params = learned["params"]

        if direction == "BUY":
            current = float(params.get("rsi_buy_threshold", 40))
            params["rsi_buy_threshold"] = max(20.0, current - 0.2)
        elif direction == "SELL":
            current = float(params.get("rsi_sell_threshold", 60))
            params["rsi_sell_threshold"] = min(80.0, current + 0.2)

        learned["params"] = params
        self._save_learned(learned)
        return f"Adjusted {direction} RSI threshold in learned params."

