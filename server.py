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

class TickRequest(BaseModel):
    available_triggers: List[str]

class ReplyRequest(BaseModel):
    merchant_id: str
    message: str
    context_id: Optional[str] = None

@app.get("/v1/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/v1/metadata")
async def metadata():
    return {
        "name": "Vera AI Deterministic Engine",
        "version": os.getenv("VERSION", "2.2.0"),
        "team": os.getenv("TEAM_NAME", "Antigravity")
    }

@app.post("/v1/context")
async def push_context(data: ContextPayload):
    try:
        updated = state.upsert_context(data.scope, data.context_id, data.payload, data.version)
        return {"accepted": True, "updated": updated}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/v1/tick")
async def tick(data: TickRequest):
    actions = []
    threshold = 50.0 # Default threshold for gap_score
    try:
        for tid in data.available_triggers:
            trigger = state.get_trigger(tid)
            if not trigger: continue
            
            t_payload = trigger.get("payload", {})
            mid = t_payload.get("merchant_id")
            if not mid: continue
            
            merchant = state.get_merchant(mid)
            if not merchant: continue
            
            # GAP ANALYSIS Check
            demand = t_payload.get("search_count", 0)
            conversion = merchant.get("performance", {}).get("conversion_rate", 0.05)
            gap_score = demand * (1 - conversion)
            
            if gap_score < threshold:
                continue # Opportunity too small
            
            cat_slug = merchant.get("category_slug", "default")
            customer = None # In a real scenario, we'd lookup customer context if present
            
            composition = engine.compose(cat_slug, merchant, trigger, customer)
            
            # Suppression Logic
            supp_key = composition["suppression_key"]
            if state.is_suppressed(mid, supp_key):
                actions.append({
                    "trigger_id": tid,
                    "action": "suppress"
                })
                continue
            
            state.update_suppression(mid, supp_key)
            actions.append({
                "trigger_id": tid,
                **composition
            })
            
        return {"actions": actions}
    except Exception as e:
        print(f"Tick error: {e}")
        return {"actions": []}

@app.post("/v1/reply")
async def handle_reply(data: ReplyRequest):
    try:
        msg_lower = data.message.lower()
        
        # 1. STOP Logic
        stop_words = ["stop", "not interested", "later", "busy", "out of office"]
        if any(word in msg_lower for word in stop_words):
            return {"action": "end"}
        
        # 2. Decision logic for positive/neutral replies
        merchant = state.get_merchant(data.merchant_id)
        if not merchant: return {"action": "end"}
            
        # Recompute best strategy
        cat_slug = merchant.get("category_slug", "default")
        # Mocking a trigger for the reply context
        mock_trigger = {"kind": "reply_engagement", "payload": {"search_count": 100, "keyword": cat_slug}}
        
        composition = engine.compose(cat_slug, merchant, mock_trigger)
        
        # If it's a strongly positive reply, we could "confirm"
        if any(w in msg_lower for w in ["yes", "ok", "sure", "proceed", "run"]):
            return {
                "action": "send",
                "message": f"Great! I'm launching the {composition['message'].split(' can ')[0]} campaign now. You'll see updates on your dashboard.",
                "cta": "View Dashboard",
                "rationale": "Merchant confirmed action. Initializing campaign sequence."
            }
        
        # Otherwise re-engage with next best action
        return {
            "action": "send",
            "message": f"I understand. We're seeing high local demand ({mock_trigger['payload']['search_count']} searches). Would you like to {composition['message'].split(' capture ')[1]}",
            "cta": composition["cta"],
            "rationale": "Re-evaluating based on merchant engagement. Emphasizing demand specificity."
        }
        
    except Exception as e:
        return {"action": "end", "rationale": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=port)
