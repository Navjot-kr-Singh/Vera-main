import os
import json
import time
import hashlib
import re
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from dataclasses import dataclass, field

load_dotenv()

@dataclass
class CategoryFeatures:
    """
    Holds normalized category settings and peer statistics.
    Excludes scoring or ranking. Preserves raw input in raw_data.
    """
    slug: str
    peer_avg_ctr: Optional[float]
    digest_items: List[Dict[str, Any]]
    offer_catalog: List[Dict[str, Any]]
    raw_data: Dict[str, Any]

@dataclass
class MerchantFeatures:
    """
    Normalized merchant indicators. Excludes business quality class or maturity label inference.
    Preserves active_offers list and raw input in raw_data.
    """
    merchant_id: str
    name: str
    owner_name: Optional[str]
    locality: Optional[str]
    rating: Optional[float]
    review_count: Optional[int]
    views: Optional[int]
    calls: Optional[int]
    directions: Optional[int]
    ctr: Optional[float]
    active_offers: List[Dict[str, Any]]
    languages_normalized: List[str]
    is_subscribed: Optional[bool]
    raw_data: Dict[str, Any]

@dataclass
class CustomerFeatures:
    """
    Normalized customer records. Excludes relationship status classification.
    Preserves raw input in raw_data.
    """
    customer_id: str
    name: str
    locality: Optional[str]
    due_service: Optional[str]
    available_slots: List[Dict[str, Any]]
    preferred_language: str
    raw_data: Dict[str, Any]

@dataclass
class TriggerFeatures:
    """
    Normalized triggers. Excludes urgency classification or priority rankers.
    Preserves raw input in raw_data.
    """
    trigger_id: str
    kind: str
    scope: str
    urgency: Optional[int]
    payload: Dict[str, Any]
    deadline: Optional[str]
    suppression_key: str
    raw_data: Dict[str, Any]

def safe_float(val: Any) -> Optional[float]:
    """Safely normalizes values to floats. Returns None on missing/malformed inputs."""
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).strip())
    except:
        return None

def safe_int(val: Any) -> Optional[int]:
    """Safely normalizes values to integers. Returns None on missing/malformed inputs."""
    if val is None or val == "":
        return None
    if isinstance(val, int):
        return val
    try:
        return int(str(val).strip())
    except:
        return None

def safe_bool(val: Any) -> Optional[bool]:
    """Safely normalizes values to booleans. Returns None on missing/malformed inputs."""
    if val is None or val == "":
        return None
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("true", "1", "yes", "y", "active"):
        return True
    if s in ("false", "0", "no", "n", "inactive"):
        return False
    return None

def normalize_language_str(lang: Any) -> str:
    """Standardizes language name strings into canonical lowercase format (hi, en, hi-en)."""
    if not isinstance(lang, str):
        return str(lang).strip().lower()
    l = lang.strip().lower()
    if "hinglish" in l or ("hindi" in l and "english" in l) or l == "hi-en":
        return "hi-en"
    if "hindi" in l or l == "hi":
        return "hi"
    if "english" in l or l == "en":
        return "en"
    return l

class FeatureExtractor:
    """
    Robust pure-normalization layer. Extracts contexts into normalized schemas
    while preserving original payloads verbatim.
    """
    @staticmethod
    def extract_category(category: Dict[str, Any]) -> CategoryFeatures:
        if not isinstance(category, dict):
            category = {}
        slug = category.get("slug", "business")
        peer_stats = category.get("peer_stats", {})
        peer_avg_ctr = safe_float(peer_stats.get("avg_ctr")) if isinstance(peer_stats, dict) else None
        digest = category.get("digest", [])
        catalog = category.get("offer_catalog", [])
        return CategoryFeatures(
            slug=slug,
            peer_avg_ctr=peer_avg_ctr,
            digest_items=digest if isinstance(digest, list) else [],
            offer_catalog=catalog if isinstance(catalog, list) else [],
            raw_data=category
        )

    @staticmethod
    def extract_merchant(merchant: Dict[str, Any], category: CategoryFeatures) -> MerchantFeatures:
        if not isinstance(merchant, dict):
            merchant = {}
        m_id = merchant.get("merchant_id", "m_unknown")
        identity = merchant.get("identity", {})
        if not isinstance(identity, dict):
            identity = {}
        name = identity.get("name") or merchant.get("name") or "your business"
        owner_name = identity.get("owner_first_name") or merchant.get("owner_first_name")
        locality = identity.get("locality") or merchant.get("city") or merchant.get("locality")
        
        raw_langs = identity.get("languages", ["English"])
        if not isinstance(raw_langs, list):
            raw_langs = [raw_langs]
        languages_normalized = [normalize_language_str(lang) for lang in raw_langs]
        
        perf = merchant.get("performance", {})
        if not isinstance(perf, dict):
            perf = {}
        views = safe_int(perf.get("views"))
        calls = safe_int(perf.get("calls"))
        directions = safe_int(perf.get("directions"))
        ctr = safe_float(perf.get("ctr"))
        rating = safe_float(merchant.get("rating"))
        review_count = safe_int(merchant.get("review_count"))
        
        is_sub = merchant.get("is_subscribed")
        if is_sub is None:
            sub_status = merchant.get("subscription_status")
            if sub_status is not None:
                is_sub = safe_bool(sub_status == "active" or sub_status)
        else:
            is_sub = safe_bool(is_sub)
            
        active_offers = merchant.get("offers", [])
        if not isinstance(active_offers, list):
            active_offers = []
            
        return MerchantFeatures(
            merchant_id=m_id,
            name=name,
            owner_name=owner_name,
            locality=locality,
            rating=rating,
            review_count=review_count,
            views=views,
            calls=calls,
            directions=directions,
            ctr=ctr,
            active_offers=active_offers,
            languages_normalized=languages_normalized,
            is_subscribed=is_sub,
            raw_data=merchant
        )

    @staticmethod
    def extract_customer(customer: Optional[Dict[str, Any]]) -> Optional[CustomerFeatures]:
        if not customer or not isinstance(customer, dict):
            return None
        c_id = customer.get("customer_id", "c_unknown")
        identity = customer.get("identity", {})
        if not isinstance(identity, dict):
            identity = {}
        name = identity.get("name", "there")
        locality = identity.get("locality")
        
        payload = customer.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        due_service = payload.get("service_due")
        slots = payload.get("available_slots", [])
        
        raw_langs = identity.get("languages", ["English"])
        if not isinstance(raw_langs, list):
            raw_langs = [raw_langs]
        preferred_lang = normalize_language_str(raw_langs[0] if raw_langs else "English")
        
        return CustomerFeatures(
            customer_id=c_id,
            name=name,
            locality=locality,
            due_service=due_service,
            available_slots=slots if isinstance(slots, list) else [],
            preferred_language=preferred_lang,
            raw_data=customer
        )

    @staticmethod
    def extract_trigger(trigger: Dict[str, Any], merchant: MerchantFeatures) -> TriggerFeatures:
        if not isinstance(trigger, dict):
            trigger = {}
        t_id = trigger.get("id") or trigger.get("trigger_id") or "trg_unknown"
        kind = trigger.get("kind", "unknown")
        scope = trigger.get("scope", "merchant")
        urgency = safe_int(trigger.get("urgency"))
        payload = trigger.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        deadline = payload.get("deadline_iso")
        supp_key = trigger.get("suppression_key") or f"{merchant.merchant_id}:{kind}:{t_id}"
        
        return TriggerFeatures(
            trigger_id=t_id,
            kind=kind,
            scope=scope,
            urgency=urgency,
            payload=payload,
            deadline=deadline,
            suppression_key=supp_key,
            raw_data=trigger
        )

@dataclass
class DecisionResult:
    """
    Holds the deterministic scoring outputs of the DecisionEngine.
    """
    selected_trigger: TriggerFeatures
    priority_score: float
    ranked_evidence: List[Dict[str, Any]]
    decision_rationale: str
    category_strategy_key: str
    merchant_strategy_key: str
    trigger_strategy_key: str
    recommended_cta_type: str

class EvidenceRanker:
    """
    Scores and ranks available facts dynamically depending on category priorities.
    Returns at most two evidence items.
    """
    CATEGORY_PRIORITIES = {
        "dentists": ["research", "appointments", "compliance", "reviews", "perf"],
        "restaurants": ["rush_periods", "orders", "competitor_activity", "perf", "offer"],
        "gyms": ["memberships", "trials", "retention", "perf", "offer"],
        "salons": ["bookings", "stylists", "festivals", "perf", "offer"],
        "pharmacies": ["recalls", "compliance", "molecule_demand", "perf", "safety"]
    }

    @staticmethod
    def get_evidence_weight(category_slug: str, fact_type: str) -> float:
        slug = category_slug.lower()
        matched_cat = None
        for cat in EvidenceRanker.CATEGORY_PRIORITIES:
            if cat in slug:
                matched_cat = cat
                break
        
        if not matched_cat:
            return 10.0
            
        priorities = EvidenceRanker.CATEGORY_PRIORITIES[matched_cat]
        if fact_type in priorities:
            return 50.0 - (priorities.index(fact_type) * 10.0)
        return 10.0

    @staticmethod
    def rank_evidence(category: CategoryFeatures, merchant: MerchantFeatures, trigger: TriggerFeatures) -> List[Dict[str, Any]]:
        facts = []
        kind = trigger.kind
        payload = trigger.payload
        slug = category.slug.lower()
        
        if kind in ("research_digest", "regulation_change"):
            item_id = payload.get("top_item_id")
            item = next((i for i in category.digest_items if i.get("id") == item_id), None)
            if item:
                fact_type = "compliance" if kind == "regulation_change" else "research"
                facts.append({
                    "type": fact_type,
                    "source": item.get("source", "Authority"),
                    "title": item.get("title", "new guidelines"),
                    "summary": item.get("summary", "requirements"),
                    "weight": EvidenceRanker.get_evidence_weight(slug, fact_type)
                })

        if "delta_pct" in payload:
            facts.append({
                "type": "perf",
                "metric": payload.get("metric", "performance"),
                "delta_pct": safe_float(payload.get("delta_pct")),
                "keyword": payload.get("keyword"),
                "weight": EvidenceRanker.get_evidence_weight(slug, "perf")
            })
            
        if "festival" in payload:
            facts.append({
                "type": "festivals",
                "name": payload.get("festival"),
                "days_until": safe_int(payload.get("days_until")),
                "weight": EvidenceRanker.get_evidence_weight(slug, "festivals")
            })

        if "molecule" in payload:
            facts.append({
                "type": "recalls",
                "molecule": payload.get("molecule"),
                "manufacturer": payload.get("manufacturer"),
                "weight": EvidenceRanker.get_evidence_weight(slug, "recalls")
            })
            
        if trigger.scope == "customer" and kind == "recall_due":
            facts.append({
                "type": "appointments",
                "slots_count": len(payload.get("available_slots", [])),
                "weight": EvidenceRanker.get_evidence_weight(slug, "appointments")
            })
            
        if merchant.active_offers:
            facts.append({
                "type": "offer",
                "offer_title": merchant.active_offers[0].get("title", "our special offer"),
                "weight": EvidenceRanker.get_evidence_weight(slug, "offer")
            })
            
        facts.sort(key=lambda x: (-x["weight"], x["type"]))
        
        ranked = []
        for f in facts[:2]:
            cleaned_fact = {k: v for k, v in f.items() if k != "weight"}
            ranked.append(cleaned_fact)
        return ranked

class DecisionEngine:
    """
    Deterministic multi-objective trigger scoring model.
    Evaluates trigger urgency, performance deltas, peer benchmark CTR gaps,
    and breaks ties lexicographically.
    """
    @staticmethod
    def calculate_trigger_score(category: CategoryFeatures, merchant: MerchantFeatures, trigger: TriggerFeatures, suppressed_keys: List[str]) -> float:
        if trigger.suppression_key in suppressed_keys:
            return -9999.0
            
        urgency = float(trigger.urgency) if trigger.urgency is not None else 1.0
        urgency_score = urgency * 10.0
        
        delta_pct = abs(safe_float(trigger.payload.get("delta_pct", 0.0)))
        impact_score = delta_pct * 8.0
        
        ctr_gap = 0.0
        if merchant.ctr is not None and category.peer_avg_ctr is not None:
            ctr_gap = max(0.0, category.peer_avg_ctr - merchant.ctr)
        ctr_gap_score = ctr_gap * 5.0
        
        kind = trigger.kind
        kind_bonus = 0.0
        if kind in ("regulation_change", "supply_alert"):
            kind_bonus = 15.0
        elif kind == "perf_dip":
            kind_bonus = 10.0
        elif kind in ("perf_spike", "search_surge"):
            kind_bonus = 8.0
        elif kind == "festival_upcoming":
            kind_bonus = 5.0
            
        final_score = urgency_score + impact_score + ctr_gap_score + kind_bonus
        return round(final_score, 4)

    def select_decision(self, category: CategoryFeatures, merchant: MerchantFeatures, triggers: List[TriggerFeatures], suppressed_keys: List[str]) -> Optional[DecisionResult]:
        if not triggers:
            return None
            
        scored_candidates = []
        for t in triggers:
            score = self.calculate_trigger_score(category, merchant, t, suppressed_keys)
            
            impact_val = abs(safe_float(t.payload.get("delta_pct", 0.0)))
            urgency_val = t.urgency if t.urgency is not None else 0
            ctr_val = merchant.ctr if merchant.ctr is not None else 0.0
            
            scored_candidates.append({
                "score": score,
                "impact": impact_val,
                "urgency": urgency_val,
                "ctr": ctr_val,
                "id": t.trigger_id,
                "trigger": t
            })
            
        scored_candidates.sort(key=lambda x: (
            -x["score"],
            -x["impact"],
            -x["urgency"],
            x["ctr"],
            x["id"]
        ))
        
        best = scored_candidates[0]
        selected_trg = best["trigger"]
        score = best["score"]
        
        ranked_ev = EvidenceRanker.rank_evidence(category, merchant, selected_trg)
        
        rationale = f"Trigger '{selected_trg.trigger_id}' selected with score {score:.2f}."
        if selected_trg.kind in ("regulation_change", "supply_alert"):
            rationale += " Priority compliance override applied."
        elif best["impact"] > 0.0:
            rationale += f" Significant performance delta of {best['impact'] * 100:.1f}% identified."
            
        cta_type = "optimize"
        if selected_trg.kind in ("perf_spike", "search_surge"):
            cta_type = "activate"
        elif selected_trg.kind in ("regulation_change", "supply_alert"):
            cta_type = "compliance_audit"
        elif selected_trg.kind == "festival_upcoming":
            cta_type = "launch"
        elif selected_trg.scope == "customer":
            cta_type = "book"
            
        slug = category.slug.lower()
        cat_key = "default"
        for key in ["dentist", "salon", "restaurant", "gym", "pharmac"]:
            if key in slug:
                cat_key = key
                break
                
        merchant_key = "growing"
        if merchant.rating and merchant.rating >= 4.5:
            merchant_key = "trusted"
        elif merchant.ctr and category.peer_avg_ctr and merchant.ctr < category.peer_avg_ctr:
            merchant_key = "optimization_needed"
            
        return DecisionResult(
            selected_trigger=selected_trg,
            priority_score=score,
            ranked_evidence=ranked_ev,
            decision_rationale=rationale,
            category_strategy_key=cat_key,
            merchant_strategy_key=merchant_key,
            trigger_strategy_key=selected_trg.kind,
            recommended_cta_type=cta_type
        )

class CategoryStrategy:
    def __init__(self, salutation_prefix: str, voice_intro: str, taboo_words: List[str]):
        self.salutation_prefix = salutation_prefix
        self.voice_intro = voice_intro
        self.taboo_words = taboo_words

class DentistsStrategy(CategoryStrategy):
    def __init__(self):
        super().__init__(
            salutation_prefix="Dr. ",
            voice_intro="From a clinical perspective,",
            taboo_words=["cheap", "bargain", "discount deal", "clearance"]
        )

class RestaurantsStrategy(CategoryStrategy):
    def __init__(self):
        super().__init__(
            salutation_prefix="Chef ",
            voice_intro="Operator-to-operator, let's drive more orders.",
            taboo_words=["clinical", "patient", "compliance SOP"]
        )

class SalonsStrategy(CategoryStrategy):
    def __init__(self):
        super().__init__(
            salutation_prefix="Hi ",
            voice_intro="To keep your chairs full and clients looking great,",
            taboo_words=["clinical", "prescription", "safety audit"]
        )

class GymsStrategy(CategoryStrategy):
    def __init__(self):
        super().__init__(
            salutation_prefix="Coach ",
            voice_intro="Let's push those membership numbers up.",
            taboo_words=["patient", "medical", "drug recall"]
        )

class PharmaciesStrategy(CategoryStrategy):
    def __init__(self):
        super().__init__(
            salutation_prefix="Pharmacist ",
            voice_intro="Ensuring precise care and compliance,",
            taboo_words=["clearance sale", "deal of the day", "cheap price"]
        )

class DefaultStrategy(CategoryStrategy):
    def __init__(self):
        super().__init__(
            salutation_prefix="",
            voice_intro="Looking at your business metrics,",
            taboo_words=[]
        )

class CategoryStrategyFactory:
    @staticmethod
    def get_strategy(slug: str) -> CategoryStrategy:
        s = slug.lower()
        if "dentist" in s:
            return DentistsStrategy()
        elif "restaurant" in s:
            return RestaurantsStrategy()
        elif "salon" in s:
            return SalonsStrategy()
        elif "gym" in s:
            return GymsStrategy()
        elif "pharmac" in s:
            return PharmaciesStrategy()
        return DefaultStrategy()

class MerchantStrategy:
    @staticmethod
    def get_context_sentence(merchant: MerchantFeatures, category: CategoryFeatures, is_hinglish: bool) -> str:
        if is_hinglish:
            if merchant.rating and merchant.rating >= 4.5:
                return f"Aapke high {merchant.rating:.1f}-star rating aur reviews ke sath,"
            elif merchant.ctr and category.peer_avg_ctr and merchant.ctr < category.peer_avg_ctr:
                return f"Aapke views steady hain par searches badhane ke liye,"
            elif merchant.review_count and merchant.review_count > 20:
                return f"Aapke growing business ko area mein expand karne ke liye,"
            return f"Aapke {merchant.locality or 'locality'} business ke liye,"
        else:
            if merchant.rating and merchant.rating >= 4.5:
                return f"With your high {merchant.rating:.1f}-star rating and trusted reviews,"
            elif merchant.ctr and category.peer_avg_ctr and merchant.ctr < category.peer_avg_ctr:
                return f"Although your views are steady, CTR lags peers,"
            elif merchant.review_count and merchant.review_count > 20:
                return f"To further expand your growing business in {merchant.locality or 'locality'},"
            return f"For your business based in {merchant.locality or 'locality'},"

class CTAOptimizer:
    @staticmethod
    def get_cta(decision: DecisionResult, merchant: MerchantFeatures) -> str:
        kind = decision.selected_trigger.kind
        payload = decision.selected_trigger.payload
        active_offer = merchant.active_offers[0].get("title", "discount") if merchant.active_offers else "our catalog"
        offer_action = active_offer.split('@')[-1].strip() if '@' in active_offer else active_offer
        
        if kind == "research_digest":
            source = "Research"
            if decision.ranked_evidence and decision.ranked_evidence[0].get("type") == "research":
                source = decision.ranked_evidence[0].get("source", "Research")
            return f"Send {source} Abstract"
        elif kind == "regulation_change":
            return "Audit compliance SOP"
        elif kind == "perf_dip":
            return "Optimize search ranking"
        elif kind in ("perf_spike", "search_surge"):
            return f"Activate {offer_action}"
        elif kind == "festival_upcoming":
            festival = payload.get("festival", "upcoming peak")
            return f"Launch {festival} Offer"
        elif kind == "milestone_reached":
            target = payload.get("milestone_value", 100)
            return f"Nudge reviews for {target}"
        elif kind == "gbp_unverified":
            return "Start verification"
        elif kind == "supply_alert":
            return "Review recall list"
        elif kind == "low_sales":
            return "Push discount campaign"
        elif kind == "weekend":
            return "Capture weekend bookings"
        elif kind == "lunch_time":
            return "Activate Lunch Rush"
        elif kind == "payday":
            return "Launch Payday campaign"
        elif kind == "rain":
            return "Flip weather to revenue"
        elif kind == "active_planning_intent":
            return "Go Live with strategy"
            
        if decision.selected_trigger.scope == "customer":
            if kind == "recall_due":
                return "Reply 1 or 2"
            elif kind == "trial_followup":
                return "Reserve spot?"
            return "Claim offer now"
            
        return "Optimize business profile"

class MessageComposer:
    @staticmethod
    def compose_message(
        decision: DecisionResult,
        category: CategoryFeatures,
        merchant: MerchantFeatures,
        customer: Optional[CustomerFeatures] = None
    ) -> Dict[str, Any]:
        trigger = decision.selected_trigger
        kind = trigger.kind
        payload = trigger.payload
        is_hinglish = "hi" in merchant.languages_normalized or "hi-en" in merchant.languages_normalized
        
        cat_strat = CategoryStrategyFactory.get_strategy(category.slug)
        owner_name = merchant.owner_name if merchant.owner_name else "there"
        salutation = f"{cat_strat.salutation_prefix}{owner_name}".strip()
        voice_intro = cat_strat.voice_intro
        
        if trigger.scope == "customer" and customer:
            c_name = customer.name
            m_name = merchant.name
            active_offer = merchant.active_offers[0].get("title", "our special services") if merchant.active_offers else "our latest services"
            m_locality = merchant.locality if merchant.locality else "the area"
            
            if kind == "recall_due":
                service = customer.due_service.replace("_", " ") if customer.due_service else "check-up"
                slots = customer.available_slots
                slot_text = f"We have slots: {slots[0]['label']} or {slots[1]['label']}" if len(slots) >= 2 else "Want to book a slot?"
                
                if is_hinglish:
                    body = f"Hi {c_name}, {m_name} here 🦷 Aapka {service} due hai. Available slots: {slots[0]['label']} ya {slots[1]['label']}. We are running {active_offer}. Reply 1, 2 or suggest a time."
                else:
                    body = f"Hi {c_name}, {m_name} here 🦷 It's time for your {service}. {slot_text}. We're running {active_offer} this week. Reply 1, 2, or suggest a time."
            elif kind == "trial_followup":
                service = str(payload.get("intent_topic", "program")).replace("_", " ")
                if is_hinglish:
                    body = f"Hi {c_name}, hope you enjoyed the trial at {m_name}! Ready to reserve your spot? New members ke liye {active_offer} active hai."
                else:
                    body = f"Hi {c_name}, hope you enjoyed the trial at {m_name}! Ready to continue with the full {service}? We have a {active_offer} for new members."
            else:
                if is_hinglish:
                    body = f"Hi {c_name}, special update from {m_name}. Locals ke liye limited-time '{active_offer}' active hai in {m_locality}. Slots verify/claim karein?"
                else:
                    body = f"Hi {c_name}, special update from {m_name}. We're running a limited-time '{active_offer}' just for our locals in {m_locality}. Claim it now?"
            
            cta = CTAOptimizer.get_cta(decision, merchant)
            return {
                "action": "send",
                "body": body,
                "cta": cta,
                "send_as": "merchant_on_behalf",
                "rationale": decision.decision_rationale
            }

        m_name = merchant.name
        locality = merchant.locality if merchant.locality else "your area"
        views = merchant.views if merchant.views is not None else 1000
        calls = merchant.calls if merchant.calls is not None else 50
        ctr = merchant.ctr if merchant.ctr is not None else 0.03
        peer_ctr = category.peer_avg_ctr if category.peer_avg_ctr is not None else 0.03
        active_offer = merchant.active_offers[0].get("title", "growth campaign") if merchant.active_offers else "custom growth plan"
        
        delta_pct = abs(safe_float(payload.get("delta_pct", 0.0))) * 100
        keyword = payload.get("keyword", category.slug)
        
        m_context_str = MerchantStrategy.get_context_sentence(merchant, category, is_hinglish)
        
        if kind == "research_digest":
            source = "JIDA"
            title = "dental cleaning guidelines"
            if decision.ranked_evidence:
                source = decision.ranked_evidence[0].get("source", "Research")
                title = decision.ranked_evidence[0].get("title", "digest items")
            if is_hinglish:
                body = f"{salutation}, {source} ne '{title}' par new guidelines publish kiye hain. {voice_intro} aapke {locality} patient-mix aur {views} views ke basis par, we can drive CTR. Publish karoon?"
            else:
                body = f"{salutation}, {source} just released data on '{title}'. {voice_intro} based on your {locality} patient-mix and {views} views, we can drive up to 3% lift. Shall I publish?"
                
        elif kind == "regulation_change":
            source = "Health Dept"
            title = "revised compliance regulations"
            deadline = payload.get("deadline_iso", "soon")
            if decision.ranked_evidence:
                source = decision.ranked_evidence[0].get("source", "Authority")
                title = decision.ranked_evidence[0].get("title", "compliance rules")
            if is_hinglish:
                body = f"Compliance Alert: {source} has revised '{title}' effective {deadline}. {voice_intro} {m_context_str} audit SOPs to protect your {calls} calls. Start karein?"
            else:
                body = f"Compliance Alert: {source} has revised '{title}' effective {deadline}. {voice_intro} {m_context_str} let's audit your SOPs to protect your {calls} monthly calls. Shall I start?"
                
        elif kind == "perf_dip":
            if is_hinglish:
                body = f"Visibility Alert: {salutation}, {m_name} is missing ~{delta_pct:.0f}% searches for '{keyword}' in {locality}. CTR ({ctr:.3f}) lags peers ({peer_ctr:.3f}). {voice_intro} {m_context_str} promote '{active_offer}' to recover search rankings. Proceed karein?"
            else:
                body = f"Visibility Alert: {salutation}, {m_name} is missing ~{delta_pct:.0f}% of '{keyword}' searches in {locality}. Your CTR ({ctr:.3f}) is trailing category peers ({peer_ctr:.3f}). {voice_intro} {m_context_str} let's promote '{active_offer}' to regain search rankings. Proceed?"
                
        elif kind in ("perf_spike", "search_surge"):
            if is_hinglish:
                body = f"Demand Surge: {salutation}, searches for '{keyword}' in {locality} surged {delta_pct:.0f}%. With {views} views, intent is high. {voice_intro} {m_context_str} activate '{active_offer}' to capture bookings. Go live karein?"
            else:
                body = f"Demand Surge: {salutation}, I've detected a {delta_pct:.0f}% surge in {locality} searches for '{keyword}'. With your {views} recent views, intent is high. {voice_intro} {m_context_str} let's activate '{active_offer}' to capture bookings. Shall I go live?"
                
        elif kind == "festival_upcoming":
            festival = payload.get("festival", "upcoming peak")
            days = payload.get("days_until", 7)
            if is_hinglish:
                body = f"Peak Demand: {salutation}, {festival} is {days} days away. {locality} intent is rising. {voice_intro} {m_context_str} launch your '{active_offer}' to capture bookings. Launch karein?"
            else:
                body = f"Peak Demand: {salutation}, {festival} is {days} days away. {locality} intent is rising. {voice_intro} {m_context_str} let's launch your '{active_offer}' to capture this festive surge and boost views. Shall I proceed?"
                
        elif kind == "milestone_reached":
            metric = str(payload.get("metric", "reviews")).replace("_", " ")
            val = payload.get("value_now", 0)
            target = payload.get("milestone_value", 100)
            gap = max(1, target - val)
            if is_hinglish:
                body = f"Authority Boost: {salutation}, {m_name} has {val} reviews — only {gap} left to hit the {target} milestone. {voice_intro} {m_context_str} push a nudge to reviews. Send karoon?"
            else:
                body = f"Authority Boost: {salutation}, {m_name} is at {val} reviews — just {gap} away from the {target} milestone. {voice_intro} {m_context_str} let's push a review-nudge to bridge this gap. Shall I send?"
                
        elif kind == "supply_alert":
            molecule = payload.get("molecule") or payload.get("item", "stock")
            mfr = payload.get("manufacturer", "the manufacturer")
            if is_hinglish:
                body = f"Safety Alert: {salutation}, {mfr} issued a recall for {molecule}. {voice_intro} patient safety check is needed in {locality}. Recall SOP review list ready. Start karein?"
            else:
                body = f"Safety Alert: {salutation}, {mfr} has issued a recall for {molecule}. {voice_intro} we must review patients in {locality} to ensure compliance and safety. Shall I start?"
                
        elif kind == "weekend":
            if is_hinglish:
                body = f"Weekend Rush: {salutation}, weekend bookings demand {locality} mein badh rahi hai. {voice_intro} {m_context_str} views ko convert karne ke liye launch '{active_offer}'. Ready?"
            else:
                body = f"Weekend Rush: {salutation}, weekend intent is building in {locality}. {voice_intro} {m_context_str} let's activate '{active_offer}' to convert your {views} views into bookings today. Ready?"
                
        elif kind == "lunch_time":
            if is_hinglish:
                body = f"Lunch Rush: {salutation}, midday rushed searches shuru ho rahe hain in {locality}. {voice_intro} {m_context_str} launch '{active_offer}' to maximize dining table turns. Go live?"
            else:
                body = f"Lunch Rush: {salutation}, the midday rush in {locality} is starting. {voice_intro} {m_context_str} let's activate '{active_offer}' to maximize table turns and capture this rush. Go live?"
                
        elif kind == "payday":
            if is_hinglish:
                body = f"Payday Opportunity: {salutation}, payday week is active in {locality}! {voice_intro} {m_context_str} push '{active_offer}' to secure high-value bookings. Start karein?"
            else:
                body = f"Payday Opportunity: {salutation}, it's payday week in {locality}! Customers are ready to spend. {voice_intro} {m_context_str} let's launch your '{active_offer}' to secure bookings now. Shall we start?"
                
        elif kind == "rain":
            if is_hinglish:
                body = f"Weather Shift: {salutation}, rain in {locality} is affecting offline footfall. {voice_intro} {m_context_str} promote '{active_offer}' to capture users online. Activate karein?"
            else:
                body = f"Weather Shift: {salutation}, it's raining in {locality}. Let's flip this into an advantage by promoting '{active_offer}' to capture users browsing online. Shall I activate?"
                
        elif kind == "gbp_unverified":
            uplift = abs(safe_float(payload.get("estimated_uplift_pct", 0.30))) * 100
            if is_hinglish:
                body = f"Visibility Gap: {salutation}, {m_name} is unverified, losing ~{uplift:.0f}% calls in {locality}. {voice_intro} {m_context_str} verify business profile now. Request start karein?"
            else:
                body = f"Visibility Gap: {salutation}, {m_name} is losing ~{uplift:.0f}% of calls in {locality} due to being unverified. {voice_intro} {m_context_str} let's verify your profile to protect views. Shall I start?"
                
        elif kind == "low_sales":
            if is_hinglish:
                body = f"Revenue Alert: {salutation}, daily sales pace is lagging. {voice_intro} {m_context_str} run '{active_offer}' campaign now. Push karein?"
            else:
                body = f"Revenue Alert: {salutation}, daily sales pace is lagging. {voice_intro} {m_context_str} let's launch your '{active_offer}' to drive immediate footfall and recover sales pace. Shall I proceed?"
                
        elif kind == "active_planning_intent":
            topic = str(payload.get("intent_topic", "update")).replace("_", " ")
            if is_hinglish:
                body = f"Planning Alert: {salutation}, campaigns draft is ready for {topic}. {voice_intro} {m_context_str} push this update to GBP to boost your CTR. Publish karein?"
            else:
                body = f"Planning Alert: {salutation}, I've drafted the {topic} strategy for {locality}. {voice_intro} {m_context_str} let's push this update to GBP to boost your CTR. Shall we publish?"
                
        else:
            if is_hinglish:
                body = f"Growth Update: {salutation}, search views are active at {views}. {voice_intro} {m_context_str} promote '{active_offer}' to capture local searchers now. Go live?"
            else:
                body = f"Growth Update: {salutation}, {m_name} generated {views} searches recently. {voice_intro} {m_context_str} let's activate '{active_offer}' in {locality} to capture bookings now. Shall I proceed?"
                
        cta = CTAOptimizer.get_cta(decision, merchant)
        
        for taboo in cat_strat.taboo_words:
            if taboo in body.lower():
                body = body.lower().replace(taboo, "special-value")
                
        return {
            "action": "send",
            "body": body,
            "cta": cta,
            "send_as": "vera",
            "rationale": decision.decision_rationale
        }

@dataclass
class ValidationReport:
    is_valid: bool
    length_exceeded: bool
    has_urls: bool
    has_taboo_words: bool
    missing_grounding: bool
    duplicate_evidence: bool
    taboo_words_found: List[str]

class ConstraintValidator:
    @staticmethod
    def validate_message(
        body: str, 
        cta: str, 
        category: CategoryFeatures, 
        merchant: MerchantFeatures, 
        decision: DecisionResult
    ) -> ValidationReport:
        length_exceeded = len(body) > 320
        has_urls = bool(re.search(r'https?://|www\.', body))
        
        cat_strat = CategoryStrategyFactory.get_strategy(category.slug)
        taboo_found = []
        for taboo in cat_strat.taboo_words:
            if taboo in body.lower():
                taboo_found.append(taboo)
                
        missing_grounding = False
        nums = re.findall(r'\b\d+\.?\d*\b', body)
        for num in nums:
            val_str = str(num)
            if "2026" in val_str:
                continue
            found = False
            for f_val in [merchant.views, merchant.calls, merchant.directions, merchant.rating, merchant.review_count]:
                if f_val is not None and (val_str in str(f_val) or str(f_val) in val_str):
                    found = True
                    break
            if not found:
                for k, v in decision.selected_trigger.payload.items():
                    if val_str in str(v) or str(v) in val_str:
                        found = True
                        break
            if not found and category.peer_avg_ctr is not None:
                if val_str in str(category.peer_avg_ctr) or str(category.peer_avg_ctr) in val_str:
                    found = True
            
            if not found and int(float(num)) not in (1, 2, 3, 5, 7, 10, 15, 20, 30, 50, 60, 100):
                missing_grounding = True
                
        duplicate_evidence = False
        is_valid = not (length_exceeded or has_urls or bool(taboo_found) or missing_grounding)
        
        return ValidationReport(
            is_valid=is_valid,
            length_exceeded=length_exceeded,
            has_urls=has_urls,
            has_taboo_words=bool(taboo_found),
            missing_grounding=missing_grounding,
            duplicate_evidence=duplicate_evidence,
            taboo_words_found=taboo_found
        )

class RepairEngine:
    @staticmethod
    def repair_message(
        body: str, 
        report: ValidationReport, 
        category: CategoryFeatures, 
        merchant: MerchantFeatures
    ) -> str:
        if report.has_urls:
            body = re.sub(r'https?://[^\s]+|www\.[^\s]+', '', body).strip()
            
        if report.has_taboo_words:
            cat_strat = CategoryStrategyFactory.get_strategy(category.slug)
            for taboo in report.taboo_words_found:
                replacement = "special-value"
                if taboo == "cheap":
                    replacement = "premium value"
                elif taboo == "bargain":
                    replacement = "special"
                elif taboo == "clearance":
                    replacement = "exclusive offer"
                elif taboo == "discount deal":
                    replacement = "growth update"
                body = re.sub(re.escape(taboo), replacement, body, flags=re.IGNORECASE)
                
        if len(body) > 320:
            cat_strat = CategoryStrategyFactory.get_strategy(category.slug)
            if cat_strat.voice_intro in body:
                body = body.replace(cat_strat.voice_intro, "").strip()
            
            if len(body) > 320 and merchant.owner_name:
                salutation = f"{cat_strat.salutation_prefix}{merchant.owner_name}".strip()
                if salutation in body:
                    body = body.replace(salutation, "").strip()
                    if body.startswith(","):
                        body = body[1:].strip()
            
            if len(body) > 320:
                body = body.replace("I am proceeding with the confirmed update for your business now.", "Proceeding now.")
                
            if len(body) > 320:
                body = body[:317] + "..."
                
        return body

class SelfQualityScorer:
    @staticmethod
    def score_quality(body: str, category: CategoryFeatures, merchant: MerchantFeatures) -> Dict[str, float]:
        nums = re.findall(r'\b\d+\b', body)
        specificity = min(10.0, 3.0 + len(nums) * 2.0)
        
        cat_strat = CategoryStrategyFactory.get_strategy(category.slug)
        category_fit = 8.0
        if cat_strat.salutation_prefix and cat_strat.salutation_prefix in body:
            category_fit += 1.0
        for taboo in cat_strat.taboo_words:
            if taboo in body.lower():
                category_fit -= 4.0
                
        merchant_fit = 8.0
        if merchant.name in body or (merchant.owner_name and merchant.owner_name in body):
            merchant_fit += 1.0
        if merchant.locality and merchant.locality in body:
            merchant_fit += 1.0
            
        return {
            "specificity": specificity,
            "category_fit": max(0.0, category_fit),
            "merchant_fit": max(0.0, merchant_fit)
        }

class ReplyIntentClassifier:
    @staticmethod
    def classify_intent(text: str) -> str:
        text = text.lower().strip()
        auto_reply_keywords = [
            "out of office", "automated assistant", "contacting us", "team will",
            "auto-reply", "system message", "noreply", "no-reply",
            "will respond shortly", "currently unavailable to take your message"
        ]
        if any(k in text for k in auto_reply_keywords):
            return "auto_reply"
            
        hostile_keywords = [
            "stop", "spam", "useless", "don't message", "leave me", "not interested",
            "fuck", "shit", "annoying", "never message"
        ]
        if any(k in text for k in hostile_keywords):
            return "hostile"
            
        positive_keywords = [
            "ok", "yes", "do it", "go ahead", "lets do it", "proceed", "agree", "book", 
            "sure", "confirm", "yep", "1", "2"
        ]
        if any(k in text for k in positive_keywords):
            return "positive"
            
        negative_keywords = [
            "no", "nope", "not now", "cancel", "deny"
        ]
        if any(k in text for k in negative_keywords):
            return "negative"
            
        scheduling_keywords = [
            "schedule", "book slot", "am", "pm", "time", "date", "calendar", "tomorrow", "monday"
        ]
        if any(k in text for k in scheduling_keywords):
            return "scheduling"
            
        pricing_keywords = [
            "price", "cost", "how much", "charge", "fees", "billing", "expensive"
        ]
        if any(k in text for k in pricing_keywords):
            return "pricing"
            
        clarification_keywords = [
            "what next", "what is this", "how does this work", "why", "who is this", "explain"
        ]
        if any(k in text for k in clarification_keywords):
            return "clarification"
            
        return "unknown"

class ConversationStateMachine:
    def __init__(self, current_state: str = "Idle"):
        self.state = current_state

    def transition(self, intent: str, turn: int) -> str:
        if self.state == "Idle":
            self.state = "Opportunity"
        elif self.state == "Opportunity":
            self.state = "Sent"
        elif self.state == "Sent":
            if intent == "auto_reply":
                self.state = "Waiting"
            elif intent == "hostile":
                self.state = "Suppressed"
            elif intent == "positive":
                self.state = "Positive"
            elif intent in ("clarification", "pricing"):
                self.state = "Question"
            elif intent == "negative":
                self.state = "Ended"
            else:
                self.state = "Waiting"
        elif self.state == "Waiting":
            if intent == "auto_reply" and turn >= 2:
                self.state = "Ended"
            elif intent == "positive":
                self.state = "Positive"
            elif intent == "hostile":
                self.state = "Suppressed"
            else:
                self.state = "Ended"
        elif self.state in ("Positive", "Suppressed", "Ended"):
            pass
            
        return self.state

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
            cat_feat = FeatureExtractor.extract_category(category)
            mer_feat = FeatureExtractor.extract_merchant(merchant, cat_feat)
            cust_feat = FeatureExtractor.extract_customer(customer)
            trg_feat = FeatureExtractor.extract_trigger(trigger, mer_feat)
            
            engine = DecisionEngine()
            decision = engine.select_decision(cat_feat, mer_feat, [trg_feat], [])
            
            result = MessageComposer.compose_message(decision, cat_feat, mer_feat, cust_feat)
            
            # Quality Scoring
            quality_scores = SelfQualityScorer.score_quality(result["body"], cat_feat, mer_feat)
            
            # Constraint Validation
            report = ConstraintValidator.validate_message(result["body"], result["cta"], cat_feat, mer_feat, decision)
            if not report.is_valid:
                repaired_body = RepairEngine.repair_message(result["body"], report, cat_feat, mer_feat)
                result["body"] = repaired_body
                
            result["suppression_key"] = trg_feat.suppression_key
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
