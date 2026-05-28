import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from .database import SignalDatabase

logger = logging.getLogger("GoldAI.AdaptiveWeighting")


class AdaptiveWeighting:
    """Tracks technique performance and persists weights outside settings.json."""

    def __init__(
        self,
        storage_path: str = "data/self_generated_data.db",
        weights_path: str = "data/technique_weights.json",
        signal_db_path: str = "data/signals_history.db",
        initial_weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.storage_path: str = storage_path
        self.weights_path: str = weights_path
        self.db: SignalDatabase = SignalDatabase(signal_db_path)
        self.initial_weights: Dict[str, float] = initial_weights or {}
        self.technique_weights: Dict[str, float] = defaultdict(lambda: 1.0)
        self.performance_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._load_weights()

    def _load_weights(self) -> None:
        if os.path.exists(self.weights_path):
            try:
                with open(self.weights_path, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                if isinstance(stored, dict) and stored:
                    self.technique_weights = defaultdict(float, stored)
                    return
            except Exception as e:
                logger.error("Failed to load weights from %s: %s", self.weights_path, e)

        if self.initial_weights:
            self.technique_weights = defaultdict(float, self.initial_weights)
            self._save_weights()

    def _save_weights(self) -> None:
        try:
            weights_dir = os.path.dirname(self.weights_path)
            if weights_dir:
                os.makedirs(weights_dir, exist_ok=True)
            with open(self.weights_path, "w", encoding="utf-8") as f:
                json.dump(dict(self.technique_weights), f, indent=4)
        except Exception as e:
            logger.error("Failed to save weights to %s: %s", self.weights_path, e)

    def update_performance(self, technique: str, signal_direction: str, outcome: float) -> None:
        """
        Update performance for a technique based on signal outcome.
        outcome: 1 for win (TP), -1 for loss (SL), 0 for breakeven/unknown.
        """
        self.performance_history[technique].append(
            {
                "direction": signal_direction,
                "outcome": outcome,
                "timestamp": datetime.now(timezone.utc),
            }
        )
        if len(self.performance_history[technique]) > 50:
            self.performance_history[technique] = self.performance_history[technique][-50:]
        self._recalculate_weights()

    def _recalculate_weights(self) -> None:
        """Recalculate weights using a sliding window win rate with smoothing."""
        for tech, history in self.performance_history.items():
            if not history:
                self.technique_weights[tech] = 1.0
                continue

            weighted_wins = 0.0
            total_weight = 0.0

            for idx, h in enumerate(reversed(history)):
                weight = max(0.5, 1.0 - (idx * 0.01))
                total_weight += weight
                if h["outcome"] == 1:
                    weighted_wins += weight
                elif h["outcome"] == -1:
                    weighted_wins -= weight * 0.6

            win_rate = (weighted_wins / total_weight) if total_weight > 0 else 0.5
            current_weight = self.technique_weights[tech]
            target_weight = max(0.2, 1.0 + (win_rate - 0.5) * 1.2)
            self.technique_weights[tech] = float((current_weight * 0.8) + (target_weight * 0.2))

        self._save_weights()

    def get_weight(self, technique: str) -> float:
        return self.technique_weights.get(technique, 1.0)

    def get_all_weights(self) -> Dict[str, float]:
        return dict(self.technique_weights)

