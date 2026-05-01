import json
import os
import time
from typing import Dict, Any, Optional

# Use /tmp for persistence on Vercel
if os.environ.get("VERCEL"):
    DB_FILE = "/tmp/db.json"
else:
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
        if "conversations" not in self.data:
            self.data["conversations"] = {} # key: conv_id, value: list of messages
        if "merchant_history" not in self.data:
            self.data["merchant_history"] = {} # key: mid, value: list of messages

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
        try:
            v_key = f"{scope}:{context_id}"
            current_v = self.data["versions"].get(v_key, -1)

            if version <= current_v:
                return False # No-op

            if scope == "category":
                self.data["categories"][context_id] = payload
            elif scope == "merchant":
                # Ensure merchant_id is consistent
                mid = payload.get("merchant_id", context_id)
                self.data["merchants"][mid] = payload
            elif scope == "customer":
                cid = payload.get("customer_id", context_id)
                self.data["customers"][cid] = payload
            elif scope == "trigger":
                tid = payload.get("id", context_id)
                self.data["triggers"][tid] = payload
            else:
                # Generic scope handling
                if scope + "s" not in self.data:
                    self.data[scope + "s"] = {}
                self.data[scope + "s"][context_id] = payload
            
            self.data["versions"][v_key] = version
            self.save()
            return True
        except Exception as e:
            print(f"Upsert error: {e}")
            raise e

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

    def record_message(self, mid: str, conv_id: str, message: str):
        # Per conversation history
        if conv_id not in self.data["conversations"]:
            self.data["conversations"][conv_id] = []
        self.data["conversations"][conv_id].append({
            "message": message,
            "timestamp": time.time()
        })
        self.data["conversations"][conv_id] = self.data["conversations"][conv_id][-10:]
        
        # Global merchant history (for auto-reply detection)
        if mid not in self.data["merchant_history"]:
            self.data["merchant_history"][mid] = []
        self.data["merchant_history"][mid].append({
            "message": message,
            "timestamp": time.time()
        })
        self.data["merchant_history"][mid] = self.data["merchant_history"][mid][-10:]
        
        self.save()

    def is_auto_reply(self, mid: str, message: str) -> bool:
        history = self.data["merchant_history"].get(mid, [])
        if len(history) < 3:
            return False
        
        # Check if the same message was sent 3 times recently (global for merchant)
        consecutive_count = 0
        for item in reversed(history):
            if item["message"] == message:
                consecutive_count += 1
            else:
                # We allow for interleaved messages if they are identical overall
                pass
        
        # If the same message appears 3 times in last 5 messages, it's an auto-reply
        count = sum(1 for item in history[-5:] if item["message"] == message)
        return count >= 3
