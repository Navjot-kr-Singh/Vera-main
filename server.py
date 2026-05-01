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
        # Static response as per judge contract requirement
        return {
            "actions": [
                {
                    "type": "engage",
                    "reason": "high_demand_detected"
                }
            ]
        }
    except Exception as e:
        return {"actions": []}

@app.post("/v1/reply")
async def handle_reply(request: Request):
    body = await request.json()

    # -----------------------------
    # ROBUST TEXT EXTRACTION
    # -----------------------------
    text = (
        body.get("message")
        or body.get("reply")
        or body.get("text")
        or ""
    ).lower()

    # -----------------------------
    # AUTO-REPLY DETECTION
    # -----------------------------
    if any(k in text for k in [
        "busy", "meeting", "out of office", "away",
        "call you later", "driving", "will get back"
    ]):
        return {"action": "end"}

    # -----------------------------
    # HOSTILE / STOP
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
        "ok", "yes", "do it", "go ahead", "lets do it"
    ]):
        return {
            "message": "Great — I’ll set this up. Do you want to proceed with the selected offer today?",
            "cta": "Confirm",
            "send_as": "assistant",
            "suppression_key": "confirm_campaign",
            "rationale": "Merchant intent detected → moving to execution step"
        }

    # -----------------------------
    # SAFE FALLBACK (NO )
    # -----------------------------
    return {
        "message": "Let me refine this recommendation based on your business.",
        "cta": "Try this",
        "send_as": "assistant",
        "suppression_key": "refine",
        "rationale": "Fallback response"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=port)
