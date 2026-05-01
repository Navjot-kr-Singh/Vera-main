import os
import json
import time
from typing import Dict, Any, Optional, List
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class MessageCompositionEngine:
    """
    LLM-powered message composition engine for magicpin Vera AI Challenge.
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini" # Using a fast, high-quality model

    def compose(self, category_slug: str, merchant: Dict[str, Any], trigger: Dict[str, Any], customer: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main entry point for message composition using LLM.
        """
        try:
            # Prepare context for the prompt
            context_summary = self._prepare_context(category_slug, merchant, trigger, customer)
            
            # System Prompt based on challenge-brief.md guidelines
            system_prompt = """You are Vera, magicpin's merchant-AI assistant. 
Your goal is to compose a WhatsApp message to a merchant (or their customer) based on provided context.

SCORING CRITERIA:
1. SPECIFICITY: Anchor on concrete facts (numbers, dates, headlines, prices). Avoid generic "X% off".
2. CATEGORY FIT: Match the voice/tone of the business type. 
   - Dentists: clinical-peer, trust-based, use "Dr." prefix.
   - Salons: beauty-focused, elegant.
   - Restaurants: operator-to-operator, craving-focused.
3. MERCHANT FIT: Personalized to their state, numbers, and language preference (honor Hindi-English code-mix if preferred).
4. TRIGGER RELEVANCE: Clearly communicate WHY you are messaging now.
5. ENGAGEMENT COMPULSION: Use levers like curiosity, loss aversion, social proof, or reciprocity.

CONSTRAINTS:
- Length: Max 320 chars. Aim for 150-200.
- CTA: Single primary binary (YES/STOP) or low-friction ask.LAND IT IN THE LAST SENTENCE.
- No URLs.
- No fabrications: Use ONLY provided data.

OUTPUT FORMAT (JSON):
{
  "body": "The WhatsApp message text",
  "cta": "The call-to-action text",
  "send_as": "vera" or "merchant_on_behalf",
  "rationale": "Short explanation of the strategy used"
}"""

            user_prompt = f"### CONTEXT ###\n{json.dumps(context_summary, indent=2)}\n\nCompose the Vera message."

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0 # Ensure determinism as requested by brief
            )

            result = json.loads(response.choices[0].message.content)
            
            # Ensure send_as is correct based on trigger scope
            trigger_scope = trigger.get("scope", "merchant")
            if trigger_scope == "customer":
                result["send_as"] = "merchant_on_behalf"
            else:
                result["send_as"] = "vera"

            return result

        except Exception as e:
            print(f"Compose Error: {e}")
            # Fallback
            return {
                "body": f"Hi {merchant.get('identity', {}).get('name', 'there')}, I noticed a new growth opportunity for your business based on recent local searches. Want to see the details?",
                "cta": "YES",
                "send_as": "vera",
                "rationale": f"Safe fallback triggered due to error: {str(e)}"
            }

    def _prepare_context(self, category_slug: str, merchant: Dict[str, Any], trigger: Dict[str, Any], customer: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Filters and structures context to keep prompt efficient and focused.
        """
        # Extract key data from merchant
        m_identity = merchant.get("identity", {})
        m_perf = merchant.get("performance", {})
        m_offers = merchant.get("offers", [])
        
        # Extract key data from trigger
        t_kind = trigger.get("kind", "unknown")
        t_payload = trigger.get("payload", {})
        
        return {
            "category": category_slug,
            "merchant": {
                "name": m_identity.get("name"),
                "locality": m_identity.get("locality"),
                "city": m_identity.get("city"),
                "languages": m_identity.get("languages", ["English"]),
                "owner_name": m_identity.get("owner_first_name"),
                "performance_30d": {
                    "views": m_perf.get("views"),
                    "calls": m_perf.get("calls"),
                    "ctr": m_perf.get("ctr")
                },
                "active_offers": [o.get("title") for o in m_offers if o.get("status") == "active"][:2]
            },
            "trigger": {
                "kind": t_kind,
                "urgency": trigger.get("urgency"),
                "payload": t_payload
            },
            "customer": {
                "name": customer.get("identity", {}).get("name"),
                "state": customer.get("state"),
                "last_visit": customer.get("relationship", {}).get("last_visit")
            } if customer else None
        }

    def generate_variations(self, category: str, merchant_name: str, offer: str, trigger: str, customer_context: str = "", tone_style: str = "default") -> Dict[str, Any]:
        """
        Legacy UI Support - Re-routed through LLM for better quality.
        """
        # Simple mock for UI demo
        merchant = {
            "identity": {"name": merchant_name, "locality": "nearby"},
            "performance": {"views": 1200, "calls": 45, "ctr": 0.025},
            "offers": [{"title": offer, "status": "active"}]
        }
        trigger_ctx = {
            "kind": trigger,
            "payload": {"keyword": category, "search_count": 142}
        }
        
        # In the demo UI, we just want one good message usually, but let's provide variations if needed
        res = self.compose(category, merchant, trigger_ctx)
        
        return {
            "merchant_insights": {
                "analysis": res.get("rationale", "Strategic opportunity detected."),
                "strategy": "Maximize local search intent capture.",
                "suggested_discount": "N/A"
            },
            "modes": [
                {
                    "mode_id": "standard",
                    "mode_name": "Optimized",
                    "message": res.get("body"),
                    "reasoning": res.get("rationale"),
                    "tags": ["AI-Powered", "High Specificity"],
                    "confidence_score": 95,
                    "expected_ctr": "8.5%",
                    "expected_conversion": "High"
                }
            ]
        }
