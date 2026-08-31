"""
Assistant Chat Service (Phase 6, Increment 15 boundary correction).

Provides the Control Center's assistant chat endpoint. Implements:
1. Natural language intent recognition
2. Previous solution lookup via EnterpriseInformationPort
3. Capability discovery via CapabilityDiscoveryPort
4. Session creation via SessionFactoryPort
5. Pattern execution via PatternExecutionPort
6. Capability execution via CapabilityExecutionPort
7. Human-in-the-loop support

Assistant is an application-layer translation service. It depends on ports,
not concrete domain-plane implementations.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from ai_response import AIResponseService
from assistant import AssistantReasoningService
from intent import Intent, IntentOrigin, ProblemFrame, recognise
from pydantic import BaseModel, Field

from contracts.capability_discovery import CapabilityCandidate, CapabilityDiscoveryPort
from contracts.capability_execution import CapabilityExecutionPort, ExecutionResult
from contracts.enterprise_capability_query import CapabilityAvailability, EnterpriseCapabilityQueryPort
from contracts.enterprise_information import EnterpriseInformationPort, SolutionRecord
from contracts.organisational_context import OrganisationalContextPort
from contracts.pattern_execution import PatternExecutionPort, PatternExecutionRequest
from contracts.session_factory import SessionFactoryPort, SessionReference
from contracts.work_management import WorkCreateRequest, WorkManagementPort

from capability_action import CapabilityActionPolicy, ExecuteCapability, AskUserToSelect

logger = logging.getLogger("ai.chat")

# TODO: Replace with a user-facing response policy abstraction.
# This is a temporary proof value for the fast/slow capability decision.
_FAST_ENTERPRISE_ETA_THRESHOLD_SECONDS = 60


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    user_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    message: str
    session_id: str
    status: str
    reasoning: str | None = None
    previous_solution: dict[str, Any] | None = None
    human_input_request: dict[str, Any] | None = None
    capability_candidates: list[dict[str, Any]] | None = None
    telemetry: dict[str, Any] = Field(default_factory=dict)
    execution_outputs: dict[str, Any] | None = None
    execution_artifacts: list[str] = Field(default_factory=list)


class ActionableIntent(BaseModel):
    mode: str
    action: str | None = None
    objective: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    confidence: str = "low"


def _extract_planning_entities(text: str, document_text: str | None = None) -> dict[str, Any]:
    """Extract explicit planning information from user text and optional document."""
    sources = [text]
    if document_text:
        sources.append(document_text)

    entities: dict[str, Any] = {
        "subject": None,
        "activity_type": None,
        "people_count": None,
        "venue": None,
        "budget": None,
        "date": None,
        "duration_days": None,
        "distance_km": None,
        "constraints": [],
        "is_definite_reference": False,
        "supporting_signals": [],
    }

    for source in sources:
        lower = source.lower()

        if lower.startswith("plan the ") or " plan the " in lower:
            entities["is_definite_reference"] = True

        party_keywords = ["birthday party", "party", "event", "celebration", "gathering", "meeting", "conference", "workshop"]
        for keyword in party_keywords:
            if keyword in lower:
                entities["activity_type"] = "event"
                if keyword == "birthday party":
                    entities["subject"] = "birthday party"
                elif keyword == "party":
                    entities["subject"] = "party"
                elif keyword in ("event", "celebration", "gathering"):
                    entities["subject"] = keyword
                elif keyword == "meeting":
                    entities["subject"] = "meeting"
                elif keyword == "conference":
                    entities["subject"] = "conference"
                elif keyword == "workshop":
                    entities["subject"] = "workshop"
                break

        if entities["subject"] is None:
            activity_keywords = ["hiking", "trip", "launch", "retreat", "festival", "market", "wedding", "conference", "workshop", "walking", "trekking", "alpine", "trail", "mountaineering", "expedition", "journey", "adventure", "outing", "excursion", "tour"]
            for keyword in activity_keywords:
                if keyword in lower:
                    entities["subject"] = keyword
                    entities["activity_type"] = "event"
                    break

        outdoor_signals = ["hiking boots", "packs", "tents", "backpacking", "trail", "mountain", "alpine", "walking day", "km per day", "km/day"]
        for signal in outdoor_signals:
            if signal in lower:
                entities["supporting_signals"].append(signal)
                break

        if entities["subject"] in ("hiking", "walking", "trekking", "alpine", "trail", "mountaineering", "expedition", "journey", "adventure", "outing", "excursion", "tour"):
            entities["activity_type"] = "outdoor activity"

        word_numbers = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
        }
        for word, num in word_numbers.items():
            if re.search(rf"\b{word}\s*(people|guests|attendees|persons|participants)\b", lower):
                entities["people_count"] = num
                break

        if entities["people_count"] is None:
            for word, num in word_numbers.items():
                if re.search(rf"\b{word}\s+of\s+us\b", lower):
                    entities["people_count"] = num
                    break

        if entities["people_count"] is None:
            of_us_pattern = re.compile(r"\b(\d+)\s+of\s+us\b")
            of_us_match = of_us_pattern.search(lower)
            if of_us_match:
                entities["people_count"] = int(of_us_match.group(1))

        venue_pattern = re.compile(r"\b(?:in|at|to|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")
        venue_matches = venue_pattern.finditer(source)
        for venue_match in venue_matches:
            candidate = venue_match.group(1)
            known_venues = {"Grindelwald", "Interlaken", "Zermatt", "Lucerne", "Zurich", "Geneva", "Bern", "Davos", "St. Moritz", "Jungfrau", "Matterhorn"}
            if candidate in known_venues or any(candidate.startswith(v) for v in known_venues):
                entities["venue"] = candidate
                break

        budget_pattern = re.compile(r"\$(\d+(?:\.\d+)?)\s*(?:budget|\$|usd)?")
        budget_match = budget_pattern.search(lower)
        if budget_match:
            entities["budget"] = float(budget_match.group(1))

        for word, num in word_numbers.items():
            if re.search(rf"\b{word}\s*(?:day|days|night|nights|week|weeks)\b", lower):
                entities["duration_days"] = num
                break

        if entities["duration_days"] is None:
            duration_pattern = re.compile(r"\b(\d+)\s*(?:day|days|night|nights|week|weeks)\b")
            duration_match = duration_pattern.search(lower)
            if duration_match:
                entities["duration_days"] = int(duration_match.group(1))

        distance_pattern = re.compile(r"\b(\d+(?:\.\d+)?)\s*km\b")
        distance_match = distance_pattern.search(lower)
        if distance_match:
            entities["distance_km"] = float(distance_match.group(1))

        date_keywords = ["today", "tomorrow", "next week", "next month", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
        for keyword in date_keywords:
            if keyword in lower:
                entities["date"] = keyword
                break

    return entities


def _extract_analysis_entities(text: str, document_text: str | None = None) -> dict[str, Any]:
    """Extract business analysis context from user text and optional document."""
    sources = [text]
    if document_text:
        sources.append(document_text)

    entities: dict[str, Any] = {
        "subject": None,
        "analysis_type": None,
        "metrics": [],
        "problems": [],
        "objectives": [],
        "constraints": [],
        "stakeholders": [],
        "time_period": None,
        "supporting_signals": [],
        "goal": None,
        "_request_text": text,
    }

    combined = " ".join(sources)
    lower = combined.lower()

    analysis_keywords = ["analyse", "analyze", "analysis", "review", "focus", "prioritise", "prioritize", "what should i focus on", "tell me what i should focus on"]
    for keyword in analysis_keywords:
        if keyword in lower:
            entities["analysis_type"] = "business_analysis"
            break

    if entities["analysis_type"] is None:
        business_keywords = ["revenue", "profit", "customer", "retention", "churn", "support", "operational", "quarterly", "feedback", "market", "sales", "growth", "decline", "issue", "problem", "opportunity"]
        for keyword in business_keywords:
            if keyword in lower:
                entities["analysis_type"] = "business_analysis"
                break

    goal_patterns = [
        (r"what (?:i|we) (?:should|do) (?:focus on|prioritise|prioritize)", "identify_focus_areas"),
        (r"what (?:should|do) (?:i|we) (?:focus on|prioritise|prioritize)", "identify_focus_areas"),
        (r"biggest risks?", "identify_risks"),
        (r"find opportunities?", "identify_opportunities"),
        (r"why performance has (?:deteriorated|declined|dropped|fallen)", "explain_deterioration"),
        (r"why (?:are we|we're|am i|i'm) (?:losing|customers|declining)", "explain_deterioration"),
        (r"determine why", "explain_deterioration"),
        (r"what (?:i|we) (?:should|do) investigate next", "identify_investigation_areas"),
        (r"what (?:should|do) (?:i|we) investigate next", "identify_investigation_areas"),
        (r"limit growth", "identify_growth_constraints"),
        (r"improve growth", "identify_growth_opportunities"),
        (r"what needs attention", "identify_attention_areas"),
        (r"what is causing the problem", "identify_root_cause"),
    ]
    for pattern, label in goal_patterns:
        if re.search(pattern, lower):
            entities["goal"] = label
            break

    subject_patterns = [
        (r"revenue\s+(?:declined|increased|dropped|grew|fell|rose)\s+(\d+)%", "revenue change"),
        (r"customer\s+retention\s+(?:fell|dropped|declined|decreased)\s+from\s+(\d+)%?\s+to\s+(\d+)%?", "customer retention decline"),
        (r"support\s+volume\s+(?:increased|rose|grew)\s+(\d+)%", "support volume increase"),
        (r"nps\s+(?:dropped|fell|declined|decreased)\s+from\s+(\d+)\s+to\s+(\d+)", "NPS decline"),
        (r"(\d+)\s+new\s+competitors", "new competitors"),
        (r"headcount\s+(?:frozen|reduced|increased)", "headcount change"),
    ]
    for pattern, label in subject_patterns:
        match = re.search(pattern, lower)
        if match:
            entities["subject"] = label
            entities["supporting_signals"].append(f"Matched pattern: {label}")
            break

    if entities["subject"] is None:
        if "revenue" in lower and ("declined" in lower or "dropped" in lower or "fell" in lower):
            entities["subject"] = "revenue decline"
        elif "customer" in lower and "retention" in lower:
            entities["subject"] = "customer retention"
        elif "support" in lower and "volume" in lower:
            entities["subject"] = "support volume"
        elif "nps" in lower:
            entities["subject"] = "net promoter score"
        elif "competitive" in lower or "competitor" in lower:
            entities["subject"] = "competitive pressure"
        elif "operational" in lower:
            entities["subject"] = "operational performance"

    metric_patterns = [
        r"revenue\s+(?:declined|dropped|fell|decreased)\s+(\d+)%",
        r"revenue\s+(?:increased|grew|rose)\s+(\d+)%",
        r"retention\s+(?:fell|dropped|declined)\s+from\s+(\d+)%?\s+to\s+(\d+)%?",
        r"retention\s+(?:is|was|dropped to|fell to)\s+(\d+)%",
        r"support\s+volume\s+(?:increased|rose|grew)\s+(\d+)%",
        r"support\s+volume\s+(?:declined|dropped|fell)\s+(\d+)%",
        r"nps\s+(?:dropped|fell|declined)\s+from\s+(\d+)\s+to\s+(\d+)",
        r"nps\s+(?:is|was|dropped to|fell to)\s+(\d+)",
        r"(\d+)\s+new\s+competitors",
        r"headcount\s+(?:frozen|reduced|increased)",
        r"budget\s+(?:cut|reduced|frozen|increased)",
        r"(\d+)%\s+(?:increase|decrease|growth|decline)",
    ]
    for pattern in metric_patterns:
        matches = re.finditer(pattern, lower)
        for match in matches:
            entities["metrics"].append(match.group(0))
            break

    problem_keywords = ["declined", "dropped", "fell", "decreased", "increased", "issue", "problem", "challenge", "risk", "threat", "pressure", "gap", "bottleneck", "delay", "shortage"]
    for keyword in problem_keywords:
        if keyword in lower:
            context_window = re.search(rf"\b\w+\b.*\b{keyword}\b.*\b\w+\b", lower)
            if context_window:
                entities["problems"].append(keyword)
            break

    objective_keywords = ["goal", "objective", "target", "aim", "strategic", "priority", "focus area", "improve", "grow", "increase", "reduce", "optimise", "optimize"]
    for keyword in objective_keywords:
        if keyword in lower:
            entities["objectives"].append(keyword)
            break

    constraint_keywords = ["budget", "headcount", "resource", "timeline", "deadline", "restriction", "limit", "cap", "freeze", "constraint"]
    for keyword in constraint_keywords:
        if keyword in lower:
            entities["constraints"].append(keyword)
            break

    stakeholder_keywords = ["customer", "client", "team", "department", "board", "investor", "shareholder", "employee", "manager", "leadership", "executive"]
    for keyword in stakeholder_keywords:
        if keyword in lower:
            entities["stakeholders"].append(keyword)
            break

    time_keywords = ["q1", "q2", "q3", "q4", "quarter", "month", "year", "week", "today", "tomorrow", "next month", "next quarter", "next year", "annual", "monthly", "quarterly"]
    for keyword in time_keywords:
        if keyword in lower:
            entities["time_period"] = keyword
            break

    return entities


def _merge_analysis_entities(new: dict[str, Any], accumulated: dict[str, Any]) -> dict[str, Any]:
    merged = dict(accumulated)
    for key, value in new.items():
        if value is None:
            continue
        if key in ("metrics", "problems", "objectives", "constraints", "stakeholders", "supporting_signals"):
            existing = merged.get(key, [])
            if isinstance(existing, list) and isinstance(value, list):
                merged[key] = existing + [v for v in value if v not in existing]
            else:
                merged[key] = value
        elif key == "_request_text":
            continue
        else:
            if key in merged and merged[key] is not None and merged[key] != value:
                merged[key] = value
            else:
                merged[key] = value
    return merged


def _analysis_is_sufficient(entities: dict[str, Any], request_text: str = "") -> tuple[bool, str | None]:
    """Determine whether an analysis request has enough context to proceed."""
    goal = entities.get("goal")
    if goal is None:
        lower_request = request_text.lower()
        generic_indicators = [
            "analyse this",
            "analyze this",
            "analyse this document",
            "analyze this document",
            "review this",
            "review this document",
        ]
        if any(indicator in lower_request for indicator in generic_indicators):
            goal_indicators = [
                "what should i focus on",
                "what should we focus on",
                "what do i focus on",
                "what do we focus on",
                "what i should focus on",
                "what we should focus on",
                "what should i prioritise",
                "what should we prioritise",
                "what should i prioritize",
                "what should we prioritize",
                "biggest risks",
                "find opportunities",
                "why performance has",
                "deteriorated",
                "investigate next",
                "limit growth",
                "improve growth",
                "what needs attention",
                "causing the problem",
            ]
            if not any(phrase in lower_request for phrase in goal_indicators):
                return False, "What would you like the analysis to help you determine?"

    if entities.get("subject") is None and not entities.get("metrics") and not entities.get("problems"):
        return False, "What area of the business would you like me to analyse?"
    if entities.get("analysis_type") is None:
        return False, "Are you looking for a business analysis, or is this a different type of review?"
    return True, None


_GOAL_UNDERSTANDING = {
    "identify_focus_areas": "Identify the business issues most worthy of management attention.",
    "identify_risks": "Identify the biggest risks to the business.",
    "identify_opportunities": "Identify the biggest opportunities for the business.",
    "explain_deterioration": "Explain why performance has deteriorated.",
    "identify_investigation_areas": "Identify what should be investigated next.",
    "identify_growth_constraints": "Identify the three things most likely to limit growth over the next 12 months.",
    "identify_growth_opportunities": "Identify the biggest opportunities to improve growth.",
    "identify_attention_areas": "Identify what needs attention.",
    "identify_root_cause": "Identify what is causing the problem.",
}


def _build_proposed_understanding(entities: dict[str, Any], analysis_ctx: dict[str, Any]) -> str:
    """Build a human-readable proposed understanding from analysis entities."""
    parts: list[str] = []
    understanding = analysis_ctx.get("understanding")
    if understanding:
        parts.append(f"I understand you want to {understanding.lower()}.")

    subject = entities.get("subject")
    if subject:
        parts.append(f"Subject: {subject}.")

    metrics = entities.get("metrics", [])
    if metrics:
        parts.append(f"Key metrics: {', '.join(metrics)}.")

    problems = entities.get("problems", [])
    if problems:
        parts.append(f"Problem indicators: {', '.join(problems)}.")

    objectives = entities.get("objectives", [])
    if objectives:
        parts.append(f"Objectives: {', '.join(objectives)}.")

    constraints = entities.get("constraints", [])
    if constraints:
        parts.append(f"Constraints: {', '.join(constraints)}.")

    stakeholders = entities.get("stakeholders", [])
    if stakeholders:
        parts.append(f"Stakeholders: {', '.join(stakeholders)}.")

    time_period = entities.get("time_period")
    if time_period:
        parts.append(f"Time period: {time_period}.")

    if not parts:
        parts.append("I have enough information to proceed with a general business analysis.")

    parts.append("Is this correct?")
    return " ".join(parts)


def _identify_relationships_and_focus(entities: dict[str, Any], document_text: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Identify relationships between evidence and produce prioritised focus areas with four-level confidence."""
    relationships: list[dict[str, Any]] = []
    focus_areas: list[dict[str, Any]] = []

    customer_metrics = []
    operational_metrics = []
    revenue_metrics = []
    competitive_metrics = []

    for metric in entities.get("metrics", []):
        lower = metric.lower()
        if any(kw in lower for kw in ["retention", "nps", "customer", "churn"]):
            customer_metrics.append(metric)
        elif any(kw in lower for kw in ["support", "response time", "operational", "headcount"]):
            operational_metrics.append(metric)
        elif any(kw in lower for kw in ["revenue", "profit", "sales"]):
            revenue_metrics.append(metric)
        elif any(kw in lower for kw in ["competitor", "competition", "market"]):
            competitive_metrics.append(metric)

    if len(customer_metrics) >= 2:
        relationships.append({
            "signals": customer_metrics,
            "interpretation": "These customer-related changes may indicate an underlying customer experience issue rather than three independent problems.",
            "level": "inferred",
        })

    if revenue_metrics and customer_metrics:
        relationships.append({
            "signals": revenue_metrics + customer_metrics,
            "interpretation": "Revenue decline coincides with customer health deterioration, suggesting revenue impact may be driven by customer loss rather than market conditions alone.",
            "level": "inferred",
        })

    if len(operational_metrics) >= 2:
        relationships.append({
            "signals": operational_metrics,
            "interpretation": "Operational metrics suggest capacity or process issues that may be amplifying customer dissatisfaction.",
            "level": "inferred",
        })

    if competitive_metrics and revenue_metrics:
        relationships.append({
            "signals": competitive_metrics + revenue_metrics,
            "interpretation": "Revenue decline coincides with new competitive entrants, suggesting market pressure may be contributing to the downturn.",
            "level": "hypothesis",
        })

    theme_scores = {
        "customer_experience": len(customer_metrics),
        "operational_capacity": len(operational_metrics),
        "revenue_protection": len(revenue_metrics) + (1 if customer_metrics else 0),
        "competitive_response": len(competitive_metrics),
    }

    goal = entities.get("goal")
    if goal == "identify_growth_opportunities":
        theme_scores["growth_opportunity"] = theme_scores.get("customer_experience", 0) + theme_scores.get("revenue_protection", 0)
    if goal == "identify_root_cause":
        theme_scores["operational_capacity"] += 2

    sorted_themes = sorted(theme_scores.items(), key=lambda x: x[1], reverse=True)

    focus_area_definitions = {
        "customer_experience": {
            "name": "Customer retention and experience",
            "evidence": customer_metrics,
            "why": "Multiple customer health indicators are moving in the same direction, suggesting a systemic issue rather than isolated incidents.",
            "validate": ["Churn reasons by customer cohort", "Support-ticket categories", "Retention by customer segment"],
            "possible_actions": ["Run exit-interview analysis", "Segment NPS by customer tier", "Review onboarding experience"],
        },
        "operational_capacity": {
            "name": "Operational capacity and responsiveness",
            "evidence": operational_metrics,
            "why": "Increased support demand combined with slower response times indicates the team may be stretched beyond sustainable capacity.",
            "validate": ["Support ticket volume trends", "Team capacity and headcount plans", "First-response time by issue type"],
            "possible_actions": ["Review support staffing model", "Introduce tiered support", "Automate common queries"],
        },
        "revenue_protection": {
            "name": "Revenue protection and renewal management",
            "evidence": revenue_metrics + customer_metrics,
            "why": "Revenue decline is occurring alongside customer health deterioration, which may indicate that retention rather than acquisition is the primary driver.",
            "validate": ["Revenue by retained vs lost customers", "Renewal rates by cohort", "Pipeline coverage and conversion rates"],
            "possible_actions": ["Focus renewal playbook on at-risk accounts", "Review pricing competitiveness", "Strengthen customer success coverage"],
        },
        "competitive_response": {
            "name": "Competitive positioning",
            "evidence": competitive_metrics,
            "why": "New market entrants may be accelerating customer attrition or price compression.",
            "validate": ["Competitive feature comparison", "Win/loss analysis", "Pricing sensitivity by segment"],
            "possible_actions": ["Refresh competitive battle cards", "Run win/loss interviews", "Review pricing tiers"],
        },
        "growth_opportunity": {
            "name": "Growth opportunity",
            "evidence": customer_metrics + revenue_metrics,
            "why": "Existing customer base and revenue patterns may contain untapped growth potential.",
            "validate": ["Upsell/cross-sell conversion rates", "Expansion revenue by segment", "Product adoption by tier"],
            "possible_actions": ["Identify expansion revenue gaps", "Test premium tier features", "Launch referral program"],
        },
    }

    for theme, score in sorted_themes:
        if score > 0 and theme in focus_area_definitions:
            definition = focus_area_definitions[theme]
            if score >= 3:
                confidence = "known"
                confidence_label = "KNOWN"
            elif score >= 2:
                confidence = "inferred"
                confidence_label = "INFERRED"
            else:
                confidence = "hypothesis"
                confidence_label = "HYPOTHESIS"
            focus_areas.append({
                "name": definition["name"],
                "evidence": definition["evidence"],
                "why": definition["why"],
                "confidence": confidence,
                "confidence_label": confidence_label,
                "validate": definition["validate"],
                "possible_actions": definition["possible_actions"],
            })

    return relationships, focus_areas


def _build_analysis_context(entities: dict[str, Any], document_text: str | None = None) -> dict[str, Any]:
    """Build enriched analysis context from extracted entities with goal-driven branching."""
    goal = entities.get("goal")
    understood_as = _GOAL_UNDERSTANDING.get(goal, entities.get("subject") or "business situation analysis")
    if not understood_as and entities.get("subject"):
        understood_as = f"Analyse {entities['subject']}"

    context: dict[str, Any] = {
        "analysis_type": entities.get("analysis_type", "business_analysis"),
        "subject": entities.get("subject"),
        "goal": goal,
        "understanding": understood_as,
        "constraints": {},
        "assumptions": [],
        "known_facts": [],
        "inferred": [],
        "relationships": [],
        "focus_areas": [],
        "validation_evidence": [],
        "hypotheses": [],
        "evidence": [],
        "validation_criteria": [],
        "possible_actions": [],
        "confidence": "low",
    }

    for metric in entities.get("metrics", []):
        context["known_facts"].append(f"Metric: {metric}")

    for problem in entities.get("problems", []):
        context["known_facts"].append(f"Problem indicator: {problem}")

    for objective in entities.get("objectives", []):
        context["known_facts"].append(f"Objective signal: {objective}")

    for constraint in entities.get("constraints", []):
        context["known_facts"].append(f"Constraint: {constraint}")

    for stakeholder in entities.get("stakeholders", []):
        context["known_facts"].append(f"Stakeholder: {stakeholder}")

    if entities.get("time_period"):
        context["known_facts"].append(f"Time period: {entities['time_period']}")
        context["constraints"]["time_period"] = entities["time_period"]

    if entities.get("subject"):
        context["constraints"]["subject"] = entities["subject"]

    if entities.get("supporting_signals"):
        context["inferred"] = entities["supporting_signals"]

    relationships, focus_areas = _identify_relationships_and_focus(entities, document_text)
    context["relationships"] = relationships
    context["focus_areas"] = focus_areas

    all_hypotheses: list[str] = []
    all_evidence: list[str] = []
    all_validation_criteria: list[str] = []
    all_possible_actions: list[str] = []
    max_confidence = "low"

    for area in focus_areas:
        area_name = area.get("name", "")
        area_evidence = area.get("evidence", [])
        area_validate = area.get("validate", [])
        area_actions = area.get("possible_actions", [])
        area_confidence = area.get("confidence", "hypothesis")
        area_confidence_label = area.get("confidence_label", "HYPOTHESIS")

        context["validation_evidence"].extend(area_validate)

        if area_confidence == "known":
            max_confidence = "high"
        elif area_confidence == "inferred" and max_confidence != "high":
            max_confidence = "medium"
        elif area_confidence == "hypothesis" and max_confidence == "low":
            max_confidence = "low"

        hypothesis_text = f"{area_name} ({area_confidence_label}): {area.get('why', '')}"
        if hypothesis_text not in all_hypotheses:
            all_hypotheses.append(hypothesis_text)

        all_evidence.extend([e for e in area_evidence if e not in all_evidence])
        all_validation_criteria.extend([v for v in area_validate if v not in all_validation_criteria])
        all_possible_actions.extend([a for a in area_actions if a not in all_possible_actions])

        if goal == "identify_root_cause":
            causal_hypothesis = f"Possible root cause of {area_name.lower()}: {area.get('why', '')}"
            if causal_hypothesis not in all_hypotheses:
                all_hypotheses.append(causal_hypothesis)

    context["hypotheses"] = all_hypotheses
    context["evidence"] = all_evidence
    context["validation_criteria"] = all_validation_criteria
    context["possible_actions"] = all_possible_actions
    context["confidence"] = max_confidence

    goal_ordering = {
        "identify_focus_areas": ["customer_experience", "revenue_protection", "operational_capacity", "competitive_response"],
        "identify_risks": ["competitive_response", "operational_capacity", "revenue_protection", "customer_experience"],
        "identify_opportunities": ["growth_opportunity", "customer_experience", "revenue_protection", "operational_capacity"],
        "explain_deterioration": ["revenue_protection", "operational_capacity", "customer_experience", "competitive_response"],
        "identify_root_cause": ["operational_capacity", "customer_experience", "revenue_protection", "competitive_response"],
    }
    preferred_order = goal_ordering.get(goal, [])
    if preferred_order:
        def area_sort_key(area):
            area_name_lower = area.get("name", "").lower()
            for idx, key in enumerate(preferred_order):
                if key.replace("_", " ") in area_name_lower or key in area_name_lower:
                    return idx
            return len(preferred_order)
        context["focus_areas"] = sorted(context["focus_areas"], key=area_sort_key)

    if not entities.get("subject") and entities.get("metrics"):
        context["assumptions"].append("The focus is on the business area indicated by the supplied metrics.")
    if not entities.get("objectives"):
        context["assumptions"].append("The objective is to identify areas for management attention rather than simply summarise the document.")
    if not entities.get("constraints"):
        context["assumptions"].append("No specific constraints have been stated; analysis will consider general business trade-offs.")

    return context


def _planning_is_sufficient(entities: dict[str, Any], document_provides_subject: bool = False) -> tuple[bool, str | None]:
    """Determine whether a planning request has enough information to proceed."""
    if entities.get("subject") is None:
        return False, "What kind of event or activity are you planning?"
    if entities.get("is_definite_reference") and not document_provides_subject:
        return False, "What kind of event are you planning?"
    return True, None


def _build_planning_assumptions(entities: dict[str, Any]) -> list[str]:
    """Build a list of reasonable assumptions for unspecified planning details."""
    assumptions = []
    if not entities.get("venue"):
        assumptions.append("No specific venue has been provided; the plan will use a general venue-selection approach.")
    if not entities.get("budget"):
        assumptions.append("No budget has been provided; the plan will include general cost considerations.")
    if not entities.get("date"):
        assumptions.append("No specific date has been provided; the plan will use a standard timeline approach.")
    if not entities.get("people_count"):
        assumptions.append("No guest count has been provided; the plan will use a general-scale approach.")
    if entities.get("activity_type") == "outdoor activity":
        assumptions.append("This is treated as a recreational outdoor activity unless stated otherwise.")
        assumptions.append("Existing accommodation arrangements are assumed to be confirmed.")
        assumptions.append("The plan should cover preparation, daily itinerary, logistics, equipment and contingencies.")
    return assumptions


def _build_planning_context(entities: dict[str, Any]) -> dict[str, Any]:
    """Build enriched planning context from extracted entities."""
    context: dict[str, Any] = {
        "planning_type": entities.get("activity_type", "event"),
        "subject": entities.get("subject"),
        "constraints": {},
        "assumptions": _build_planning_assumptions(entities),
        "understood_as": entities.get("subject"),
        "known_facts": [],
        "inferred": [],
    }

    if entities.get("people_count"):
        context["constraints"]["people_count"] = entities["people_count"]
        context["known_facts"].append(f"{entities['people_count']} participant(s)")
    if entities.get("venue"):
        context["constraints"]["venue"] = entities["venue"]
        context["known_facts"].append(f"Location: {entities['venue']}")
    if entities.get("budget"):
        context["constraints"]["budget"] = entities["budget"]
        context["known_facts"].append(f"Budget: ${entities['budget']}")
    if entities.get("date"):
        context["constraints"]["date"] = entities["date"]
        context["known_facts"].append(f"Date: {entities['date']}")
    if entities.get("duration_days"):
        context["constraints"]["duration_days"] = entities["duration_days"]
        context["known_facts"].append(f"Duration: {entities['duration_days']} days")
    if entities.get("distance_km"):
        context["constraints"]["distance_km"] = entities["distance_km"]
        context["known_facts"].append(f"Daily distance: {entities['distance_km']} km")

    if entities.get("supporting_signals"):
        context["inferred"] = entities["supporting_signals"]

    return context

    if entities.get("people_count"):
        context["constraints"]["people_count"] = entities["people_count"]
    if entities.get("venue"):
        context["constraints"]["venue"] = entities["venue"]
    if entities.get("budget"):
        context["constraints"]["budget"] = entities["budget"]
    if entities.get("date"):
        context["constraints"]["date"] = entities["date"]

    return context


class AssistantChatService:
    """Application-layer translation service bridging natural language to domain planes."""

    def __init__(
        self,
        reasoning_service: AssistantReasoningService | None = None,
        capability_discovery: CapabilityDiscoveryPort | None = None,
        capability_execution: CapabilityExecutionPort | None = None,
        enterprise_information: EnterpriseInformationPort | None = None,
        organisational_context: OrganisationalContextPort | None = None,
        work_management: WorkManagementPort | None = None,
        session_factory: SessionFactoryPort | None = None,
        pattern_execution: PatternExecutionPort | None = None,
        capability_selection_telemetry: Any | None = None,
        enterprise_capability_query: EnterpriseCapabilityQueryPort | None = None,
        ai_response: AIResponseService | None = None,
    ) -> None:
        self._reasoning = reasoning_service or AssistantReasoningService()
        self._capability_discovery = capability_discovery
        self._capability_execution = capability_execution
        self._enterprise_information = enterprise_information
        self._organisational_context = organisational_context
        self._work_management = work_management
        self._session_factory = session_factory
        self._pattern_execution = pattern_execution
        self._sessions: dict[str, SessionReference] = {}
        self._action_policy = CapabilityActionPolicy()
        self._capability_selection_telemetry = capability_selection_telemetry
        self._enterprise_capability_query = enterprise_capability_query
        self._ai_response = ai_response
        self._pending_planning_contexts: dict[str, dict[str, Any]] = {}
        self._analysis_contexts: dict[str, dict[str, Any]] = {}
        self._validation_contexts: dict[str, dict[str, Any]] = {}
        self._conversation_history: dict[str, list[dict[str, str]]] = {}
        self._pending_actionable_intents: dict[str, ActionableIntent] = {}

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Process a chat message and return a response."""
        intent = Intent(
            id=f"chat-{datetime.now(timezone.utc).timestamp()}",
            origin=IntentOrigin.USER_REQUEST,
            raw={"type": "natural_language", "text": request.message},
            declared_context=request.context,
        )

        frame = recognise(intent)
        session_id = request.session_id or f"ses-{intent.id}"

        if self._enterprise_information is not None:
            strategy_tag = f"strategy:{self._strategy_from_frame(frame)}"
            previous = self._enterprise_information.find_previous_solutions(strategy_tag)
            if previous is not None:
                return ChatResponse(
                    message=f"I've done this before. Last time: {previous.summary}. Want me to reuse that?",
                    session_id=session_id,
                    status="awaiting_confirmation",
                    reasoning=f"Found previous solution for {strategy_tag}",
                    previous_solution=previous.model_dump(),
                    telemetry={"match_type": "concept_lookup"},
                )

        if self._capability_discovery is not None:
            candidates = self._capability_discovery.find_capabilities(
                request_text=request.message,
                context=frame.context,
            )

            enterprise_response = self._evaluate_enterprise_action(candidates, intent, frame, session_id)
            if enterprise_response is not None:
                return enterprise_response

            action = self._action_policy.decide(candidates, request.context)
            if isinstance(action, ExecuteCapability):
                return self._execute_capability_response(intent, frame, action.candidate, session_id)
            if isinstance(action, AskUserToSelect):
                return self._capability_selection_response(intent, frame, action.candidates, action.interaction, session_id)
            # NoCapabilityMatch falls through to pattern execution

        if self._ai_response is not None and self._is_clearly_conversational(request.message):
            actionable_response = self._check_actionable_intent(request, session_id, frame)
            if actionable_response is not None:
                return actionable_response
            try:
                history = self._conversation_history.get(session_id, [])
                ai_message, ai_telemetry = self._ai_response.generate(
                    user_message=request.message,
                    context=request.context,
                    conversation_history=list(history),
                )
                self._append_conversation_turn(session_id, request.message, ai_message)
                return ChatResponse(
                    message=ai_message,
                    session_id=session_id,
                    status="completed",
                    reasoning="Generated by AI via Portkey",
                    telemetry={"runtime": "ai_response_service", "model": self._ai_response.model, **ai_telemetry},
                )
            except Exception as exc:
                logger.warning("AI response generation failed: %s", exc)

        decision = self._reasoning.decide(intent)

        session = None
        if self._session_factory is not None:
            session = self._session_factory.create_session(
                strategy=decision.chosen_strategy.value,
                pattern_pipeline=decision.pattern_pipeline,
                context=request.context,
            )
            self._sessions[session.session_id] = session

        if session is not None and session.pipeline and self._pattern_execution is not None:
            pattern_request = PatternExecutionRequest(
                session_id=session.session_id,
                pattern_step={
                    "pattern_id": decision.pattern_pipeline[0] if decision.pattern_pipeline else "default",
                    "ordered_steps": [
                        {
                            "step_id": step_id,
                            "role": "assistant",
                            "tools": [],
                            "gate_condition": None,
                        }
                        for step_id in session.pipeline
                    ],
                },
                context=request.context,
                participants=[{"role": r} for r in decision.participant_roles],
                prompt=request.message,
            )
            response = self._pattern_execution.execute_pattern(pattern_request)

            if response.status == "waiting" and response.human_input_request:
                return ChatResponse(
                    message=response.human_input_request.get("question", "I need some input to proceed."),
                    session_id=session.session_id,
                    status="awaiting_human_input",
                    reasoning=decision.rationale,
                    human_input_request=response.human_input_request,
                    telemetry={"runtime": "pattern_execution_port"},
                )

            if response.status == "completed":
                if self._enterprise_information is not None:
                    self._enterprise_information.record_solution(
                        SolutionRecord(
                            summary=response.outputs.get("summary", ""),
                            outputs=response.outputs,
                            strategy=decision.chosen_strategy.value,
                            pattern_pipeline=decision.pattern_pipeline,
                        )
                    )
                return ChatResponse(
                    message=f"Done. {response.outputs.get('summary', 'Task completed successfully.')}",
                    session_id=session.session_id,
                    status="completed",
                    reasoning=decision.rationale,
                    telemetry={"runtime": "pattern_execution_port"},
                )

        # No pattern execution path available — delegate to the Organisation if possible
        if self._work_management is not None:
            planning_check = self._check_planning_context(intent, session_id)
            if planning_check is not None:
                return planning_check
            analysis_check = self._check_analysis_context(intent, session_id)
            if analysis_check is not None:
                return analysis_check
            return self._delegate_work_response(intent, frame, session_id)

        return ChatResponse(
            message=f"I'll help with that. Strategy: {decision.chosen_strategy.value}. Pipeline: {', '.join(decision.pattern_pipeline)}.",
            session_id=session.session_id if session else f"ses-{intent.id}",
            status="pending",
            reasoning=decision.rationale,
            telemetry={"runtime": "none", "reason": "no_pattern_execution_configured"},
        )

    def resume_with_human_input(self, session_id: str, human_response: dict[str, Any]) -> ChatResponse:
        """Resume a paused session with human input."""
        actionable = self._pending_actionable_intents.get(session_id)
        if actionable is not None:
            response_text = human_response.get("response", "").strip().lower()
            confirm_signals = [
                "yes", "correct", "confirm", "proceed", "ok", "execute",
                "that's right", "right", "good", "yep", "yeah", "go ahead", "please do",
            ]
            is_confirm = any(response_text.startswith(sig) for sig in confirm_signals) or response_text in confirm_signals
            if is_confirm:
                del self._pending_actionable_intents[session_id]
                intent = Intent(
                    id=f"chat-{datetime.now(timezone.utc).timestamp()}",
                    origin=IntentOrigin.USER_REQUEST,
                    raw={"type": "natural_language", "text": actionable.objective or actionable.action},
                    declared_context={"actionable_intent": actionable.model_dump()},
                )
                frame = recognise(intent)
                analysis_context = self._build_actionable_analysis_context(actionable)
                if self._work_management is not None:
                    return self._delegate_work_response(intent, frame, session_id, analysis_context=analysis_context)
                return ChatResponse(
                    message=f"Proceeding with {actionable.action}: {actionable.objective}.",
                    session_id=session_id,
                    status="pending",
                )
            self._pending_actionable_intents.pop(session_id, None)
            return ChatResponse(
                message="Understood. What would you like to do instead?",
                session_id=session_id,
                status="completed",
                reasoning="User rejected the proposed action.",
                telemetry={"actionable_intent_rejected": True},
            )

        pending = self._pending_planning_contexts.get(session_id)
        if pending is not None:
            response_text = human_response.get("response", "")
            merged_text = f"{pending['original_text']} {response_text}".strip()
            document_text = pending.get("document_text")
            intent = Intent(
                id=f"chat-{datetime.now(timezone.utc).timestamp()}",
                origin=IntentOrigin.USER_REQUEST,
                raw={"type": "natural_language", "text": merged_text},
                declared_context={**(human_response.get("context", {})), "input_text": document_text} if document_text else human_response.get("context", {}),
            )
            frame = recognise(intent)
            context_type = pending.get("context_type", "planning")
            if context_type == "analysis":
                entities = _extract_analysis_entities(merged_text, document_text)
                accumulated = self._analysis_contexts.get(session_id)
                if accumulated is not None:
                    entities = _merge_analysis_entities(entities, accumulated)
                analysis_ctx = _build_analysis_context(entities, document_text)
                intent.declared_context = {**(intent.declared_context or {}), "analysis_context": analysis_ctx}
                self._analysis_contexts[session_id] = entities
                del self._pending_planning_contexts[session_id]

                proposed = _build_proposed_understanding(entities, analysis_ctx)
                self._validation_contexts[session_id] = {
                    "entities": entities,
                    "analysis_context": analysis_ctx,
                    "document_text": document_text,
                    "proposed_understanding": proposed,
                    "original_request_text": merged_text,
                }
                return ChatResponse(
                    message=proposed,
                    session_id=session_id,
                    status="awaiting_validation",
                    reasoning=f"Analysis context is sufficient after clarification. Proposed understanding: {proposed}",
                    human_input_request={
                        "question": proposed,
                        "session_id": session_id,
                        "validation_type": "analysis_understanding",
                        "options": ["confirm", "clarify", "update", "contradict"],
                    },
                    telemetry={"analysis_validation": True, "proposed_understanding": proposed},
                )
            entities = _extract_planning_entities(merged_text, document_text)
            planning_ctx = _build_planning_context(entities)
            intent.declared_context = {**(intent.declared_context or {}), "planning_context": planning_ctx}
            del self._pending_planning_contexts[session_id]
            if self._work_management is not None:
                return self._delegate_work_response(intent, frame, session_id, planning_context=planning_ctx)
            return ChatResponse(
                message="I have enough information now, but work management is not configured.",
                session_id=session_id,
                status="pending",
            )

        validation = self._validation_contexts.get(session_id)
        if validation is not None:
            response_text = human_response.get("response", "").strip().lower()
            entities = validation["entities"]
            analysis_ctx = validation["analysis_context"]
            document_text = validation.get("document_text")

            confirm_signals = ["yes", "correct", "confirm", "proceed", "ok", "execute", "that's right", "right", "good", "yep", "yeah", "go ahead", "please do"]
            contradict_signals = ["no ", "actually", "wrong", "not ", "instead", "rather", "incorrect"]
            clarify_signals = ["?", "clarify", "explain", "what do you mean", "unclear"]

            is_confirm = any(response_text.startswith(sig) for sig in confirm_signals) or response_text in confirm_signals
            is_contradict = any(response_text.startswith(sig) for sig in contradict_signals) or any(sig in response_text for sig in contradict_signals)
            is_clarify = any(response_text.startswith(sig) for sig in clarify_signals) or "?" in response_text

            if is_confirm:
                del self._validation_contexts[session_id]
                original_text = validation.get("original_request_text", human_response.get("response", ""))
                intent = Intent(
                    id=f"chat-{datetime.now(timezone.utc).timestamp()}",
                    origin=IntentOrigin.USER_REQUEST,
                    raw={"type": "natural_language", "text": original_text},
                    declared_context=human_response.get("context", {}),
                )
                frame = recognise(intent)
                if self._work_management is not None:
                    return self._delegate_work_response(intent, frame, session_id, analysis_context=analysis_ctx)
                return ChatResponse(
                    message="Proceeding with the analysis.",
                    session_id=session_id,
                    status="pending",
                )

            if is_contradict:
                new_text = human_response.get("response", "")
                new_entities = _extract_analysis_entities(new_text, document_text)
                accumulated = self._analysis_contexts.get(session_id)
                if accumulated is not None:
                    new_entities = _merge_analysis_entities(new_entities, accumulated)
                new_ctx = _build_analysis_context(new_entities, document_text)
                self._analysis_contexts[session_id] = new_entities
                proposed = _build_proposed_understanding(new_entities, new_ctx)
                self._validation_contexts[session_id] = {
                    "entities": new_entities,
                    "analysis_context": new_ctx,
                    "document_text": document_text,
                    "proposed_understanding": proposed,
                    "original_request_text": new_text,
                }
                return ChatResponse(
                    message=f"Understood. Revised understanding:\n\n{proposed}",
                    session_id=session_id,
                    status="awaiting_validation",
                    reasoning="Contradiction detected. Revised analysis context.",
                    human_input_request={
                        "question": proposed,
                        "session_id": session_id,
                        "validation_type": "analysis_understanding",
                        "options": ["confirm", "clarify", "update", "contradict"],
                    },
                    telemetry={"analysis_validation": True, "revision": "contradiction", "proposed_understanding": proposed},
                )

            if is_clarify:
                self._pending_planning_contexts[session_id] = {
                    "original_text": human_response.get("response", ""),
                    "document_text": document_text,
                    "entities": entities,
                    "question": "What would you like me to clarify?",
                    "context_type": "analysis",
                }
                del self._validation_contexts[session_id]
                return ChatResponse(
                    message="What would you like me to clarify?",
                    session_id=session_id,
                    status="awaiting_human_input",
                    reasoning="User requested clarification on the proposed understanding.",
                    human_input_request={"question": "What would you like me to clarify?", "session_id": session_id},
                    telemetry={"analysis_clarification": True},
                )

            update_text = human_response.get("response", "")
            original_text = validation.get("original_request_text", "")
            merged_text = f"{original_text} {update_text}".strip()
            updated_entities = _extract_analysis_entities(merged_text, document_text)
            accumulated = self._analysis_contexts.get(session_id)
            if accumulated is not None:
                updated_entities = _merge_analysis_entities(updated_entities, accumulated)
            updated_ctx = _build_analysis_context(updated_entities, document_text)
            self._analysis_contexts[session_id] = updated_entities
            proposed = _build_proposed_understanding(updated_entities, updated_ctx)
            self._validation_contexts[session_id] = {
                "entities": updated_entities,
                "analysis_context": updated_ctx,
                "document_text": document_text,
                "proposed_understanding": proposed,
                "original_request_text": merged_text,
            }
            return ChatResponse(
                message=f"Updated understanding:\n\n{proposed}",
                session_id=session_id,
                status="awaiting_validation",
                reasoning="Context updated with new information.",
                human_input_request={
                    "question": proposed,
                    "session_id": session_id,
                    "validation_type": "analysis_understanding",
                    "options": ["confirm", "clarify", "update", "contradict"],
                },
                telemetry={"analysis_validation": True, "revision": "update", "proposed_understanding": proposed},
            )

        investigation_mode = human_response.get("investigation", False)
        if investigation_mode:
            accumulated_entities = self._analysis_contexts.get(session_id)
            if accumulated_entities is not None:
                document_text = validation.get("document_text") if validation else None
                analysis_ctx = _build_analysis_context(accumulated_entities, document_text)
                investigation_text = human_response.get("response", "")
                new_entities = _extract_analysis_entities(investigation_text, document_text)
                if new_entities.get("goal"):
                    accumulated_entities = _merge_analysis_entities(new_entities, accumulated_entities)
                    self._analysis_contexts[session_id] = accumulated_entities
                    updated_ctx = _build_analysis_context(accumulated_entities, document_text)
                    proposed = _build_proposed_understanding(accumulated_entities, updated_ctx)
                    self._validation_contexts[session_id] = {
                        "entities": accumulated_entities,
                        "analysis_context": updated_ctx,
                        "document_text": document_text,
                        "proposed_understanding": proposed,
                        "original_request_text": investigation_text,
                    }
                    return ChatResponse(
                        message=f"Understood. Revised understanding:\n\n{proposed}",
                        session_id=session_id,
                        status="awaiting_validation",
                        reasoning="Investigation follow-up revised analysis context.",
                        human_input_request={
                            "question": proposed,
                            "session_id": session_id,
                            "validation_type": "analysis_understanding",
                            "options": ["confirm", "clarify", "update", "contradict"],
                        },
                        telemetry={"analysis_validation": True, "revision": "investigation", "proposed_understanding": proposed},
                    )
                return ChatResponse(
                    message=f"Continuing investigation: {investigation_text}\n\nBased on the existing analysis, here are the key areas to explore further:\n\n" + "\n".join([f"- {h}" for h in analysis_ctx.get("hypotheses", [])]),
                    session_id=session_id,
                    status="completed",
                    reasoning="Investigation follow-up using existing analysis context.",
                    telemetry={"investigation": True, "follow_up": investigation_text},
                    execution_outputs={"analysis_context": analysis_ctx} if analysis_ctx else None,
                )
            return ChatResponse(
                message="No previous analysis context found. Please start with an analysis first.",
                session_id=session_id,
                status="pending",
            )

        if self._pattern_execution is not None:
            response = self._pattern_execution.resume_pattern(session_id, human_response)
            if response.status == "completed":
                return ChatResponse(
                    message=f"Done. {response.outputs.get('summary', 'Task completed successfully.')}",
                    session_id=session_id,
                    status="completed",
                    telemetry={"runtime": "pattern_execution_port", "resumed": True},
                )

        return ChatResponse(
            message="Session resumed.",
            session_id=session_id,
            status="completed",
            telemetry={"runtime": "none"},
        )

    def execute_selected_capability(
        self,
        capability_id: str,
        context: dict[str, Any],
    ) -> ExecutionResult:
        """Execute a capability selected by the caller."""
        if self._capability_execution is None:
            raise ValueError("CapabilityExecutionPort not configured")
        return self._capability_execution.execute(
            capability_id=capability_id,
            context=context,
            actor_context={},
        )

    def record_capability_feedback(
        self,
        match_event_id: str,
        user_action: str,
        selected_capability_id: str | None = None,
    ) -> None:
        """Record user feedback on a previously presented capability candidate set."""
        if self._capability_selection_telemetry is not None:
            self._capability_selection_telemetry.record_user_action(
                event_id=match_event_id,
                user_action=user_action,
                selected_capability_id=selected_capability_id,
            )

    def _is_clearly_conversational(self, text: str) -> bool:
        """MVP routing: return True when the message is general conversation.

        Explicit actionable requests (planning, analysis, document summarisation,
        capability execution) are routed to the deterministic path. Everything
        else is treated as conversational and sent to the LLM.
        """
        lower = text.lower().strip()

        planning_signals = [
            "plan the ", "plan a ", "plan this", "plan our ",
            "schedule ", "organise ", "organize ",
        ]
        if any(signal in lower for signal in planning_signals):
            return False

        analysis_signals = [
            "analyse ", "analyze ", "analysis ", "review this",
            "what should i focus on", "what should we focus on",
            "tell me what i should focus on",
        ]
        if any(signal in lower for signal in analysis_signals):
            return False

        document_signals = [
            "summarise this", "summarize this", "look at this and",
        ]
        if any(signal in lower for signal in document_signals):
            return False

        capability_signals = [
            "create a ", "build a ", "develop a ", "design a ",
            "implement a ", "write a ", "draft a ",
        ]
        if any(signal in lower for signal in capability_signals):
            return False

        return True

    def _append_conversation_turn(self, session_id: str, user_message: str, assistant_message: str) -> None:
        history = self._conversation_history.get(session_id)
        if history is None:
            history = []
            self._conversation_history[session_id] = history
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant_message})
        max_turns = 20
        max_messages = max_turns * 2
        if len(history) > max_messages:
            del history[: len(history) - max_messages]

    def _strategy_from_frame(self, frame: ProblemFrame) -> str:
        problem = frame.context.problem_context.value
        activity = frame.context.activity_purpose.value
        mapping = {
            ("innovation", "explore"): "research_to_synthesis",
            ("incident", "execute"): "investigate_then_fix",
            ("incident", "investigate"): "investigate_then_fix",
            ("design", "decide"): "deliberate_to_consensus",
            ("decision", "decide"): "deliberate_to_consensus",
            ("compliance", "validate"): "verify_and_assimilate",
            ("learning", "optimise"): "verify_and_assimilate",
            ("unknown", "investigate"): "research_to_synthesis",
            ("routine_operation", "execute"): "recognise_and_reuse",
            ("innovation", "decide"): "deliberate_to_consensus",
            ("compliance", "investigate"): "investigate_then_fix",
        }
        return mapping.get((problem, activity), "research_to_synthesis")

    def _get_accumulated_context(self, session_id: str) -> dict[str, Any]:
        accumulated: dict[str, Any] = {}
        planning = self._pending_planning_contexts.get(session_id)
        if planning:
            accumulated["planning"] = planning.get("original_text", "")
        analysis = self._analysis_contexts.get(session_id)
        if analysis:
            accumulated["analysis"] = analysis
        return accumulated

    def _check_actionable_intent(
        self,
        request: ChatRequest,
        session_id: str,
        frame: ProblemFrame,
    ) -> ChatResponse | None:
        if self._ai_response is None:
            return None
        history = self._conversation_history.get(session_id, [])
        if len(history) < 2:
            return None
        accumulated = self._get_accumulated_context(session_id)
        try:
            raw_intent = self._ai_response.classify_actionable_intent(
                user_message=request.message,
                conversation_history=list(history),
                accumulated_context=accumulated if accumulated else None,
            )
            intent = ActionableIntent.model_validate(raw_intent)
        except Exception as exc:
            logger.debug("Actionable intent classification failed: %s", exc)
            return None
        if intent.mode != "actionable" or not intent.action:
            return None
        self._pending_actionable_intents[session_id] = intent
        message = self._build_actionable_confirmation(intent)
        return ChatResponse(
            message=message,
            session_id=session_id,
            status="awaiting_confirmation",
            reasoning=f"AI detected actionable intent: {intent.action} — {intent.objective}",
            telemetry={
                "runtime": "ai_intent_classifier",
                "actionable_intent": intent.model_dump(),
            },
        )

    def _build_actionable_confirmation(self, intent: ActionableIntent) -> str:
        parts: list[str] = []
        if intent.objective:
            parts.append(f"I understand that you want to {intent.action}: {intent.objective}.")
        else:
            parts.append(f"I understand that you want to {intent.action}.")
        if intent.context:
            items = [f"{k}: {v}" for k, v in intent.context.items() if v]
            if items:
                parts.append(f"Based on our conversation, I'll use this evidence: {', '.join(items)}.")
        parts.append("Shall I proceed?")
        return " ".join(parts)

    def _build_actionable_analysis_context(self, intent: ActionableIntent) -> dict[str, Any]:
        context = dict(intent.context or {})
        context.setdefault("understanding", intent.objective or intent.action)
        context.setdefault("goal", intent.objective or intent.action)
        context.setdefault("analysis_type", "investigation")
        known_facts = []
        for key, value in context.items():
            if key not in ("understanding", "goal", "analysis_type") and value:
                known_facts.append(f"{key}: {value}")
        if known_facts:
            context.setdefault("known_facts", known_facts)
        return context

    def _execute_capability_response(
        self,
        intent: Intent,
        frame: ProblemFrame,
        candidate: CapabilityCandidate,
        session_id: str,
    ) -> ChatResponse:
        match_event = None
        if self._capability_selection_telemetry is not None:
            match_event = self._capability_selection_telemetry.record_match_event(
                request_text=intent.raw.get("text", ""),
                session_id=session_id,
                candidates=[candidate],
                interaction_type="confirm",
            )

        if self._capability_execution is None:
            telemetry = {
                "recognition_level": frame.recognition_level.value,
                "capability_id": candidate.id,
                "capability_name": candidate.name,
                "execution_mode": candidate.execution_mode,
            }
            if match_event is not None:
                telemetry["match_event_id"] = match_event.event_id
            return ChatResponse(
                message=f"I found a capability ({candidate.name}) but execution is not configured.",
                session_id=f"ses-{intent.id}",
                status="awaiting_capability_selection",
                reasoning=f"Capability {candidate.name} identified but no execution port available.",
                capability_candidates=[
                    {
                        "id": candidate.id,
                        "name": candidate.name,
                        "description": candidate.description,
                        "kind": candidate.kind,
                        "execution_mode": candidate.execution_mode,
                        "tags": candidate.tags,
                    }
                ],
                telemetry=telemetry,
            )

        result = self.execute_selected_capability(
            capability_id=candidate.id,
            context={},
        )

        if result.telemetry.get("error"):
            message = f"Execution failed: {result.outputs.get('error', result.telemetry['error'])}"
            status = "failed"
        else:
            outputs = result.outputs
            summary = outputs.get("summary") or outputs.get("result") or str(outputs)
            message = f"Executed {candidate.name}. Result: {summary}"
            if result.artifacts:
                message += f" Artifacts: {', '.join(result.artifacts)}"
            status = "completed"

        return ChatResponse(
            message=message,
            session_id=f"ses-{intent.id}",
            status=status,
            reasoning=f"Executed capability {candidate.name} ({candidate.kind}, {candidate.execution_mode})",
            telemetry={
                "recognition_level": frame.recognition_level.value,
                "capability_id": candidate.id,
                "capability_name": candidate.name,
                "execution_mode": candidate.execution_mode,
                "execution_error": result.telemetry.get("error"),
                **({"match_event_id": match_event.event_id} if match_event is not None else {}),
            },
            execution_outputs=result.outputs,
            execution_artifacts=result.artifacts,
        )

    def _capability_selection_response(
        self,
        intent: Intent,
        frame: ProblemFrame,
        candidates: list[CapabilityCandidate],
        interaction: str = "select",
        session_id: str | None = None,
    ) -> ChatResponse:
        """Build a response that exposes capability candidates for human selection or confirmation."""
        if interaction == "confirm" and len(candidates) == 1:
            message = (
                f"I found {candidates[0].name}. "
                f"Shall I proceed with this capability?"
            )
        else:
            message = (
                f"I found {len(candidates)} capabilities that might help. "
                f"Please select one to proceed, or tell me which one to run."
            )

        match_event = None
        if self._capability_selection_telemetry is not None:
            match_event = self._capability_selection_telemetry.record_match_event(
                request_text=intent.raw.get("text", ""),
                session_id=session_id,
                candidates=candidates,
                interaction_type=interaction,
            )

        telemetry = {
            "recognition_level": frame.recognition_level.value,
            "matcher": "human_selection",
            "candidate_count": len(candidates),
            "interaction": interaction,
        }
        if match_event is not None:
            telemetry["match_event_id"] = match_event.event_id

        return ChatResponse(
            message=message,
            session_id=session_id or f"ses-{intent.id}",
            status="awaiting_capability_selection",
            reasoning=(
                f"Recognised as {frame.context.problem_context.value} / "
                f"{frame.context.activity_purpose.value}. "
                f"{len(candidates)} capabilities available."
            ),
            capability_candidates=[
                {
                    "id": cap.id,
                    "name": cap.name,
                    "description": cap.description,
                    "kind": cap.kind,
                    "execution_mode": cap.execution_mode,
                    "tags": cap.tags,
                }
                for cap in candidates
            ],
            telemetry=telemetry,
        )

    def _check_planning_context(self, intent: Intent, session_id: str) -> ChatResponse | None:
        """Check whether a planning request has enough context to execute.

        Returns a ChatResponse with awaiting_human_input if clarification is needed,
        or None if execution should proceed.
        """
        request_text = intent.raw.get("text", "")
        lower = request_text.lower()

        planning_keywords = ["plan", "planning", "schedule", "organise", "organize"]
        if not any(keyword in lower for keyword in planning_keywords):
            return None

        document_text = intent.declared_context.get("input_text") if intent.declared_context else None
        document_entities = _extract_planning_entities(document_text) if document_text else {}
        entities = _extract_planning_entities(request_text, document_text)
        sufficient, question = _planning_is_sufficient(entities, bool(document_entities.get("subject")))
        if sufficient:
            planning_ctx = _build_planning_context(entities)
            intent.declared_context = {**(intent.declared_context or {}), "planning_context": planning_ctx}
            return None

        self._pending_planning_contexts[session_id] = {
            "original_text": request_text,
            "document_text": document_text,
            "entities": entities,
            "question": question,
        }
        return ChatResponse(
            message=question,
            session_id=session_id,
            status="awaiting_human_input",
            reasoning=f"Planning request needs clarification: {question}",
            human_input_request={"question": question, "session_id": session_id},
            telemetry={"planning_clarification": True, "pending_entities": entities},
        )

    def _check_analysis_context(self, intent: Intent, session_id: str) -> ChatResponse | None:
        """Check whether an analysis request has enough context to execute.

        Returns a ChatResponse with awaiting_human_input if clarification is needed,
        or None if execution should proceed.
        """
        request_text = intent.raw.get("text", "")
        lower = request_text.lower()

        pending = self._pending_planning_contexts.get(session_id)
        if pending is not None and pending.get("context_type") == "analysis":
            request_text = f"{pending['original_text']} {request_text}".strip()
            intent.raw = {**intent.raw, "text": request_text}
            document_text = pending.get("document_text")
            if document_text and not intent.declared_context.get("input_text"):
                intent.declared_context = {**(intent.declared_context or {}), "input_text": document_text}

        analysis_keywords = ["analyse", "analyze", "analysis", "review", "focus", "prioritise", "prioritize"]
        analysis_phrases = ["what should i focus on", "tell me what i should focus on", "what should we focus on"]
        is_analysis_request = any(keyword in lower for keyword in analysis_keywords) or any(phrase in lower for phrase in analysis_phrases)
        if not is_analysis_request:
            return None

        document_text = intent.declared_context.get("input_text") if intent.declared_context else None
        entities = _extract_analysis_entities(request_text, document_text)

        accumulated = self._analysis_contexts.get(session_id)
        if accumulated is not None:
            entities = _merge_analysis_entities(entities, accumulated)

        sufficient, question = _analysis_is_sufficient(entities, request_text)
        if sufficient:
            analysis_ctx = _build_analysis_context(entities, document_text)
            intent.declared_context = {**(intent.declared_context or {}), "analysis_context": analysis_ctx}
            self._analysis_contexts[session_id] = entities
            if pending is not None and pending.get("context_type") == "analysis":
                del self._pending_planning_contexts[session_id]

            proposed = _build_proposed_understanding(entities, analysis_ctx)
            self._validation_contexts[session_id] = {
                "entities": entities,
                "analysis_context": analysis_ctx,
                "document_text": document_text,
                "proposed_understanding": proposed,
                "original_request_text": request_text,
            }
            return ChatResponse(
                message=proposed,
                session_id=session_id,
                status="awaiting_validation",
                reasoning=f"Analysis context is sufficient. Proposed understanding: {proposed}",
                human_input_request={
                    "question": proposed,
                    "session_id": session_id,
                    "validation_type": "analysis_understanding",
                    "options": ["confirm", "clarify", "update", "contradict"],
                },
                telemetry={"analysis_validation": True, "proposed_understanding": proposed},
            )

        self._analysis_contexts[session_id] = entities
        self._pending_planning_contexts[session_id] = {
            "original_text": request_text,
            "document_text": document_text,
            "entities": entities,
            "question": question,
            "context_type": "analysis",
        }
        return ChatResponse(
            message=question,
            session_id=session_id,
            status="awaiting_human_input",
            reasoning=f"Analysis request needs clarification: {question}",
            human_input_request={"question": question, "session_id": session_id},
            telemetry={"analysis_clarification": True, "pending_entities": entities},
        )

    def _delegate_work_response(
        self,
        intent: Intent,
        frame: ProblemFrame,
        session_id: str,
        required_capability_ids: list[str] | None = None,
        planning_context: dict[str, Any] | None = None,
        analysis_context: dict[str, Any] | None = None,
    ) -> ChatResponse:
        """Delegate work to the Organisation via WorkManagementPort."""
        request_text = intent.raw.get("text", "")
        work_context = dict(intent.declared_context or {})
        if planning_context:
            work_context.setdefault("planning_context", planning_context)
        if analysis_context:
            work_context.setdefault("analysis_context", analysis_context)
        work_ref = self._work_management.create_work(
            WorkCreateRequest(
                title=request_text[:100],
                description=request_text,
                accountable_role_id="default",
                work_type="project",
                priority="normal",
                organisation_id="default",
                required_capability_ids=required_capability_ids or [],
                context=work_context,
            )
        )
        self._work_management.mark_ready(work_ref.work_id)
        updated_work = self._work_management.get_work(work_ref.work_id)
        outcome = updated_work.outcome if updated_work else None
        execution_outputs: dict[str, Any] | None = None
        if outcome and outcome.get("status") == "completed":
            summary = outcome.get("summary", "Task completed successfully.")
            message = f"Done. {summary}"
            status = "completed"
            if analysis_context:
                execution_outputs = {"analysis_context": analysis_context}
        elif outcome and outcome.get("status") == "failed":
            message = f"Failed: {outcome.get('error', 'Unknown error')}"
            status = "failed"
        else:
            message = f"I've delegated this to the Organisation. Work ID: {work_ref.work_id}. Status: {updated_work.status if updated_work else work_ref.status}."
            status = "delegated"
        return ChatResponse(
            message=message,
            session_id=session_id,
            status=status,
            reasoning=(
                f"No capability match. Delegated to Organisation as work "
                f"({frame.context.problem_context.value} / "
                f"{frame.context.activity_purpose.value})."
            ),
            telemetry={
                "recognition_level": frame.recognition_level.value,
                "work_id": work_ref.work_id,
                "work_status": updated_work.status if updated_work else work_ref.status,
                "delegated": True,
                "required_capability_ids": required_capability_ids or [],
            },
            execution_outputs=execution_outputs,
        )

    def _evaluate_enterprise_action(
        self,
        candidates: list[CapabilityCandidate],
        intent: Intent,
        frame: ProblemFrame,
        session_id: str,
    ) -> ChatResponse | None:
        """Evaluate whether the Organisation can handle this request.

        Returns a ChatResponse if the enterprise should act, otherwise None
        to allow fallback to pattern execution or other paths.
        """
        if self._enterprise_capability_query is None or not candidates:
            return None

        best_candidate = candidates[0]
        availability = self._enterprise_capability_query.query_capability(best_candidate.id)

        if availability is None:
            return self._handle_capability_gap(intent, frame, session_id, best_candidate)

        if not availability.available:
            return self._handle_unavailable_capability(intent, frame, session_id, availability)

        eta = availability.eta_seconds or 0
        if eta <= _FAST_ENTERPRISE_ETA_THRESHOLD_SECONDS:
            return self._handle_fast_capability(best_candidate.id, intent, frame, session_id)

        return self._handle_slow_capability(best_candidate.id, intent, frame, session_id, eta)

    def _handle_fast_capability(
        self,
        capability_id: str,
        intent: Intent,
        frame: ProblemFrame,
        session_id: str,
    ) -> ChatResponse:
        """Fast enterprise capability: delegate immediately."""
        return self._delegate_work_response(
            intent, frame, session_id, required_capability_ids=[capability_id]
        )

    def _handle_slow_capability(
        self,
        capability_id: str,
        intent: Intent,
        frame: ProblemFrame,
        session_id: str,
        eta_seconds: int,
    ) -> ChatResponse:
        """Slow enterprise capability: provide interim answer and delegate."""
        self._delegate_work_response(
            intent, frame, session_id, required_capability_ids=[capability_id]
        )
        return ChatResponse(
            message=(
                f"The enterprise can produce the proper answer for this, "
                f"but it will take approximately {eta_seconds} seconds. "
                f"I can give you a preliminary answer now while the enterprise work continues. "
                f"Work has been delegated to the Organisation."
            ),
            session_id=session_id,
            status="delegated_with_interim",
            reasoning=(
                f"Enterprise capability {capability_id} available but ETA {eta_seconds}s exceeds threshold. "
                f"Providing interim response while enterprise work proceeds."
            ),
            telemetry={
                "recognition_level": frame.recognition_level.value,
                "capability_id": capability_id,
                "eta_seconds": eta_seconds,
                "delegated": True,
                "interim": True,
            },
        )

    def _handle_unavailable_capability(
        self,
        intent: Intent,
        frame: ProblemFrame,
        session_id: str,
        availability: CapabilityAvailability,
    ) -> ChatResponse:
        """Capability exists but is currently unavailable."""
        return ChatResponse(
            message=(
                f"The enterprise has this capability, but it is currently unavailable. "
                f"{availability.reason}. "
                f"I can queue this work for when it becomes available."
            ),
            session_id=session_id,
            status="capability_unavailable",
            reasoning=(
                f"Capability exists but unavailable: {availability.reason}. "
                f"Assignee: {availability.assignee}."
            ),
            telemetry={
                "recognition_level": frame.recognition_level.value,
                "capability_id": availability.capability_id,
                "available": False,
                "assignee": availability.assignee,
                "reason": availability.reason,
            },
        )

    def _handle_capability_gap(
        self,
        intent: Intent,
        frame: ProblemFrame,
        session_id: str,
        candidate: CapabilityCandidate,
    ) -> ChatResponse:
        """Capability does not exist in the enterprise."""
        work_ref = None
        if self._work_management is not None:
            request_text = intent.raw.get("text", "")
            work_ref = self._work_management.create_work(
                WorkCreateRequest(
                    title=f"Develop capability: {candidate.name}",
                    description=(
                        f"Investigate and develop a capability for: {request_text}\n"
                        f"Missing capability: {candidate.name} ({candidate.id})"
                    ),
                    accountable_role_id="default",
                    work_type="capability_development",
                    priority="normal",
                    organisation_id="default",
                    required_capability_ids=[],
                )
            )

        message = (
            f"The enterprise does not currently have a capability for '{candidate.name}'. "
            f"I can provide a best-effort response"
        )
        if work_ref is not None:
            message += (
                f", and I've initiated work to develop this capability "
                f"(Work ID: {work_ref.work_id})"
            )
        message += "."

        return ChatResponse(
            message=message,
            session_id=session_id,
            status="capability_gap",
            reasoning=(
                f"No enterprise capability found for {candidate.id}. "
                f"This represents a capability gap. "
                f"{'Capability development work created: ' + work_ref.work_id if work_ref else 'No work management available.'}"
            ),
            telemetry={
                "recognition_level": frame.recognition_level.value,
                "capability_id": candidate.id,
                "capability_name": candidate.name,
                "gap": True,
                "work_created": work_ref is not None,
                "work_id": work_ref.work_id if work_ref else None,
            },
        )
