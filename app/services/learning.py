import json
import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class LearningDB:
    def __init__(self, path: str = None):
        from ..core.config import get_settings
        self.path = path or get_settings().LEARNING_DB
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self._write({"rules": {}, "categories": {}, "feedback": []})
        self.db = self._read()

    def _read(self) -> Dict[str, Any]:
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: Dict[str, Any]):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_rule_weight(self, rule_id: str, default: float = 1.0) -> float:
        return self.db.get("rules", {}).get(rule_id, {}).get("weight", default)

    def get_category_weight(self, category: str, default: float = 1.0) -> float:
        return self.db.get("categories", {}).get(category, {}).get("weight", default)

    def update_category_weight(self, category: str, correct: bool):
        cats = self.db.setdefault("categories", {}).setdefault(category, {"weight": 1.0, "tp":0, "fp":0})
        if correct:
            cats["tp"] += 1
            cats["weight"] = min(2.0, cats["weight"] + 0.03)
        else:
            cats["fp"] += 1
            cats["weight"] = max(0.5, cats["weight"] - 0.05)
        self._write(self.db)

    def update_with_feedback(self, feedback: List[Dict[str, Any]]):
        changed = False
        for fb in feedback:
            rid = fb["rule_id"]
            correct = fb["correct"]
            rules = self.db.setdefault("rules", {}).setdefault(rid, {"weight": 1.0, "tp":0, "fp":0, "fn":0})
            if correct:
                rules["tp"] += 1
                rules["weight"] = min(2.0, rules["weight"] + 0.05)
            else:
                rules["fp"] += 1
                rules["weight"] = max(0.5, rules["weight"] - 0.08)
            changed = True
            self.db.setdefault("feedback", []).append(fb)
        if changed:
            self._write(self.db)

    def replace_db(self, data: Dict[str, Any]):
        self.db = data
        self._write(self.db)
