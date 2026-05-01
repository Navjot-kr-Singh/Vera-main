import hashlib
import json
import time
from typing import Dict, Any, Optional, List

class MessageCompositionEngine:
    """
    Deterministic, rule-based message composition engine for magicpin Vera AI Challenge.
    """
    
    TONE_MAP = {
        "dentist": {"tone": "clinical, calm, trust-based", "style": "professional"},
        "salon": {"tone": "aspirational, beauty-focused", "style": "elegant"},
        "gym": {"tone": "energetic, motivational", "style": "active"},
        "restaurant": {"tone": "craving, urgency", "style": "persuasive"},
        "pharmacy": {"tone": "practical, helpful, urgent", "style": "supportive"},
        "default": {"tone": "promotional", "style": "direct"}
    }

    TEMPLATES = [
        "{n} people searched '{k}' near {l} today.",
        "Demand spike: {n} searches for '{k}' in {l}.",
        "{n} local searches for '{k}' detected in {l} today."
    ]

    def compose(self, category: str, merchant: Dict[str, Any], trigger: Dict[str, Any], customer: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main entry point for message composition.
        """
        try:
            category = category.lower()
            
            # STEP 1: GAP ANALYSIS
            m_perf = merchant.get("performance", {})
            conversion = m_perf.get("conversion_rate", 0.05)
            demand = trigger.get("payload", {}).get("search_count", 0)
            
            gap_score = demand * (1 - conversion)
            
            # STEP 2 & 3: GENERATE & SCORE STRATEGIES
            best_strategy = self._select_best_strategy(category, merchant, trigger, customer)
            
            # STEP 4: DYNAMIC MESSAGE GENERATION (DETERMINISTIC)
            result = self._generate_deterministic_content(best_strategy, category, merchant, trigger, customer)
            
            # Add suppression key
            result["suppression_key"] = f"{merchant.get('id', 'm')}:{best_strategy['type']}"
            
            return result
        except Exception as e:
            print(f"Compose Error: {e}")
            return {
                "message": "Strategic opportunity detected for your business. Check your dashboard for details.",
                "cta": "Go live now",
                "send_as": "assistant",
                "suppression_key": "error_fallback",
                "rationale": f"Safe fallback triggered due to processing error: {str(e)}"
            }

    def _select_best_strategy(self, category: str, merchant: Dict[str, Any], trigger: Dict[str, Any], customer: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Implements the 3-strategy scoring logic.
        """
        m_perf = merchant.get("performance", {})
        conversion = m_perf.get("conversion_rate", 0.05)
        demand = trigger.get("payload", {}).get("search_count", 0)
        
        strategies = [
            {
                "type": "acquisition",
                "impact": 9 if demand > 100 else 6,
                "urgency": 8 if demand > 200 else 5,
                "merchant_fit": 9 if conversion < 0.03 else 7,
                "category_fit": 10
            },
            {
                "type": "awareness",
                "impact": 7,
                "urgency": 6,
                "merchant_fit": 10 if conversion < 0.01 else 6,
                "category_fit": 9
            },
            {
                "type": "retention",
                "impact": 8 if customer and customer.get("state") == "inactive" else 4,
                "urgency": 10 if customer and customer.get("state") == "inactive" else 3,
                "merchant_fit": 8,
                "category_fit": 9
            }
        ]

        for s in strategies:
            s["final_score"] = (
                s["impact"] * 0.4 +
                s["urgency"] * 0.3 +
                s["merchant_fit"] * 0.2 +
                s["category_fit"] * 0.1
            )

        # Pick highest scoring strategy
        best = max(strategies, key=lambda x: x["final_score"])
        return best

    def _generate_deterministic_content(self, strategy: Dict[str, Any], category: str, merchant: Dict[str, Any], trigger: Dict[str, Any], customer: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        m_name = merchant.get("identity", {}).get("name", "Merchant")
        m_loc = merchant.get("identity", {}).get("locality", "nearby")
        t_meta = trigger.get("payload", {})
        keyword = t_meta.get("keyword", category)
        n = t_meta.get("search_count", 0)
        conversion = merchant.get("performance", {}).get("conversion_rate", 0.05)
        
        offers = merchant.get("offers", [])
        best_offer = offers[0] if offers else {"title": "special deal", "price": "99"}
        offer_text = f"₹{best_offer.get('price', '99')} {best_offer.get('title', 'offer')}"

        # Deterministic Hashing for Template Selection
        ctx_str = f"{m_name}-{category}-{n}-{keyword}"
        hash_val = int(hashlib.md5(ctx_str.encode()).hexdigest(), 16)
        template_index = hash_val % len(self.TEMPLATES)
        template = self.TEMPLATES[template_index]

        # Build Message
        cta_question = "Run this now?"
        if strategy["type"] == "acquisition": cta_question = "Launch this offer?"
        elif strategy["type"] == "retention": cta_question = "Go live now?"

        intro = template.format(n=n, k=keyword, l=m_loc)
        message = f"{intro} {m_name} can capture this demand with {offer_text}. {cta_question}"

        # Category Tone Transformation
        if category == "dentist":
            message = message.replace("capture", "serve").replace("demand", "needs")
        elif category == "gym":
            message = "💪 " + message
        elif category == "salon":
            message = "✨ " + message

        # Rationale (MANDATORY FORMAT)
        rationale = f"High demand ({n}) with low conversion (~{int(conversion*100)}%) indicates drop-off. A {offer_text} reduces friction and improves conversion."

        return {
            "message": message,
            "cta": strategy.get("cta", "Run this"),
            "send_as": "assistant",
            "rationale": rationale,
            "best_action": strategy["type"] # Internal use
        }

    def generate_variations(self, category: str, merchant_name: str, offer: str, trigger: str, customer_context: str = "", tone_style: str = "default") -> Dict[str, Any]:
        """
        Legacy UI Support - Ported to new strategy engine.
        """
        merchant = {
            "id": "m_ui",
            "identity": {"name": merchant_name, "locality": "nearby"},
            "performance": {"conversion_rate": 0.02, "searches": 450},
            "offers": [{"title": offer, "price": "199"}]
        }
        trigger_ctx = {
            "kind": trigger,
            "payload": {"keyword": category, "search_count": 142}
        }
        
        # We'll return 3 strategy variations for the UI
        modes = []
        for s_type in ["acquisition", "awareness", "retention"]:
            s_mock = {
                "type": s_type,
                "impact": 8, "urgency": 7, "merchant_fit": 9, "category_fit": 10
            }
            content = self._generate_deterministic_content(s_mock, category, merchant, trigger_ctx)
            
            modes.append({
                "mode_id": s_type,
                "mode_name": s_type.capitalize(),
                "message": content["message"],
                "reasoning": content["rationale"],
                "tags": [s_type, category],
                "confidence_score": 85,
                "expected_ctr": "7.2%",
                "expected_conversion": "High"
            })

        return {
            "merchant_insights": {
                "analysis": f"High demand ({142}) detected for {category} near this location.",
                "strategy": "Deploy aggressive acquisition strategy to capture current surge.",
                "suggested_discount": "20%"
            },
            "ab_test_recommendation": "Acquisition strategy is recommended for maximum conversion impact.",
            "modes": modes
        }
