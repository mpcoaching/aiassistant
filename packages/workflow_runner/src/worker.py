"""
Minimal worker for operational execution (Increment 21Z).

Executes a work item and produces a tangible artifact.
This is an operational execution mechanism, NOT an organisational concept.

Design constraints:
- Worker obtains work from OrganisationControlPlane via public interface
- Work lifecycle is managed by the Organisation
- Results are reported back to the Organisation via public interface
- Paperclip and other execution backends remain behind operational adapters
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from role import Agent, Work, WorkStatus
from contracts.capability_execution import CapabilityExecutionPort, ExecutionResult


class Worker:
    """Minimal worker that executes assigned work from the Organisation."""

    DEFAULT_AGENT_ID = "worker-agent"
    DEFAULT_AGENT_NAME = "Default Worker"

    def __init__(
        self,
        output_dir: str = "worker_outputs",
        agent_id: str = DEFAULT_AGENT_ID,
        capability_execution: CapabilityExecutionPort | None = None,
        capability_registry: Any | None = None,
    ) -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._agent_id = agent_id
        self._capability_execution = capability_execution
        self._capability_registry = capability_registry

    def pickup(self, org_plane: Any) -> Work | None:
        """Pick up work assigned to this worker from the Organisation.

        Returns the first pending/assigned work item assigned to this worker's agent_id,
        or any unassigned work item if none is specifically assigned to this worker.
        """
        all_work = org_plane.list_work()
        for work in all_work:
            if work.status in (
                WorkStatus.PENDING,
                WorkStatus.ASSIGNED,
            ):
                if work.assignee_agent_id == self._agent_id or work.assignee_agent_id is None:
                    return work
        return None

    def execute(self, work: Work, org_plane: Any) -> dict[str, Any]:
        """Execute a work item and return the result.

        Uses only the public OrganisationControlPlane interface for
        assignment and capability registration. Result reporting
        (complete_work / fail_work) is handled by the caller (Operations).
        """
        if work.assignee_agent_id is None:
            worker_agent = Agent(id=self._agent_id, name=self.DEFAULT_AGENT_NAME)
            org_plane.assign_work(work, worker_agent)

        work.status = WorkStatus.IN_PROGRESS
        work.updated_at = datetime.now(UTC)

        try:
            if work.work_type == "capability_development":
                result = self._develop_capability(work, org_plane)
            elif work.required_capability_ids and self._capability_execution is not None:
                result = self._execute_capability(work)
            else:
                result = self._do_work(work)
            return result
        except Exception as exc:
            outcome = {
                "status": "failed",
                "error": str(exc),
                "summary": f"Worker failed: {exc}",
            }
            return outcome

    def _execute_capability(self, work: Work) -> dict[str, Any]:
        """Execute the capability referenced by the work item."""
        capability_id = work.required_capability_ids[0]
        actor_context = {
            "actor_id": self._agent_id,
            "actor_type": "agent",
        }
        execution_result: ExecutionResult = self._capability_execution.execute(
            capability_id=capability_id,
            context=work.context or {},
            actor_context=actor_context,
        )
        result = {
            "status": "completed",
            "execution_mode": "capability_execution_port",
            "capability_id": capability_id,
            "outputs": dict(execution_result.outputs),
            "artifacts": list(execution_result.artifacts),
            "telemetry": dict(execution_result.telemetry),
            "work_id": work.id,
            "title": work.title,
            "description": work.description,
        }
        return result

    def _develop_capability(self, work: Work, org_plane: Any) -> dict[str, Any]:
        """Develop a new capability from a capability-gap work item."""
        from capability import Capability, CapabilityKind, CapabilityStatus

        capability_id = f"cap-{work.id}"
        capability_name = work.title.replace("Develop capability: ", "").strip()
        capability = Capability(
            id=capability_id,
            name=capability_name,
            description=work.description,
            capability_kind=CapabilityKind.SKILL,
            status=CapabilityStatus.ACTIVE,
            owner=self._agent_id,
            created_by="worker",
            interface={
                "inputs": [{"name": "context", "type": "dict", "required": True}],
                "outputs": [{"name": "result", "type": "dict", "required": True}],
            },
        )

        org_plane.register_capability(capability)

        if self._capability_registry is not None:
            self._capability_registry.register(capability)

        artifact_path = self._write_capability_artifact(work.id, capability)

        return {
            "status": "completed",
            "execution_mode": "capability_development",
            "capability_id": capability_id,
            "capability_name": capability_name,
            "artifact_path": str(artifact_path),
            "work_id": work.id,
            "title": work.title,
            "description": work.description,
        }

    def _write_capability_artifact(
        self, work_id: str, capability: Any
    ) -> Path:
        """Write the capability development artifact to a file."""
        interface = capability.interface or {}
        if hasattr(interface, "inputs"):
            inputs = interface.inputs
            outputs = interface.outputs
        else:
            inputs = interface.get("inputs", [])
            outputs = interface.get("outputs", [])

        lines = [
            f"# Capability Development: {capability.name}",
            "",
            f"**Capability ID:** {capability.id}",
            f"**Kind:** {capability.capability_kind.value}",
            f"**Status:** {capability.status.value}",
            f"**Owner:** {capability.owner}",
            "",
            "## Purpose",
            capability.description or "No description provided.",
            "",
            "## Interface",
            "### Inputs",
        ]
        for inp in inputs:
            name = getattr(inp, "name", None)
            if name is None and hasattr(inp, "get"):
                name = inp.get("name", "?")
            if name is None:
                name = str(inp)
            type_ = getattr(inp, "type", None)
            if type_ is None and hasattr(inp, "get"):
                type_ = inp.get("type", "?")
            if type_ is None:
                type_ = "?"
            lines.append(f"- {name} ({type_})")
        lines.extend([
            "",
            "### Outputs",
        ])
        for out in outputs:
            name = getattr(out, "name", None)
            if name is None and hasattr(out, "get"):
                name = out.get("name", "?")
            if name is None:
                name = str(out)
            type_ = getattr(out, "type", None)
            if type_ is None and hasattr(out, "get"):
                type_ = out.get("type", "?")
            if type_ is None:
                type_ = "?"
            lines.append(f"- {name} ({type_})")
        lines.extend([
            "",
            "## Development Evidence",
            f"This capability was developed by {self._agent_id} in response to a capability gap.",
            f"Development work ID: {work_id}",
            "",
            "---",
            f"*Generated at {datetime.now(UTC).isoformat()}*",
        ])
        content = "\n".join(lines)
        safe_name = capability.name.lower().replace(" ", "-")[:30]
        filename = f"{work_id}-{safe_name}.md"
        output_path = self._output_dir / filename
        output_path.write_text(content, encoding="utf-8")
        return output_path

    def _do_work(self, work: Work) -> dict[str, Any]:
        """Perform the actual work.

        Routes to a content-specific generator based on the inferred intent.
        If input_text is provided in work.context, generates a summary of that text.
        """
        context = work.context or {}
        input_text = context.get("input_text")
        text = f"{work.title} {work.description or ''}"
        intent = self._infer_intent(text)

        if input_text and intent == "Content summarisation":
            output = self._summarise_text(work, input_text)
        elif intent == "Planning request":
            planning_context = (work.context or {}).get("planning_context")
            output = self._generate_action_plan(work, text, self._extract_key_phrases(text), self._suggest_actions(work, intent), planning_context=planning_context)
        elif intent == "Content creation":
            output = self._generate_proposal(work, text)
        elif intent == "Comparison":
            output = self._generate_comparison(work, text)
        elif intent == "Brainstorming":
            output = self._generate_ideas(work, text)
        elif intent == "Meeting actions":
            output = self._generate_actions(work, text)
        elif intent in ("Explanation request", "Content analysis"):
            analysis_context = (work.context or {}).get("analysis_context")
            output = self._generate_analysis(work, text, analysis_context=analysis_context)
        else:
            output = self._generate_ideas(work, text)

        output_path = self._write_output(work.id, work.title, output)

        return {
            "status": "completed",
            "summary": output,
            "output_path": str(output_path),
            "output_type": "markdown",
            "work_id": work.id,
            "title": work.title,
            "description": work.description,
        }

    def _generate_summary(self, work: Work) -> str:
        """Generate a structured analysis of the work request."""
        text = f"{work.title} {work.description or ''}"
        words = text.split()
        word_count = len(words)
        key_phrases = self._extract_key_phrases(text)
        intent = self._infer_intent(text)
        suggestions = self._suggest_actions(work, intent)

        if intent == "Planning request":
            return self._generate_action_plan(work, text, key_phrases, suggestions)

        lines = [
            f"# Work Analysis: {work.title}",
            "",
            "## Request Summary",
            f"- **Work ID:** {work.id}",
            f"- **Type:** {work.work_type}",
            f"- **Priority:** {work.priority}",
            f"- **Word count:** {word_count}",
            "",
            "## Inferred Intent",
            f"- {intent}",
            "",
            "## Key Phrases",
        ]
        if key_phrases:
            for phrase in key_phrases:
                lines.append(f"- {phrase}")
        else:
            lines.append("- (no significant phrases detected)")
        lines.extend([
            "",
            "## Suggested Actions",
        ])
        for suggestion in suggestions:
            lines.append(f"- {suggestion}")
        lines.extend([
            "",
            "## Result",
            "This work item was processed by the minimal Organisation worker.",
            f"The analysis has been written to `worker_outputs/{work.id}.md`.",
            "",
            "---",
            f"*Generated at {datetime.now(UTC).isoformat()}*",
        ])
        return "\n".join(lines)

    def _generate_action_plan(self, work: Work, text: str, key_phrases: list[str], suggestions: list[str], planning_context: dict[str, Any] | None = None) -> str:
        """Generate a structured action plan for planning-oriented requests."""
        entities = self._extract_entities(text)
        activity = self._detect_activity_type(text, key_phrases)
        phases = self._build_plan_phases(work, key_phrases, entities, activity)

        lines = [
            f"# Action Plan: {work.title}",
            "",
            "## Overview",
            f"- **Work ID:** {work.id}",
            f"- **Type:** {work.work_type}",
            f"- **Priority:** {work.priority}",
            "",
        ]

        if planning_context:
            lines.extend([
                "## Understanding",
                f"- {planning_context.get('understood_as', work.title)}",
                "",
            ])
            constraints = planning_context.get("constraints", {})
            if constraints:
                lines.extend([
                    "## Constraints",
                ])
                for key, value in constraints.items():
                    lines.append(f"- **{key}:** {value}")
                lines.append("")

            known_facts = planning_context.get("known_facts", [])
            if known_facts:
                lines.extend([
                    "## Known facts",
                ])
                for fact in known_facts:
                    lines.append(f"- {fact}")
                lines.append("")

            inferred = planning_context.get("inferred", [])
            if inferred:
                lines.extend([
                    "## Inferred signals",
                ])
                for signal in inferred:
                    lines.append(f"- {signal}")
                lines.append("")

            assumptions = planning_context.get("assumptions", [])
            if assumptions:
                lines.extend([
                    "## Assumptions",
                ])
                for assumption in assumptions:
                    lines.append(f"- {assumption}")
                lines.append("")

        lines.extend([
            "## Detected Activity",
            f"- {activity['name']}",
            "",
            "## Detected Entities",
        ])
        if entities:
            for entity_type, values in entities.items():
                lines.append(f"- **{entity_type}:** {', '.join(values)}")
        else:
            lines.append("- No specific entities detected; plan uses generic planning steps")
        lines.extend([
            "",
            "## Phases",
        ])
        for phase in phases:
            lines.append(f"### Phase {phase['number']}: {phase['name']}")
            lines.append(f"{phase['description']}")
            lines.append("")
            for task in phase["tasks"]:
                lines.append(f"- [ ] {task}")
            lines.append("")
        lines.extend([
            "## Suggested Actions",
        ])
        for suggestion in suggestions:
            lines.append(f"- {suggestion}")
        lines.extend([
            "",
            "## Result",
            "This work item was processed by the minimal Organisation worker.",
            f"The action plan has been written to `worker_outputs/{work.id}.md`.",
            "",
            "---",
            f"*Generated at {datetime.now(UTC).isoformat()}*",
        ])
        return "\n".join(lines)

    def _extract_entities(self, text: str) -> dict[str, list[str]]:
        """Extract simple entities from text for planning."""
        lower = text.lower()
        entities: dict[str, list[str]] = {
            "people": [],
            "quantities": [],
            "time": [],
            "locations": [],
        }

        people_keywords = ["party", "meeting", "event", "team", "client", "customer", "guest", "attendee"]
        for keyword in people_keywords:
            if keyword in lower:
                entities["people"].append(keyword.capitalize())

        import re
        quantity_pattern = re.compile(r"\b(\d+)\b")
        quantities = quantity_pattern.findall(text)
        entities["quantities"] = quantities[:5]

        time_keywords = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
                         "week", "month", "quarter", "year", "today", "tomorrow", "deadline"]
        for keyword in time_keywords:
            if keyword in lower:
                entities["time"].append(keyword.capitalize())

        return {k: v for k, v in entities.items() if v}

    def _detect_activity_type(self, text: str, key_phrases: list[str]) -> dict[str, Any]:
        """Detect the type of activity from the request text."""
        lower = text.lower()

        activity_patterns = [
            (["birthday", "party", "celebration", "anniversary"], "Event", "Event planning"),
            (["meeting", "conference", "summit", "workshop", "seminar"], "Professional Event", "Professional event planning"),
            (["hiking", "camping", "trip", "travel", "adventure", "expedition"], "Travel/Outdoor", "Travel and outdoor activity planning"),
            (["product", "launch", "release", "marketing", "campaign"], "Product Launch", "Product launch planning"),
            (["project", "build", "develop", "create", "implement"], "Project", "Project planning"),
            (["wedding", "marriage", "ceremony", "reception"], "Wedding", "Wedding planning"),
            (["conference", "convention", "congress", "symposium"], "Conference", "Conference planning"),
            (["party", "celebration", "gathering", "get-together"], "Social Gathering", "Social event planning"),
            (["retreat", "team building", "offsite", "away day"], "Retreat", "Retreat planning"),
            (["festival", "fair", "carnival", "market"], "Festival/Market", "Festival or market planning"),
        ]

        for keywords, activity_type, description in activity_patterns:
            if any(keyword in lower for keyword in keywords):
                return {
                    "type": activity_type,
                    "name": description,
                    "keywords": [k for k in keywords if k in lower],
                }

        return {
            "type": "General",
            "name": "General planning",
            "keywords": key_phrases[:3],
        }

    def _build_plan_phases(self, work: Work, key_phrases: list[str], entities: dict[str, list[str]], activity: dict[str, Any]) -> list[dict[str, Any]]:
        """Build planning phases based on detected activity type and entities."""
        activity_type = activity.get("type", "General")
        has_people = bool(entities.get("people"))
        has_quantities = bool(entities.get("quantities"))
        has_time = bool(entities.get("time"))
        has_locations = bool(entities.get("locations"))

        quantity = entities.get("quantities", ["several"])[0] if entities.get("quantities") else "several"
        people_types = entities.get("people", ["participants"])[0] if entities.get("people") else "participants"

        if activity_type == "Event" or activity_type == "Social Gathering":
            return self._build_event_plan(quantity, people_types, has_time, has_locations, work)
        elif activity_type == "Professional Event" or activity_type == "Conference":
            return self._build_professional_event_plan(quantity, people_types, has_time, has_locations, work)
        elif activity_type == "Travel/Outdoor":
            return self._build_travel_plan(quantity, people_types, has_time, work)
        elif activity_type == "Product Launch":
            return self._build_product_launch_plan(work)
        elif activity_type == "Project":
            return self._build_project_plan(quantity, has_time, work)
        elif activity_type == "Wedding":
            return self._build_wedding_plan(quantity, has_time, work)
        elif activity_type == "Retreat":
            return self._build_retreat_plan(quantity, people_types, has_time, work)
        elif activity_type == "Festival/Market":
            return self._build_festival_plan(quantity, has_time, has_locations, work)
        else:
            return self._build_generic_plan(quantity, has_people, has_time, work)

    def _build_event_plan(self, quantity: str, people_types: str, has_time: bool, has_locations: bool, work: Work) -> list[dict[str, Any]]:
        phases = [
            {
                "number": 1,
                "name": "Define Event Concept",
                "description": f"Clarify the {people_types.lower()} event details, theme, and objectives.",
                "tasks": [
                    "Confirm event type, date, and duration",
                    f"Define guest count target ({quantity} {people_types.lower()})",
                    "Set budget and cost categories",
                    "Identify venue requirements and constraints",
                ],
            },
            {
                "number": 2,
                "name": "Book Venue and Suppliers",
                "description": "Secure the physical location and key service providers.",
                "tasks": [
                    "Research and shortlist suitable venues",
                    f"Verify venue capacity for {quantity} guests",
                    "Book venue and negotiate terms",
                    "Book catering, entertainment, and equipment",
                ],
            },
            {
                "number": 3,
                "name": "Invitations and Communications",
                "description": f"Manage communications with {people_types.lower()}.",
                "tasks": [
                    f"Create guest list ({quantity} {people_types.lower()})",
                    "Design and send invitations",
                    "Track RSVPs and follow up non-responders",
                    "Share event details (location, timing, dress code)",
                ],
            },
        ]
        if has_time:
            phases.append({
                "number": len(phases) + 1,
                "name": "Final Timeline and Run Sheet",
                "description": "Create a minute-by-minute schedule for the event day.",
                "tasks": [
                    "Build event day timeline",
                    "Assign setup, coordination, and teardown roles",
                    "Prepare contingency plans (weather, delays, no-shows)",
                ],
            })
        phases.append({
            "number": len(phases) + 1,
            "name": "Execute and Review",
            "description": "Run the event and capture outcomes.",
            "tasks": [
                "Confirm all suppliers and arrangements",
                "Execute event according to run sheet",
                "Capture feedback from guests",
                "Review budget vs actual and note improvements",
            ],
        })
        return phases

    def _build_professional_event_plan(self, quantity: str, people_types: str, has_time: bool, has_locations: bool, work: Work) -> list[dict[str, Any]]:
        phases = [
            {
                "number": 1,
                "name": "Define Event Objectives",
                "description": f"Clarify the purpose and outcomes for this professional {people_types.lower()} event.",
                "tasks": [
                    "Define event purpose and success metrics",
                    f"Confirm target audience size ({quantity} {people_types.lower()})",
                    "Set budget, format, and delivery mode (in-person/virtual/hybrid)",
                    "Identify venue or platform requirements",
                ],
            },
            {
                "number": 2,
                "name": "Programme and Speakers",
                "description": "Design the event content and secure contributors.",
                "tasks": [
                    "Draft agenda and session formats",
                    "Identify and invite speakers or facilitators",
                    "Prepare presentations, materials, and handouts",
                    "Plan networking or interaction elements",
                ],
            },
            {
                "number": 3,
                "name": "Logistics and Promotion",
                "description": "Handle operational setup and attendance.",
                "tasks": [
                    f"Set up registration for {quantity} attendees",
                    "Configure event platform or prepare venue",
                    "Promote event through appropriate channels",
                    "Test A/V, streaming, and accessibility",
                ],
            },
        ]
        if has_time:
            phases.append({
                "number": len(phases) + 1,
                "name": "Rehearsal and Final Checks",
                "description": "Prepare for smooth execution.",
                "tasks": [
                    "Run through agenda with speakers",
                    "Confirm catering, seating, and signage",
                    "Prepare run-of-show and contact list",
                ],
            })
        phases.append({
            "number": len(phases) + 1,
            "name": "Execute and Review",
            "description": "Deliver the event and capture outcomes.",
            "tasks": [
                "Manage event execution and handle issues",
                "Gather attendee feedback",
                "Compile outcomes and follow-up actions",
            ],
        })
        return phases

    def _build_travel_plan(self, quantity: str, people_types: str, has_time: bool, work: Work) -> list[dict[str, Any]]:
        phases = [
            {
                "number": 1,
                "name": "Define Route and Destination",
                "description": f"Plan the trip structure for {quantity} {people_types.lower()}.",
                "tasks": [
                    "Choose destination and route",
                    f"Confirm trip duration and daily pacing for {quantity} people",
                    "Identify accommodation options",
                    "Check seasonal conditions and restrictions",
                ],
            },
            {
                "number": 2,
                "name": "Book Transport and Accommodation",
                "description": "Secure travel arrangements.",
                "tasks": [
                    "Book transport (flights, trains, vehicles)",
                    "Book accommodation and confirm cancellation policies",
                    "Arrange local transport or car rental",
                    "Verify baggage and equipment allowances",
                ],
            },
            {
                "number": 3,
                "name": "Prepare Gear and Supplies",
                "description": f"Ensure {quantity} people are properly equipped.",
                "tasks": [
                    "Create packing checklist by person",
                    "Verify safety and first-aid equipment",
                    "Prepare navigation tools and emergency contacts",
                    "Arrange food, water, and cooking supplies",
                ],
            },
        ]
        if has_time:
            phases.append({
                "number": len(phases) + 1,
                "name": "Itinerary and Contingencies",
                "description": "Build the detailed schedule and backup options.",
                "tasks": [
                    "Create day-by-day itinerary",
                    "Identify backup routes and shelter options",
                    "Share itinerary with emergency contacts",
                ],
            })
        phases.append({
            "number": len(phases) + 1,
            "name": "Execute and Review",
            "description": "Run the trip and capture outcomes.",
            "tasks": [
                "Execute itinerary and adapt to conditions",
                "Track expenses and experiences",
                "Debrief and document lessons learned",
            ],
        })
        return phases

    def _build_product_launch_plan(self, work: Work) -> list[dict[str, Any]]:
        phases = [
            {
                "number": 1,
                "name": "Define Launch Strategy",
                "description": "Clarify product positioning, messaging, and target audience.",
                "tasks": [
                    "Finalise value proposition and messaging",
                    "Define launch goals and success metrics",
                    "Identify target audience and channels",
                    "Set launch date and milestones",
                ],
            },
            {
                "number": 2,
                "name": "Prepare Marketing Assets",
                "description": "Create the materials needed for the launch.",
                "tasks": [
                    "Develop landing page or product page",
                    "Create promotional content (social, email, blog)",
                    "Prepare press kit or media outreach",
                    "Configure analytics and tracking",
                ],
            },
            {
                "number": 3,
                "name": "Coordinate Launch Execution",
                "description": "Align teams and execute the launch sequence.",
                "tasks": [
                    "Brief sales, support, and engineering teams",
                    "Schedule announcements and content drops",
                    "Monitor launch day metrics and issues",
                    "Respond to early feedback and bugs",
                ],
            },
            {
                "number": 4,
                "name": "Post-Launch Review",
                "description": "Assess launch outcomes and plan next steps.",
                "tasks": [
                    "Analyse launch metrics against goals",
                    "Collect customer and stakeholder feedback",
                    "Plan follow-up campaigns or iterations",
                ],
            },
        ]
        return phases

    def _build_project_plan(self, quantity: str, has_time: bool, work: Work) -> list[dict[str, Any]]:
        phases = [
            {
                "number": 1,
                "name": "Define Scope and Objectives",
                "description": "Clarify what the project must deliver.",
                "tasks": [
                    "Confirm project objectives and deliverables",
                    "Identify stakeholders and decision-makers",
                    "Define acceptance criteria and quality standards",
                ],
            },
            {
                "number": 2,
                "name": "Break Down Work",
                "description": "Decompose the project into manageable tasks.",
                "tasks": [
                    "Create work breakdown structure",
                    "Estimate effort and dependencies",
                    "Identify risks and mitigation strategies",
                ],
            },
            {
                "number": 3,
                "name": "Assign and Schedule",
                "description": "Allocate work and set timelines.",
                "tasks": [
                    f"Assign tasks to team members or roles",
                    "Create project timeline and milestones",
                    "Set up tracking and reporting cadence",
                ],
            },
        ]
        if has_time:
            phases.append({
                "number": len(phases) + 1,
                "name": "Execute and Monitor",
                "description": "Run the project and track progress.",
                "tasks": [
                    "Execute tasks according to schedule",
                    "Monitor progress and manage changes",
                    "Communicate status to stakeholders",
                ],
            })
        phases.append({
            "number": len(phases) + 1,
            "name": "Deliver and Review",
            "description": "Complete the project and capture lessons.",
            "tasks": [
                "Verify deliverables against acceptance criteria",
                "Obtain stakeholder sign-off",
                "Conduct project retrospective",
            ],
        })
        return phases

    def _build_wedding_plan(self, quantity: str, has_time: bool, work: Work) -> list[dict[str, Any]]:
        phases = [
            {
                "number": 1,
                "name": "Set Vision and Budget",
                "description": f"Define the wedding style and financial parameters for {quantity} guests.",
                "tasks": [
                    "Agree on wedding style and theme",
                    "Set overall budget and allocate categories",
                    "Choose date and venue options",
                ],
            },
            {
                "number": 2,
                "name": "Book Key Vendors",
                "description": "Secure the essential service providers.",
                "tasks": [
                    "Book ceremony and reception venues",
                    "Hire photographer, videographer, and celebrant",
                    "Book caterer, cake, and beverages",
                    "Arrange transport and accommodation",
                ],
            },
            {
                "number": 3,
                "name": "Plan Guest Experience",
                "description": f"Manage the guest journey for {quantity} attendees.",
                "tasks": [
                    f"Finalise guest list ({quantity})",
                    "Design and send invitations",
                    "Track RSVPs and dietary requirements",
                    "Plan seating, ceremony, and reception flow",
                ],
            },
        ]
        if has_time:
            phases.append({
                "number": len(phases) + 1,
                "name": "Final Details and Rehearsal",
                "description": "Prepare for the day.",
                "tasks": [
                    "Confirm final numbers with vendors",
                    "Prepare vows, speeches, and readings",
                    "Run rehearsal and final walkthrough",
                ],
            })
        phases.append({
            "number": len(phases) + 1,
            "name": "Execute and Review",
            "description": "Celebrate and capture memories.",
            "tasks": [
                "Enjoy the wedding day",
                "Collect photos and videos",
                "Send thank-you notes",
            ],
        })
        return phases

    def _build_retreat_plan(self, quantity: str, people_types: str, has_time: bool, work: Work) -> list[dict[str, Any]]:
        phases = [
            {
                "number": 1,
                "name": "Define Retreat Objectives",
                "description": f"Clarify the purpose and outcomes for {quantity} {people_types.lower()}.",
                "tasks": [
                    "Define retreat goals (team building, strategy, wellness)",
                    "Set budget and date range",
                    "Identify destination and venue criteria",
                ],
            },
            {
                "number": 2,
                "name": "Arrange Venue and Travel",
                "description": "Secure the location and logistics.",
                "tasks": [
                    "Book retreat venue or accommodation",
                    "Arrange transport for the group",
                    "Confirm catering and special dietary needs",
                ],
            },
            {
                "number": 3,
                "name": "Design Programme",
                "description": "Plan the retreat activities and sessions.",
                "tasks": [
                    "Create session agenda with breaks",
                    "Prepare materials, handouts, and equipment",
                    "Arrange facilitators or speakers if needed",
                ],
            },
        ]
        if has_time:
            phases.append({
                "number": len(phases) + 1,
                "name": "Final Preparation",
                "description": "Prepare participants and logistics.",
                "tasks": [
                    "Send pre-retreat information and packing lists",
                    "Confirm attendee list and preferences",
                    "Prepare backup indoor options",
                ],
            })
        phases.append({
            "number": len(phases) + 1,
            "name": "Execute and Review",
            "description": "Run the retreat and capture outcomes.",
            "tasks": [
                "Facilitate sessions and manage energy",
                "Gather participant feedback",
                "Document outcomes and action items",
            ],
        })
        return phases

    def _build_festival_plan(self, quantity: str, has_time: bool, has_locations: bool, work: Work) -> list[dict[str, Any]]:
        phases = [
            {
                "number": 1,
                "name": "Define Festival Concept",
                "description": "Set the theme, format, and target audience.",
                "tasks": [
                    "Choose festival theme and name",
                    "Define target audience and experience",
                    "Set budget and revenue model",
                ],
            },
            {
                "number": 2,
                "name": "Secure Site and Permissions",
                "description": "Lock in the location and legal requirements.",
                "tasks": [
                    "Book festival site or outdoor venue",
                    "Apply for permits, insurance, and safety approvals",
                    "Arrange infrastructure (power, water, toilets, waste)",
                ],
            },
            {
                "number": 3,
                "name": "Programme and Vendors",
                "description": "Build the line-up and marketplace.",
                "tasks": [
                    "Book performers, speakers, or activities",
                    "Recruit food, drink, and market vendors",
                    "Create festival schedule and stage plan",
                ],
            },
        ]
        if has_time:
            phases.append({
                "number": len(phases) + 1,
                "name": "Promotion and Ticketing",
                "description": "Drive attendance and manage entry.",
                "tasks": [
                    "Set up ticketing and pricing tiers",
                    "Launch promotional campaign",
                    "Prepare staff, volunteers, and security",
                ],
            })
        phases.append({
            "number": len(phases) + 1,
                "name": "Execute and Review",
                "description": "Run the festival and capture outcomes.",
                "tasks": [
                    "Execute festival according to run-of-show",
                    "Monitor safety, crowd, and vendor issues",
                    "Collect feedback and financial reconciliation",
                ],
            })
        return phases

    def _build_generic_plan(self, quantity: str, has_people: bool, has_time: bool, work: Work) -> list[dict[str, Any]]:
        phases = [
            {
                "number": 1,
                "name": "Define Scope and Objectives",
                "description": "Clarify what needs to be achieved.",
                "tasks": [
                    "Confirm the core objective and desired outcome",
                    "Identify constraints (budget, time, resources)",
                    "Define success criteria",
                ],
            },
            {
                "number": 2,
                "name": "Gather Requirements",
                "description": "Collect the information and resources needed.",
                "tasks": [
                    "List required resources and dependencies",
                    "Identify risks and assumptions",
                ],
            },
        ]
        if has_people:
            phases.append({
                "number": len(phases) + 1,
                "name": "Coordinate People",
                "description": "Organise the people and roles involved.",
                "tasks": [
                    f"Confirm involvement of {quantity} people",
                    "Assign roles and responsibilities",
                    "Communicate plan and expectations",
                ],
            })
        if has_time:
            phases.append({
                "number": len(phases) + 1,
                "name": "Schedule",
                "description": "Create a timeline and milestones.",
                "tasks": [
                    "Set key dates and deadlines",
                    "Create a timeline with milestones",
                    "Identify dependencies between tasks",
                ],
            })
        phases.append({
            "number": len(phases) + 1,
            "name": "Execute and Review",
            "description": "Carry out the plan and verify results.",
            "tasks": [
                "Execute according to the plan",
                "Monitor progress against milestones",
                "Review outcomes and capture lessons learned",
            ],
        })
        return phases

    def _extract_key_phrases(self, text: str) -> list[str]:
        """Extract simple key phrases from text."""
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "as", "is", "was", "are",
            "were", "been", "be", "have", "has", "had", "do", "does", "did",
            "will", "would", "shall", "should", "may", "might", "must", "can",
            "could", "this", "that", "these", "those", "it", "its", "i",
            "you", "he", "she", "we", "they", "what", "which", "who",
            "when", "where", "why", "how", "all", "each", "every", "both",
            "few", "more", "most", "other", "some", "such", "no", "not",
            "only", "same", "so", "than", "too", "very", "just", "about",
            "into", "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once", "here",
            "there", "up", "down", "out", "off", "over", "under", "please",
            "thank", "thanks", "help", "need", "want", "like", "make",
            "get", "got", "know", "think", "see", "look", "come", "go",
        }
        words = text.lower().split()
        candidates = [
            word.strip(".,!?;:\"'()[]{}")
            for word in words
            if len(word) > 3 and word.lower() not in stop_words
        ]
        seen = set()
        phrases = []
        for phrase in candidates:
            if phrase not in seen:
                seen.add(phrase)
                phrases.append(phrase)
        return phrases[:8]

    def _infer_intent(self, text: str) -> str:
        """Infer the user's intent from simple keyword matching."""
        lower = text.lower()
        if any(word in lower for word in ["summarise", "summary", "summarize", "brief"]):
            return "Content summarisation"
        if any(word in lower for word in ["meeting notes", "convert to actions", "action items", "meeting actions"]):
            return "Meeting actions"
        if any(word in lower for word in ["brainstorm", "ideas for", "generate ideas", "idea generation"]):
            return "Brainstorming"
        if any(word in lower for word in ["analyse", "analyze", "analysis", "review", "investigate"]):
            return "Content analysis"
        if any(word in lower for word in ["plan", "schedule", "organise", "organize"]):
            return "Planning request"
        if any(word in lower for word in ["compare", "difference", "versus", "vs"]):
            return "Comparison"
        if any(word in lower for word in ["create", "generate", "write", "draft"]):
            return "Content creation"
        if any(word in lower for word in ["find", "search", "locate", "look for"]):
            return "Information retrieval"
        if any(word in lower for word in ["explain", "describe", "tell me about"]):
            return "Explanation request"
        if any(word in lower for word in ["fix", "repair", "resolve", "solve"]):
            return "Problem resolution"
        return "General assistance"

    def _suggest_actions(self, work: Work, intent: str) -> list[str]:
        """Suggest concrete next actions based on inferred intent."""
        suggestions = []
        if intent == "Content summarisation":
            suggestions.append("Locate the source document or data to summarise")
            suggestions.append("Extract key points and structure them concisely")
        elif intent == "Content analysis":
            suggestions.append("Identify the scope and criteria for analysis")
            suggestions.append("Gather relevant data or documents")
        elif intent == "Content creation":
            suggestions.append("Clarify the target format and audience")
            suggestions.append("Gather source material and constraints")
        elif intent == "Information retrieval":
            suggestions.append("Identify the information sources to search")
            suggestions.append("Define search criteria and filters")
        elif intent == "Comparison":
            suggestions.append("Identify the items to compare")
            suggestions.append("Define comparison criteria")
        elif intent == "Explanation request":
            suggestions.append("Identify the concept or topic to explain")
            suggestions.append("Determine the required level of detail")
        elif intent == "Problem resolution":
            suggestions.append("Document the problem symptoms and context")
            suggestions.append("Identify potential root causes")
        elif intent == "Planning request":
            suggestions.append("Define the planning horizon and constraints")
            suggestions.append("Identify required resources and dependencies")
        else:
            suggestions.append("Clarify the specific objective")
            suggestions.append("Identify available resources and constraints")
        return suggestions

    def _write_output(self, work_id: str, title: str, content: str) -> Path:
        """Write the work output to a file."""
        safe_title = title.lower().replace(" ", "-")[:30]
        filename = f"{work_id}-{safe_title}.md"
        output_path = self._output_dir / filename
        output_path.write_text(content, encoding="utf-8")
        return output_path

    def _summarise_text(self, work: Work, text: str) -> str:
        """Generate an extractive summary of the supplied text."""
        sentences = self._split_sentences(text)
        word_count = len(text.split())
        sentence_count = len(sentences)

        if sentence_count <= 3:
            summary_sentences = sentences
        else:
            scores = self._score_sentences(sentences)
            target_count = max(2, sentence_count // 3)
            ranked = sorted(
                [(score, idx, sentence) for idx, (score, sentence) in enumerate(scores)],
                key=lambda x: x[0],
                reverse=True,
            )
            selected = sorted(ranked[:target_count], key=lambda x: x[1])
            summary_sentences = [sentence for _, _, sentence in selected]

        summary_text = " ".join(summary_sentences)
        key_phrases = self._extract_key_phrases(text)
        reading_time = max(1, word_count // 200)
        compression = round((1 - len(summary_text.split()) / word_count) * 100) if word_count > 0 else 0

        lines = [
            f"# Summary: {work.title}",
            "",
            "## Overview",
            f"- **Work ID:** {work.id}",
            f"- **Input length:** {word_count} words, {sentence_count} sentences",
            f"- **Summary length:** {len(summary_text.split())} words",
            f"- **Compression:** {compression}%",
            f"- **Estimated reading time:** {reading_time} minute(s)",
            "",
        ]
        if key_phrases:
            lines.extend([
                "## Key Themes",
            ])
            for phrase in key_phrases[:6]:
                lines.append(f"- {phrase}")
        lines.extend([
            "",
            "## Summary",
            "",
            summary_text,
            "",
            "## Result",
            "This work item was processed by the minimal Organisation worker.",
            f"The summary has been written to `worker_outputs/{work.id}.md`.",
            "",
            "---",
            f"*Generated at {datetime.now(UTC).isoformat()}*",
        ])
        return "\n".join(lines)

    def _generate_proposal(self, work: Work, text: str) -> str:
        """Generate a structured project proposal."""
        key_phrases = self._extract_key_phrases(text)
        subject = work.title.replace("Create a proposal for", "").replace("Create proposal for", "").strip()
        if not subject:
            subject = text.split()[-1] if text.split() else "project"

        lines = [
            f"# Project Proposal: {subject}",
            "",
            "## Overview",
            f"- **Work ID:** {work.id}",
            f"- **Subject:** {subject}",
            "",
            "## Objectives",
            f"- Define the scope and goals for {subject}",
            "- Identify key stakeholders and their needs",
            "- Establish measurable success criteria",
            "",
            "## Approach",
            "- Research existing solutions and best practices",
            "- Design the core solution architecture",
            "- Develop a phased implementation plan",
            "- Define resource requirements and timeline",
            "",
            "## Deliverables",
            "- Working prototype or minimum viable product",
            "- Documentation and user guides",
            "- Testing and validation report",
            "- Deployment and rollout plan",
            "",
            "## Timeline",
            "- Week 1-2: Discovery and requirements",
            "- Week 3-4: Design and planning",
            "- Week 5-8: Development and iteration",
            "- Week 9-10: Testing and refinement",
            "- Week 11-12: Deployment and handover",
            "",
            "## Key Themes",
        ]
        if key_phrases:
            for phrase in key_phrases[:6]:
                lines.append(f"- {phrase}")
        lines.extend([
            "",
            "## Result",
            "This work item was processed by the minimal Organisation worker.",
            f"The proposal has been written to `worker_outputs/{work.id}.md`.",
            "",
            "---",
            f"*Generated at {datetime.now(UTC).isoformat()}*",
        ])
        return "\n".join(lines)

    def _generate_actions(self, work: Work, text: str) -> str:
        """Generate action items from meeting notes or discussion text."""
        key_phrases = self._extract_key_phrases(text)
        sentences = self._split_sentences(text)
        action_keywords = ["action", "task", "todo", "follow up", "follow-up", "assign", "responsible", "deadline", "owner", "schedule", "meeting", "notes"]

        actions = []
        for sentence in sentences:
            lower = sentence.lower()
            if any(kw in lower for kw in action_keywords) or len(sentence.split()) > 8:
                actions.append(sentence)

        if not actions:
            actions = sentences[:3]

        lines = [
            f"# Action Items: {work.title}",
            "",
            "## Overview",
            f"- **Work ID:** {work.id}",
            f"- **Source items:** {len(sentences)} statements, {len(actions)} actions extracted",
            "",
            "## Action Items",
        ]
        for idx, action in enumerate(actions, 1):
            lines.append(f"- [ ] {action}")
        lines.extend([
            "",
            "## Next Steps",
            "- Review and prioritise action items",
            "- Assign owners and deadlines",
            "- Schedule follow-up meeting",
            "",
            "## Key Themes",
        ])
        if key_phrases:
            for phrase in key_phrases[:6]:
                lines.append(f"- {phrase}")
        lines.extend([
            "",
            "## Result",
            "This work item was processed by the minimal Organisation worker.",
            f"The action items have been written to `worker_outputs/{work.id}.md`.",
            "",
            "---",
            f"*Generated at {datetime.now(UTC).isoformat()}*",
        ])
        return "\n".join(lines)

    def _generate_ideas(self, work: Work, text: str) -> str:
        """Generate brainstorming ideas based on the topic."""
        key_phrases = self._extract_key_phrases(text)
        topic = text.lower()
        topic = topic.replace("generate ideas for", "").replace("brainstorm", "").replace("ideas for", "").strip()
        if not topic:
            topic = work.title

        idea_templates = [
            f"Launch a pilot program focused on {topic}",
            f"Partner with industry leaders in {topic}",
            f"Create a community or network around {topic}",
            f"Develop a digital platform or tool for {topic}",
            f"Run workshops or training sessions on {topic}",
            f"Publish research or case studies about {topic}",
            f"Offer a subscription or membership model for {topic}",
            f"Integrate {topic} with existing popular services",
        ]

        lines = [
            f"# Brainstorm: {topic}",
            "",
            "## Overview",
            f"- **Work ID:** {work.id}",
            f"- **Topic:** {topic}",
            "",
            "## Ideas",
        ]
        for idx, idea in enumerate(idea_templates, 1):
            lines.append(f"{idx}. {idea}")
        lines.extend([
            "",
            "## Evaluation Criteria",
            "- Feasibility: Can we execute this with current resources?",
            "- Impact: How much value does this create?",
            "- Differentiation: Does this set us apart?",
            "- Speed: How quickly can we launch?",
            "",
            "## Key Themes",
        ])
        if key_phrases:
            for phrase in key_phrases[:6]:
                lines.append(f"- {phrase}")
        lines.extend([
            "",
            "## Result",
            "This work item was processed by the minimal Organisation worker.",
            f"The ideas have been written to `worker_outputs/{work.id}.md`.",
            "",
            "---",
            f"*Generated at {datetime.now(UTC).isoformat()}*",
        ])
        return "\n".join(lines)

    def _generate_comparison(self, work: Work, text: str) -> str:
        """Generate a comparison between two or more approaches."""
        key_phrases = self._extract_key_phrases(text)
        lower = text.lower()

        approaches = []
        if " versus " in lower or " vs " in lower:
            parts = lower.split(" versus " if " versus " in lower else " vs ")
            approaches = [p.strip().title() for p in parts[:2]]
        if not approaches and " and " in lower:
            parts = lower.split(" and ")
            approaches = [p.strip().title() for p in parts[:2]]
        if not approaches:
            words = text.split()
            approaches = [words[0].title() if words else "Approach A", words[-1].title() if words else "Approach B"]

        criteria = ["Cost", "Speed", "Quality", "Scalability", "Complexity", "Risk"]

        lines = [
            f"# Comparison: {' vs '.join(approaches)}",
            "",
            "## Overview",
            f"- **Work ID:** {work.id}",
            f"- **Comparing:** {' vs '.join(approaches)}",
            "",
            "## Comparison Matrix",
            "| Criterion | " + " | ".join(approaches) + " |",
            "|-----------|" + "|".join(["------" for _ in approaches]) + "|",
        ]
        for criterion in criteria:
            ratings = []
            for _ in approaches:
                ratings.append("Medium")
            lines.append(f"| {criterion} | " + " | ".join(ratings) + " |")
        lines.extend([
            "",
            "## Summary",
            f"- Both approaches have distinct trade-offs",
            f"- {approaches[0]} may offer different advantages depending on priorities",
            f"- {approaches[1]} may be preferable in other contexts",
            "- Consider hybrid approaches where appropriate",
            "",
            "## Recommendation",
            "- Evaluate based on your specific constraints and goals",
            "- Run a small-scale test before full commitment",
            "- Revisit the decision after initial results",
            "",
            "## Key Themes",
        ])
        if key_phrases:
            for phrase in key_phrases[:6]:
                lines.append(f"- {phrase}")
        lines.extend([
            "",
            "## Result",
            "This work item was processed by the minimal Organisation worker.",
            f"The comparison has been written to `worker_outputs/{work.id}.md`.",
            "",
            "---",
            f"*Generated at {datetime.now(UTC).isoformat()}*",
        ])
        return "\n".join(lines)

    def _generate_analysis(self, work: Work, text: str, analysis_context: dict[str, Any] | None = None) -> str:
        """Generate a structured decision-oriented analysis of content."""
        key_phrases = self._extract_key_phrases(text)
        sentences = self._split_sentences(text)
        word_count = len(text.split())

        lines = [
            f"# Analysis: {work.title}",
            "",
            "## Overview",
            f"- **Work ID:** {work.id}",
            f"- **Input length:** {word_count} words, {len(sentences)} sentences",
            "",
        ]

        if analysis_context:
            lines.extend([
                "## Understanding",
                f"- {analysis_context.get('understanding', work.title)}",
                "",
            ])
            known_facts = analysis_context.get("known_facts", [])
            if known_facts:
                lines.extend([
                    "## What We Know",
                ])
                for fact in known_facts:
                    lines.append(f"- {fact}")
                lines.append("")

            evidence = analysis_context.get("evidence", [])
            if evidence:
                lines.extend([
                    "## Evidence Path",
                ])
                for item in evidence:
                    lines.append(f"- {item}")
                lines.append("")

            relationships = analysis_context.get("relationships", [])
            if relationships:
                lines.extend([
                    "## What Appears Connected",
                ])
                for rel in relationships:
                    level = rel.get("level", "inferred")
                    lines.append(f"- **[{level.upper()}]** {'; '.join(rel.get('signals', []))}: {rel.get('interpretation', '')}")
                lines.append("")

            hypotheses = analysis_context.get("hypotheses", [])
            if hypotheses:
                lines.extend([
                    "## Possible Explanation",
                ])
                for hyp in hypotheses:
                    lines.append(f"- {hyp}")
                lines.append("")

            focus_areas = analysis_context.get("focus_areas", [])
            if focus_areas:
                lines.extend([
                    "## Prioritised Focus",
                ])
                for idx, area in enumerate(focus_areas, 1):
                    lines.append(f"### {idx}. {area.get('name', '')}")
                    evidence_items = area.get("evidence", [])
                    if evidence_items:
                        lines.append(f"Evidence: {'; '.join(evidence_items)}")
                    lines.append(f"Why this matters: {area.get('why', '')}")
                    lines.append(f"Confidence: {area.get('confidence_label', area.get('confidence', 'inferred'))}")
                    validate = area.get("validate", [])
                    if validate:
                        lines.append(f"What would validate this: {'; '.join(validate)}")
                    actions = area.get("possible_actions", [])
                    if actions:
                        lines.append(f"Possible next moves: {'; '.join(actions)}")
                    lines.append("")

            possible_actions = analysis_context.get("possible_actions", [])
            if possible_actions:
                lines.extend([
                    "## Possible Next Moves",
                ])
                for action in possible_actions:
                    lines.append(f"- {action}")
                lines.append("")

            validation_criteria = analysis_context.get("validation_criteria", [])
            if validation_criteria:
                lines.extend([
                    "## What We Would Want to Verify",
                ])
                for criterion in validation_criteria:
                    lines.append(f"- {criterion}")
                lines.append("")

            confidence = analysis_context.get("confidence", "low")
            lines.extend([
                "## Confidence",
                f"- Overall confidence: {confidence.upper()}",
                "",
            ])

            assumptions = analysis_context.get("assumptions", [])
            if assumptions:
                lines.extend([
                    "## Assumptions",
                ])
                for assumption in assumptions:
                    lines.append(f"- {assumption}")
                lines.append("")
        else:
            lines.extend([
                "## Key Points",
            ])
            for sentence in sentences[:5]:
                lines.append(f"- {sentence}")
            lines.extend([
                "",
                "## Themes",
            ])
            if key_phrases:
                for phrase in key_phrases[:6]:
                    lines.append(f"- {phrase}")
            lines.extend([
                "",
                "## Insights",
                "- The content presents a coherent narrative",
                "- Key themes emerge from the main arguments",
                "- Further detail is available in the source material",
                "",
            ])

        lines.extend([
            "## Result",
            "This work item was processed by the minimal Organisation worker.",
            f"The analysis has been written to `worker_outputs/{work.id}.md`.",
            "",
            "---",
            f"*Generated at {datetime.now(UTC).isoformat()}*",
        ])
        return "\n".join(lines)

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        import re
        text = text.replace("\n", " ")
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _score_sentences(self, sentences: list[str]) -> list[tuple[float, str]]:
        """Score sentences by word frequency and position."""
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "as", "is", "was", "are",
            "were", "been", "be", "have", "has", "had", "do", "does", "did",
            "will", "would", "shall", "should", "may", "might", "must", "can",
            "could", "this", "that", "these", "those", "it", "its", "i",
            "you", "he", "she", "we", "they", "what", "which", "who",
            "when", "where", "why", "how", "all", "each", "every", "both",
            "few", "more", "most", "other", "some", "such", "no", "not",
            "only", "same", "so", "than", "too", "very", "just", "about",
            "into", "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once", "here",
            "there", "up", "down", "out", "off", "over", "under", "please",
            "thank", "thanks", "help", "need", "want", "like", "make",
            "get", "got", "know", "think", "see", "look", "come", "go",
        }
        word_freq: dict[str, int] = {}
        for sentence in sentences:
            for word in sentence.lower().split():
                word = word.strip(".,!?;:\"'()[]{}")
                if len(word) > 3 and word not in stop_words:
                    word_freq[word] = word_freq.get(word, 0) + 1

        max_freq = max(word_freq.values()) if word_freq else 1
        for word in word_freq:
            word_freq[word] = word_freq[word] / max_freq

        scored = []
        total_sentences = len(sentences)
        for idx, sentence in enumerate(sentences):
            words = [
                w.strip(".,!?;:\"'()[]{}")
                for w in sentence.lower().split()
                if len(w.strip(".,!?;:\"'()[]{}")) > 3
            ]
            if not words:
                scored.append((0.0, sentence))
                continue

            freq_score = sum(word_freq.get(w, 0.0) for w in words) / len(words)
            position_score = 1.0 if idx < 2 else (0.5 if idx >= total_sentences - 2 else 0.0)
            length_score = 1.0 if 5 <= len(words) <= 30 else (0.5 if len(words) < 5 else 0.7)

            score = (freq_score * 2.0) + position_score + length_score
            scored.append((score, sentence))
        return scored
