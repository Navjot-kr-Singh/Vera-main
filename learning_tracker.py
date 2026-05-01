import json
import os
from collections import defaultdict

LEARNING_DATA_FILE = os.path.join(os.path.dirname(__file__), "learning_data.json")

class LearningTracker:
    """
    Simulates a learning system by tracking which message modes
    perform best for a given trigger + category combination.
    Persists data to learning_data.json across server restarts.
    """

    def __init__(self):
        self.data = self._load()

    def _load(self):
        if os.path.exists(LEARNING_DATA_FILE):
            try:
                with open(LEARNING_DATA_FILE, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"patterns": {}, "total_runs": 0}

    def _save(self):
        try:
            with open(LEARNING_DATA_FILE, "w") as f:
                json.dump(self.data, f, indent=2)
        except IOError:
            pass

    def _key(self, category, trigger):
        return f"{category}|{trigger}"

    def record(self, category, trigger, modes):
        """
        Record the results of a generation run.
        The mode with the highest confidence_score is treated as the 'winner'.
        """
        self.data["total_runs"] = self.data.get("total_runs", 0) + 1

        if not modes:
            self._save()
            return

        winner = max(modes, key=lambda m: m.get("confidence_score", 0))
        key = self._key(category, trigger)

        patterns = self.data.setdefault("patterns", {})
        if key not in patterns:
            patterns[key] = {
                "category": category,
                "trigger": trigger,
                "runs": 0,
                "mode_wins": defaultdict(int)
            }

        patterns[key]["runs"] += 1
        patterns[key]["mode_wins"][winner["mode_id"]] = \
            patterns[key]["mode_wins"].get(winner["mode_id"], 0) + 1

        self._save()

    def get_insight(self, category, trigger):
        """
        Returns a dict with:
          - best_mode_id: the historically winning mode
          - runs: how many times this combo has been run
          - insight_text: human-readable learning summary
          - boost_mode_id: mode to boost (same as best_mode_id)
        Returns None if not enough data.
        """
        key = self._key(category, trigger)
        pattern = self.data.get("patterns", {}).get(key)

        if not pattern or pattern["runs"] < 1:
            return None

        mode_wins = pattern.get("mode_wins", {})
        if not mode_wins:
            return None

        best_mode_id = max(mode_wins, key=mode_wins.get)
        runs = pattern["runs"]

        mode_labels = {
            "aggressive": "🔥 Aggressive",
            "premium": "💎 Premium",
            "retention": "🎯 Retention",
            "growth": "🚀 Growth"
        }
        label = mode_labels.get(best_mode_id, best_mode_id.title())

        insight_text = (
            f"Based on {runs} past run{'s' if runs != 1 else ''}, "
            f"{label} mode performs best for {category}s on {trigger} campaigns."
        )

        return {
            "best_mode_id": best_mode_id,
            "runs": runs,
            "insight_text": insight_text,
            "boost_mode_id": best_mode_id
        }
