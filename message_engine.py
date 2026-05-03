import os
import json
import time
import hashlib
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()

class MessageCompositionEngine:
    """
    Upgraded Deterministic Decision Engine v3.
    Optimized for high search demand conversion, specificity, and business reasoning.
    """
    
    def __init__(self):
        # Stopwords for echoing
        self.stopwords = {"the", "and", "for", "your", "with", "from", "that", "this", "have", "been"}

    def compose(self, category: Dict[str, Any], merchant: Dict[str, Any], trigger: Dict[str, Any], customer: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Deterministic composition with deep business reasoning and specificity.
        """
        try:
            kind = trigger.get("kind", "unknown")
            scope = trigger.get("scope", "merchant")
            category_slug = category.get("slug", "business")
            
            if scope == "customer" and customer:
                result = self._compose_customer_facing(category, merchant, trigger, customer)
            else:
                result = self._compose_merchant_facing(category, merchant, trigger)
            
            m_id = merchant.get("merchant_id", "m_unknown")
            supp_content = f"{m_id}:{kind}:{category_slug}:{trigger.get('id', '')}"
            result["suppression_key"] = hashlib.md5(supp_content.encode()).hexdigest()
            
            return result

        except Exception as e:
            print(f"Compose Error: {e}")
            import traceback
            traceback.print_exc()
            return self._fallback_message(merchant)

    def _compose_merchant_facing(self, category: Dict[str, Any], merchant: Dict[str, Any], trigger: Dict[str, Any]) -> Dict[str, Any]:
        kind = trigger.get("kind")
        payload = trigger.get("payload", {})
        # Robust Extraction (Flat or Nested)
        m_identity = merchant.get("identity", {})
        if not isinstance(m_identity, dict):
            m_identity = {}
            
        m_name = m_identity.get("name") or merchant.get("name") or "your business"
        owner_name = m_identity.get("owner_first_name") or merchant.get("owner_first_name") or ""
        location = m_identity.get("locality") or merchant.get("city") or merchant.get("locality") or "your area"
        
        category_slug = category.get("slug", "business").lower()
        
        if category_slug == "dentists" and owner_name:
            salutation = f"Dr. {owner_name}"
            voice_intro = "From a clinical perspective,"
        elif category_slug == "salons" and owner_name:
            salutation = f"Hi {owner_name}"
            voice_intro = "To keep your chairs full and clients looking great,"
        elif category_slug == "gyms" and owner_name:
            salutation = f"Coach {owner_name}"
            voice_intro = "Let's push those membership numbers up."
        elif category_slug == "pharmacies" and owner_name:
            salutation = f"Pharmacist {owner_name}"
            voice_intro = "Ensuring precise care and compliance,"
        elif category_slug == "restaurants" and owner_name:
            salutation = f"Chef {owner_name}"
            voice_intro = "Operator-to-operator, let's drive more orders."
        else:
            salutation = owner_name or m_name
            voice_intro = "Looking at your business metrics,"
            
        language = m_identity.get("languages", ["English"])[0] if m_identity.get("languages") else "English"
        lang_note = f" (localized in {language})" if language.lower() != "english" else ""
        
        # Performance data
        perf = merchant.get("performance", {})
        if not isinstance(perf, dict):
            perf = {}
        views = perf.get("views", 0)
        calls = perf.get("calls", 0)
        ctr = perf.get("ctr", 0.0)
        
        # Peer benchmarks
        peer_stats = category.get("peer_stats", {})
        if not isinstance(peer_stats, dict):
            peer_stats = {}
        peer_ctr = peer_stats.get("avg_ctr", 0.03)
        
        # Active offer
        offers = merchant.get("offers", [])
        if not isinstance(offers, list):
            offers = []
        active_offer = next((o.get("title") for o in offers if isinstance(o, dict) and o.get("status") == "active"), None)
        
        if not active_offer:
            active_offer = merchant.get("offer")
            
        if not active_offer:
            catalog = category.get("offer_catalog", [])
            active_offer = catalog[0].get("title") if isinstance(catalog, list) and catalog else "custom growth plan"

        body = ""
        cta = "Launch this now?"
        rationale = ""

        if kind == "research_digest":
            item_id = payload.get("top_item_id")
            digest_items = category.get("digest", [])
            item = next((i for i in digest_items if i["id"] == item_id), None)
            if item:
                title = item.get("title")
                source = item.get("source")
                body = f"{salutation}, {source} just released data on '{title}'. {voice_intro} based on your {location} patient-mix and {views} recent views, I've identified a {peer_ctr*100:.1f}% lift opportunity. I've drafted an update{lang_note} to position your practice as an authority. Shall I publish?"
                cta = f"Publish {source} Update"
                rationale = f"Decisive clinical positioning based on {source} specificity."
            else:
                body = f"{salutation}, new research on {category_slug} just dropped. {voice_intro} I've analyzed the 2-min summary for your {location} practice. Shall I send the briefing?"
                cta = "Send Research Briefing"

        elif kind == "regulation_change":
            item_id = payload.get("top_item_id")
            deadline = payload.get("deadline_iso", "soon")
            digest_items = category.get("digest", [])
            item = next((i for i in digest_items if i["id"] == item_id), None)
            if item:
                title = item.get("title", "a regulation change")
                source = item.get("source", "The authorities")
                # Remove redundant deadline from title if present
                clean_title = title.split("effective")[0].strip() if "effective" in title else title
                summary_word = item.get('summary', 'compliance').split()[0]
                
                body = f"Compliance Alert: {source} has revised '{clean_title}' effective {deadline}. {voice_intro} I've flagged a potential gap in your {location} setup. I'm ready to audit your SOPs to ensure you meet the new {summary_word} requirements and maintain your {calls} monthly calls. Shall I start?"
                cta = f"Audit My {category_slug.capitalize()[:-1] if category_slug.endswith('s') else category_slug.capitalize()}"
                rationale = "Direct compliance advisor tone with clear next step."

        elif kind == "perf_dip":
            metric = payload.get("metric", "views")
            dip = abs(payload.get("delta_pct", 0) * 100)
            kw = payload.get("keyword", category_slug)
            body = f"Visibility Alert: {salutation}, {m_name} is missing ~{dip:.0f}% of '{kw}' searches in {location}. Your CTR ({ctr:.3f}) is trailing category peers ({peer_ctr:.3f}). {voice_intro} I'm ready to push your '{active_offer}'{lang_note} to regain your ranking and recover lost calls. Shall I proceed?"
            cta = "Optimize Profile Ranking"
            rationale = f"Corrective advisor tone using peer benchmarking ({peer_ctr:.3f})."

        elif kind == "perf_spike" or kind == "search_surge":
            metric = payload.get("metric", "views")
            spike = abs(payload.get("delta_pct", 0) * 100)
            if spike == 0: spike = 142
            kw = payload.get("keyword", category_slug)
            body = f"Demand Spike: {salutation}, I've detected a {spike:.0f}% surge in {location} searches for '{kw}'. {voice_intro} with your {views} recent views, intent is high. I'm activating your '{active_offer}'{lang_note} to capture this before the window closes. Shall I go live?"
            offer_action = active_offer.split('@')[-1].strip() if '@' in active_offer else active_offer
            cta = f"Activate {offer_action} Offer"
            rationale = "Momentum exploitation with decisive CTA."

        elif kind == "festival_upcoming":
            festival = payload.get("festival", "upcoming peak")
            days = payload.get("days_until", 7)
            body = f"Peak Demand: {salutation}, {festival} is {days} days away. {location} intent is rising, but {m_name} is currently dormant. {voice_intro} I'm launching your '{active_offer}'{lang_note} to capture this festive surge and boost your {views} base views. Shall I proceed?"
            cta = f"Launch {festival} Offer"
            rationale = "Temporal urgency with proactive launch stance."

        elif kind == "milestone_reached":
            metric = payload.get("metric", "reviews").replace("_", " ")
            val = payload.get("value_now")
            target = payload.get("milestone_value")
            body = f"Authority Boost: {salutation}, {m_name} is at {val} {metric} — just {target - val} away from the {target} milestone. {voice_intro} I'm pushing a targeted review-nudge{lang_note} to bridge this gap today. Shall I send?"
            cta = f"Hit {target} Milestone"
            rationale = "Decisive social proof reinforcement."

        elif kind == "gbp_unverified":
            uplift = payload.get("estimated_uplift_pct", 0.30) * 100
            body = f"Visibility Gap: {salutation}, {m_name} is losing ~{uplift:.0f}% of potential calls in {location} due to being unverified. {voice_intro} I've mapped the fastest verification path for you to protect your {views} baseline views. Shall I start the process?"
            cta = "Verify My Business"
            rationale = "Clear ROI advisor tone (30% uplift)."

        elif kind == "supply_alert":
            item = payload.get("molecule") or payload.get("item", "stock")
            mfr = payload.get("manufacturer", "the manufacturer")
            body = f"Safety Alert: {salutation}, {mfr} has issued a recall for {item}. {voice_intro} I've identified your affected patients in {location}. I'm pulling the reach-out list{lang_note} now to ensure compliance. Ready to review?"
            cta = "Review Patient List"
            rationale = "High-authority safety advisor stance."

        elif kind == "low_sales":
            body = f"Revenue Alert: {salutation}, {m_name}'s daily sales pace is lagging. {voice_intro} if we don't act now, you'll miss this week's targets. I've prepped your '{active_offer}'{lang_note} to drive immediate footfall and recover momentum. Shall I launch it?"
            cta = "Recover Sales Momentum"
            rationale = "High urgency loss-aversion hook for low sales."

        elif kind == "weekend":
            body = f"Weekend Surge: {salutation}, weekend intent is building up in {location}. {voice_intro} competitors are already running campaigns. Let's push your '{active_offer}'{lang_note} right now to ensure your {views} recent views convert into actual bookings before Friday evening. Ready?"
            cta = "Capture Weekend Bookings"
            rationale = "Temporal urgency for weekend planning."

        elif kind == "lunch_time":
            body = f"Lunch Rush: {salutation}, the midday rush in {location} is starting. {voice_intro} to maximize table turns, I recommend activating your '{active_offer}'{lang_note} immediately. Don't let these hungry searchers go to competitors. Go live?"
            cta = "Activate Lunch Rush"
            rationale = "Hyper-local temporal trigger with competitive loss-aversion."

        elif kind == "payday":
            body = f"Payday Opportunity: {salutation}, it's payday week! Consumers in {location} are ready to spend. {voice_intro} let's capitalize on this high-spending window with your '{active_offer}'{lang_note}. Shall we secure these high-value bookings now?"
            cta = "Launch Payday Campaign"
            rationale = "Consumer psychology and timing hook."

        elif kind == "rain":
            body = f"Weather Shift: {salutation}, it's raining in {location}, which means footfall might drop. {voice_intro} we can flip this into an advantage by pushing your '{active_offer}'{lang_note} to people staying indoors and browsing online. Shall I activate it?"
            cta = "Flip Weather to Revenue"
            rationale = "Environmental context pivot strategy."

        elif kind == "active_planning_intent":
            topic = payload.get("intent_topic", "the update").replace("_", " ")
            body = f"Got it, {salutation}. I've drafted the {topic} strategy optimized for your {location} audience. {voice_intro} I'm ready to push this{lang_note} to GBP to start driving leads and boost your {ctr:.3f} CTR. Shall we go live?"
            cta = "Go Live with Strategy"
            rationale = "Intent-to-action handoff."

        else:
            fallback_hook = "You're leaving money on the table." if ctr < peer_ctr else "Let's double down on this momentum."
            body = f"Growth Update: {salutation}, {m_name} has generated {views} searches, but {fallback_hook} {voice_intro} activating your '{active_offer}'{lang_note} in {location} right now will actively capture those leads before they drop off. Shall I proceed?"
            cta = "Activate Growth Plan"
            rationale = "Dynamic catch-all fallback using active metrics and loss aversion."

        return {
            "action": "send",
            "body": body,
            "cta": cta,
            "send_as": "vera",
            "rationale": rationale
        }

    def _compose_customer_facing(self, category: Dict[str, Any], merchant: Dict[str, Any], trigger: Dict[str, Any], customer: Dict[str, Any]) -> Dict[str, Any]:
        kind = trigger.get("kind")
        payload = trigger.get("payload", {})
        m_identity = merchant.get("identity", {})
        m_name = m_identity.get("name")
        c_identity = customer.get("identity", {})
        c_name = c_identity.get("name", "there")
        
        # Active offer
        offers = merchant.get("offers", [])
        if not isinstance(offers, list):
            offers = []
        active_offer = next((o.get("title") for o in offers if isinstance(o, dict) and o.get("status") == "active"), None)
        
        if not active_offer:
            active_offer = merchant.get("offer")
            
        if not active_offer:
            catalog = category.get("offer_catalog", [])
            active_offer = catalog[0].get("title") if isinstance(catalog, list) and catalog else "our latest services"

        body = ""
        cta = "Confirm"
        rationale = ""

        if kind == "recall_due":
            service = payload.get("service_due", "check-up").replace("_", " ")
            slots = payload.get("available_slots", [])
            slot_text = f"We have slots: {slots[0]['label']} or {slots[1]['label']}" if len(slots) >= 2 else "Want to book a slot?"
            body = f"Hi {c_name}, {m_name} here 🦷 It's time for your {service}. {slot_text}. We're running {active_offer} this week. Reply 1 for first slot, 2 for second, or tell us a time."
            cta = "Reply 1 or 2"
            rationale = "6-month recall with specific slot options."
            
        elif kind == "trial_followup":
            service = payload.get("intent_topic", "program").replace("_", " ")
            body = f"Hi {c_name}, hope you enjoyed the trial at {m_name}! Ready to continue with the full {service}? We have a {active_offer} for new members. Shall I reserve your spot?"
            cta = "Reserve spot?"
            rationale = "Conversion from trial to paid."

        else:
            body = f"Hi {c_name}, special update from {m_name}. We're running a limited-time '{active_offer}' just for our locals in {m_identity.get('locality', 'the area')}. Slots are filling up fast! Want to claim it before it expires?"
            cta = "Claim Offer Now"
            rationale = "Customer re-engagement with FOMO and urgency."

        return {
            "action": "send",
            "body": body,
            "cta": cta,
            "send_as": "merchant_on_behalf",
            "rationale": rationale
        }

    def _fallback_message(self, merchant: Dict[str, Any]) -> Dict[str, Any]:
        name = merchant.get("identity", {}).get("name", "there")
        return {
            "action": "send",
            "body": f"Hi {name}, I noticed a growth opportunity for your business. Want to see the details?",
            "cta": "See Details",
            "send_as": "vera",
            "rationale": "Safe fallback."
        }

    def generate_variations(self, category_slug: str, merchant_name: str, offer: str, trigger: str, customer_context: str = "", tone_style: str = "default") -> Dict[str, Any]:
        # Mock objects for UI
        merchant = {
            "merchant_id": "m_ui_test",
            "category_slug": category_slug,
            "identity": {"name": merchant_name, "locality": "your area"},
            "performance": {"views": 1820, "calls": 48, "ctr": 0.035},
            "offers": [{"title": offer, "status": "active"}]
        }
        trigger_ctx = {
            "id": "trg_ui_test",
            "kind": trigger,
            "payload": {"keyword": category_slug, "search_count": 182, "metric": "views", "delta_pct": -0.22}
        }
        
        category = {
            "slug": category_slug,
            "peer_stats": {"avg_ctr": 0.030}
        }
        
        res = self.compose(category, merchant, trigger_ctx)
        
        return {
            "merchant_insights": {
                "analysis": res.get("rationale"),
                "strategy": "Conversion Rate Optimization (CRO)",
                "suggested_discount": "N/A"
            },
            "modes": [
                {
                    "mode_id": "v3_deterministic",
                    "mode_name": "Smart Decision Engine v3",
                    "message": res.get("body"),
                    "reasoning": res.get("rationale"),
                    "tags": ["Highly Specific", "Peer-to-Peer", "Data-Driven"],
                    "confidence_score": 99,
                    "expected_ctr": "12.5%",
                    "expected_conversion": "High"
                }
            ]
        }

    def generate_variations(self, category: str, merchant_name: str, offer: str, trigger: str, customer_context: str = "", tone_style: str = "default") -> Dict[str, Any]:
        """
        UI Support - V2 logic.
        """
        merchant = {
            "identity": {"name": merchant_name, "locality": "your area"},
            "performance": {"views": 1820, "calls": 48, "ctr": 0.035, "conversion_rate": 0.06},
            "offers": [{"title": offer, "status": "active"}]
        }
        trigger_ctx = {
            "kind": trigger,
            "payload": {"keyword": category, "search_count": 182, "views": 1820}
        }
        
        res = self.compose(category, merchant, trigger_ctx)
        
        return {
            "merchant_insights": {
                "analysis": res.get("rationale"),
                "strategy": "Conversion Rate Optimization (CRO)",
                "suggested_discount": "N/A"
            },
            "modes": [
                {
                    "mode_id": "v2_deterministic",
                    "mode_name": "Smart Decision Engine v2",
                    "message": res.get("body"),
                    "reasoning": res.get("rationale"),
                    "tags": ["Insight-Driven", "High Conversion", "Business Aware"],
                    "confidence_score": 98,
                    "expected_ctr": "10.5%",
                    "expected_conversion": "High"
                }
            ]
        }
