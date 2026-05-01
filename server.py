import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from message_engine import MessageCompositionEngine
from state_manager import StateManager
from datetime import datetime

load_dotenv()

app = FastAPI(title=os.getenv("APP_NAME", "Vera AI Engine"))
engine = MessageCompositionEngine()
state = StateManager()

# --- Static Files ---

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/app.js")
async def get_js():
    return FileResponse("static/app.js")

@app.get("/logo.png")
async def get_logo():
    return FileResponse("static/logo.png")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

# --- Demo UI Helpers ---

def get_now_ist():
    from datetime import timedelta, timezone
    return datetime.now(timezone(timedelta(hours=5, minutes=30)))

@app.get("/api/context")
async def get_ui_context():
    now = get_now_ist()
    hour = now.hour
    
    if 6 <= hour < 11: tod = "morning"
    elif 11 <= hour < 15: tod = "lunch time"
    elif 15 <= hour < 18: tod = "afternoon"
    elif 18 <= hour < 21: tod = "evening"
    else: tod = "night"
    
    return {
        "time_of_day": tod,
        "day_type": "weekend" if now.weekday() >= 5 else "weekday",
        "festival": None,
        "suggested_trigger": "search_surge",
        "current_time": now.strftime("%I:%M %p")
    }

class GenerateRequest(BaseModel):
    category: str
    merchant_name: str
    offer: str
    trigger: str
    customer_context: Optional[str] = "default"
    tone_style: Optional[str] = "default"

@app.post("/api/generate")
async def generate_ui_message(data: GenerateRequest):
    try:
        return engine.generate_variations(
            data.category, data.merchant_name, data.offer,
            data.trigger, data.customer_context, data.tone_style
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- Judge v1 API Endpoints ---

class ContextPayload(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: Optional[str] = None

class TickRequest(BaseModel):
    available_triggers: Optional[List[str]] = None
    now: Optional[str] = None

class ReplyRequest(BaseModel):
    message: Optional[str] = ""
    from_role: Optional[str] = "merchant"
    context: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"

@app.get("/v1/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/v1/metadata")
async def metadata():
    return {
        "team_name": "Navjot Singh",
        "model": "Deterministic Decision Engine v2"
    }

@app.post("/v1/context")
async def push_context(data: Dict[str, Any]):
    try:
        scope = data.get("scope")
        context_id = data.get("context_id")
        payload = data.get("payload")
        version = data.get("version", 0)
        
        if not all([scope, context_id, payload]):
            return JSONResponse(status_code=422, content={"error": "Missing required fields in context"})

        updated = state.upsert_context(scope, context_id, payload, version)
        return {"accepted": True, "updated": updated}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/v1/tick")
async def tick(data: Optional[TickRequest] = None):
    try:
        if not data or not data.available_triggers:
            return {"actions": []}
        
        actions = []
        for tid in data.available_triggers:
            trigger = state.get_trigger(tid)
            if not trigger:
                continue
            
            mid = trigger.get("merchant_id") or trigger.get("payload", {}).get("merchant_id")
            if not mid:
                continue
            
            merchant = state.get_merchant(mid)
            if not merchant:
                continue
            
            category_slug = merchant.get("category_slug")
            if not category_slug:
                continue
            
            customer_id = trigger.get("customer_id")
            customer = state.get_customer(customer_id) if customer_id else None
            
            # Compose message
            category = state.get_category(category_slug)
            res = engine.compose(category, merchant, trigger, customer)
            
            # Action schema
            action = {
                "type": "engage",
                "merchant_id": mid,
                "trigger_id": tid,
                "body": res.get("body"),
                "message": res.get("body"), 
                "cta": res.get("cta"),
                "send_as": res.get("send_as", "vera"),
                "suppression_key": res.get("suppression_key"),
                "rationale": res.get("rationale")
            }
            actions.append(action)
            
        return {"actions": actions}
    except Exception as e:
        return {"actions": []}

def safe_str(x):
    return str(x) if x is not None else ""

@app.post("/v1/reply")
async def handle_reply(request: Request):
    try:
        body = await request.json()
        mid = body.get("merchant_id", "m_unknown")
        conv_id = body.get("conversation_id", "c_unknown")

        # -----------------------------
        # ROBUST TEXT EXTRACTION
        # -----------------------------
        raw_msg = body.get("message")
        if isinstance(raw_msg, dict):
            raw_msg = raw_msg.get("text", "")

        text = (
            str(raw_msg or "")
            + " "
            + str(body.get("reply") or "")
            + " "
            + str(body.get("text") or "")
        ).lower().strip()

        # Record message for auto-reply detection
        state.record_message(mid, conv_id, text)

        # -----------------------------
        # SAFETY / EMPTY CHECK
        # -----------------------------
        if not text:
            return {"action": "end"}

        # -----------------------------
        # AUTO-REPLY DETECTION (WAIT THEN END)
        # -----------------------------
        auto_reply_keywords = [
            "busy", "meeting", "out of office", "away",
            "call you later", "driving", "will get back",
            "unavailable", "not available", "later",
            "auto", "automatic", "respond later",
            "cant talk", "cannot talk", "right now",
            "in a call", "occupied", "shortly",
            "contacting us", "team will", "automated assistant"
        ]

        is_keyword_match = any(k in text for k in auto_reply_keywords)
        streak = state.get_auto_reply_streak(mid, text)

        if is_keyword_match or state.is_auto_reply(mid, text):
            if streak >= 2:
                return {"action": "end"}
            else:
                return {"action": "wait", "wait_seconds": 60}

        # -----------------------------
        # HOSTILE
        # -----------------------------
        if any(k in text for k in [
            "stop", "spam", "useless", "not interested",
            "don't message", "leave me"
        ]):
            return {"action": "end"}

        # -----------------------------
        # POSITIVE INTENT
        # -----------------------------
        if any(k in text for k in [
            "ok", "yes", "do it", "go ahead", "lets do it", "proceed", "agree"
        ]):
            msg = safe_str("Great — I’ll set this up. I am proceeding with the confirmed update for your business now.")
            return {
                "action": "send",
                "body": msg,
                "message": msg,
                "cta": "Confirm",
                "send_as": "assistant",
                "suppression_key": "confirm_campaign",
                "rationale": "Merchant intent detected → moving to execution step"
            }

        # -----------------------------
        # ECHOING FALLBACK
        # -----------------------------
        echo_word = ""
        # Technical or specific words are better
        words = [w.strip("?,.!") for w in text.split()]
        specific_words = [w for w in words if len(w) > 3 and w not in auto_reply_keywords and w not in [
            "hello", "there", "please", "thanks", "thank", " Vera", "vera", "assistant"
        ]]
        
        if specific_words:
            # Try to find a very specific word (e.g. capitalized in original, or long)
            echo_word = max(specific_words, key=len)
        
        if echo_word:
            fallback_msg = safe_str(f"I understand your interest in {echo_word}. Let me refine this recommendation based on your business profile.")
        else:
            fallback_msg = safe_str("Let me refine this recommendation based on your business profile.")

        return {
            "action": "send",
            "body": fallback_msg,
            "message": fallback_msg,
            "cta": "See Details",
            "send_as": "assistant",
            "suppression_key": "refine",
            "rationale": "Context-aware fallback response"
        }

    except Exception as e:
        # ABSOLUTE SAFETY NET
        return {"action": "end"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=port)
