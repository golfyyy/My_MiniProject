import json
import logging
import os
from collections import defaultdict
from datetime import datetime

from .database import SignalDatabase

logger = logging.getLogger("GoldAI.AdaptiveWeighting")


class AdaptiveWeighting:
    """Tracks technique performance and persists weights outside settings.json."""

    def __init__(
        self,
        storage_path="data/self_generated_data.db",
        weights_path="data/technique_weights.json",
        signal_db_path="data/signals_history.db",
        initial_weights=None,
    ):
        self.storage_path = storage_path
        self.weights_path = weights_path
        self.db = SignalDatabase(signal_db_path)
        self.initial_weights = initial_weights or {}
        self.technique_weights = defaultdict(lambda: 1.0)
        self.performance_history = defaultdict(list)
        self._load_weights()

    def _load_weights(self):
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

    def _save_weights(self):
        try:
            weights_dir = os.path.dirname(self.weights_path)
            if weights_dir:
                os.makedirs(weights_dir, exist_ok=True)
            with open(self.weights_path, "w", encoding="utf-8") as f:
                json.dump(dict(self.technique_weights), f, indent=4)
        except Exception as e:
            logger.error("Failed to save weights to %s: %s", self.weights_path, e)

    def update_performance(self, technique, signal_direction, outcome):
        """
        Update performance for a technique based on signal outcome.
        outcome: 1 for win (TP), -1 for loss (SL), 0 for breakeven/unknown.
        """
        self.performance_history[technique].append(
            {
                "direction": signal_direction,
                "outcome": outcome,
                "timestamp": datetime.now(),
            }
        )
        if len(self.performance_history[technique]) > 50:
            self.performance_history[technique] = self.performance_history[technique][-50:]
        self._recalculate_weights()

    def _recalculate_weights(self):
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

    def get_weight(self, technique):
        return self.technique_weights.get(technique, 1.0)

    def get_all_weights(self):
        return dict(self.technique_weights)
