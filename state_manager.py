import json
import os
from typing import Dict, Any, Optional

DB_FILE = os.path.join(os.path.dirname(__file__), "db.json")

class StateManager:
    """
    Handles persistence of contexts (Category, Merchant, Customer, Trigger)
    with versioning and suppression tracking.
    """
    def __init__(self):
        self.data = self._load()
        if "versions" not in self.data:
            self.data["versions"] = {}
        if "suppression" not in self.data:
            self.data["suppression"] = {} # key: (merchant_id or customer_id), value: last_intent

    def _load(self):
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r") as f:
                    return json.load(f)
            except:
                pass
        return {
            "categories": {},
            "merchants": {},
            "customers": {},
            "triggers": {},
            "versions": {},
            "suppression": {}
        }

    def save(self):
        with open(DB_FILE, "w") as f:
            json.dump(self.data, f, indent=2)

    def upsert_context(self, scope: str, context_id: str, payload: Dict[str, Any], version: int = 0):
        """
        Idempotent: same version = no-op. Higher version replaces.
        """
        v_key = f"{scope}:{context_id}"
        current_v = self.data["versions"].get(v_key, -1)

        if version <= current_v:
            return False # No-op

        if scope == "category":
            self.data["categories"][context_id] = payload
        elif scope == "merchant":
            self.data["merchants"][context_id] = payload
        elif scope == "customer":
            self.data["customers"][context_id] = payload
        elif scope == "trigger":
            self.data["triggers"][context_id] = payload
        
        self.data["versions"][v_key] = version
        self.save()
        return True

    def get_category(self, slug):
        return self.data["categories"].get(slug, {})

    def get_merchant(self, mid):
        return self.data["merchants"].get(mid, {})

    def get_customer(self, cid):
        return self.data["customers"].get(cid, {})

    def get_trigger(self, tid):
        return self.data["triggers"].get(tid, {})

    def is_suppressed(self, key: str, intent: str) -> bool:
        """
        Check if the same strategy was used within 6 hours.
        """
        import time
        supp_data = self.data["suppression"].get(key)
        if not supp_data:
            return False
            
        last_intent = supp_data.get("intent")
        last_time = supp_data.get("timestamp", 0)
        
        # 6 hours = 6 * 3600 seconds
        is_recent = (time.time() - last_time) < (6 * 3600)
        
        return last_intent == intent and is_recent

    def update_suppression(self, key: str, intent: str):
        import time
        self.data["suppression"][key] = {
            "intent": intent,
            "timestamp": time.time()
        }
        self.save()

    def clear_suppression(self, key: str):
        if key in self.data["suppression"]:
            del self.data["suppression"][key]
            self.save()
