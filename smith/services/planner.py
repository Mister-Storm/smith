"""Guided planning service — deterministic context assembly with gated AI."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from smith.core.config import Config
from smith.llm.base import LLMProvider
from smith.llm.factory import get_llm_provider
from smith.models.git_intelligence import DevelopmentAssessment
from smith.models.planning_context import (
    ContextGap,
    GapSeverity,
    PlanningConstraint,
    PlanningContext,
    PlanningDecision,
    PlanningDimension,
    PlanningKnown,
    PlanningReadiness,
    PlanningResult,
    PlanningSession,
)
from smith.services.clarification import generate_questions_from_gaps, has_blocking_gaps
from smith.services.context_gap_analysis import (
    apply_decisions,
    critical_dimension_gaps,
    detect_context_gaps,
    important_dimension_gaps,
    structural_gaps,
    validate_gap_order,
)
from smith.services.git_intelligence import try_get_repository_status
from smith.services.planning_confidence import (
    MIN_CONFIDENCE_FOR_PLAN,
    MINIMUM_CONTEXT_THRESHOLD,
    calculate_confidence,
    calculate_context_quality,
)
from smith.services.project_context import (
    ProjectContextService,
    display_build,
    display_framework,
    display_language,
)
from smith.services.user_context import UserContextService
from smith.services.workspace_intelligence import WorkspaceIntelligenceService

logger = logging.getLogger(__name__)

MIN_KNOWNS_FOR_PLAN = 3
MAX_IMPORTANT_GAPS = 2
MAX_ASSUMPTIONS = 3
MAX_PLAN_STEPS = 15
MAX_PROMPT_CHARS = 6000

INFRA_EVIDENCE: dict[str, list[str]] = {
    "docker": ["Dockerfile", "docker-compose.yml"],
    "docker-compose": ["docker-compose.yml"],
    "kubernetes": ["k8s/", "kubernetes/"],
}

CI_EVIDENCE: dict[str, list[str]] = {
    "github-actions": [".github/workflows/"],
    "gitlab-ci": [".gitlab-ci.yml"],
    "jenkins": ["Jenkinsfile"],
}

_PLAN_SYSTEM = (
    "You generate concise, practical implementation plans in markdown. "
    "Use only the provided context. Keep the plan to 5-15 actionable steps "
    "across up to 3 phases. Do not invent requirements not supported by context."
)

_RANK_SYSTEM = (
    "Rank planning dimension gaps by relevance to the goal. "
    'Respond with strict JSON only: {"order": ["success_criteria", "timeline", ...]}. '
    "Use only dimension IDs from the input. Do not add or remove dimensions."
)

_planning_session: PlanningSession | None = None


def get_last_planning_result() -> PlanningResult | None:
    if _planning_session and _planning_session.last_result:
        return _planning_session.last_result
    return None


def get_planning_session() -> PlanningSession | None:
    return _planning_session


def set_last_planning_result(result: PlanningResult | None) -> None:
    global _planning_session
    if result is None:
        _planning_session = None
        return
    _planning_session = PlanningSession(
        goal=result.goal,
        gaps=result.gaps,
        decisions=result.decisions,
        questions=result.questions,
        last_result=result,
    )


class PlanningService:
    def __init__(
        self,
        cwd: Path | None = None,
        config: Config | None = None,
        *,
        provider: LLMProvider | None = None,
    ) -> None:
        self._cwd = (cwd or Path.cwd()).expanduser().resolve()
        self._config = config or Config.load()
        self._provider = provider
        self._project_service = ProjectContextService()
        self._workspace_service = WorkspaceIntelligenceService(self._cwd)

    def build_context(
        self,
        goal: str | None = None,
        *,
        decisions: list[PlanningDecision] | None = None,
    ) -> PlanningContext:
        session_decisions = decisions
        if session_decisions is None and _planning_session and _planning_session.goal == goal:
            session_decisions = _planning_session.decisions

        user_context = UserContextService(workspace_root=self._cwd).load()
        project_context = self._project_service.load(self._cwd)
        workspace_context = self._workspace_service.load_workspace_context()
        git_context = try_get_repository_status(self._cwd)

        ctx = PlanningContext(
            user_context=user_context,
            project_context=project_context,
            workspace_context=workspace_context,
            git_context=git_context,
            goal=goal,
            decisions=list(session_decisions or []),
        )
        ctx.knowns = self.identify_knowns(ctx)
        ctx.constraints = self.identify_constraints(ctx)
        ctx.assumptions = self.identify_assumptions(ctx, goal or "")
        raw_gaps = detect_context_gaps(
            goal or "",
            ctx,
            knowns=ctx.knowns,
            constraints=ctx.constraints,
            assumptions=ctx.assumptions,
        )
        ctx.gaps = apply_decisions(raw_gaps, ctx.decisions)
        return ctx

    def record_decision(self, dimension: PlanningDimension, answer: str) -> PlanningDecision:
        global _planning_session
        if _planning_session is None or not _planning_session.goal:
            raise RuntimeError("No active planning session. Run `smith plan <goal>` first.")
        decision = PlanningDecision(
            dimension=dimension,
            answer=answer,
            recorded_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        existing = [d for d in _planning_session.decisions if d.dimension != dimension]
        existing.append(decision)
        _planning_session.decisions = existing
        return decision

    def identify_knowns(self, ctx: PlanningContext) -> list[PlanningKnown]:
        knowns: list[PlanningKnown] = []
        user = ctx.user_context

        if user.primary_languages:
            lang = user.primary_languages[0]
            knowns.append(
                PlanningKnown(
                    text=f"User primarily works with {lang}",
                    source="User Context",
                    evidence=user.primary_languages[:3],
                )
            )
        if user.preferred_frameworks:
            fw = user.preferred_frameworks[0]
            knowns.append(
                PlanningKnown(
                    text=f"User prefers {fw}",
                    source="User Context",
                    evidence=user.preferred_frameworks[:3],
                )
            )
        if user.active_projects:
            names = ", ".join(user.active_projects[:3])
            knowns.append(
                PlanningKnown(
                    text=f"User has active projects: {names}",
                    source="User Context",
                    evidence=user.active_projects[:5],
                )
            )
        if user.working_domains:
            domains = ", ".join(user.working_domains[:3])
            knowns.append(
                PlanningKnown(
                    text=f"User working domains include {domains}",
                    source="User Context",
                    evidence=user.working_domains[:5],
                )
            )
        if user.goals:
            knowns.append(
                PlanningKnown(
                    text=f"User goal: {user.goals[0]}",
                    source="User Context",
                    evidence=user.goals[:3],
                )
            )

        for decision in ctx.decisions:
            knowns.append(
                PlanningKnown(
                    text=f"{decision.dimension.value.replace('_', ' ').title()}: {decision.answer}",
                    source="User Answer",
                    evidence=[decision.recorded_at],
                )
            )

        project = ctx.project_context
        if project:
            if project.language:
                knowns.append(
                    PlanningKnown(
                        text=f"Current project language is {display_language(project.language)}",
                        source="Project Context",
                        evidence=[project.project_name],
                    )
                )
            if project.framework:
                knowns.append(
                    PlanningKnown(
                        text=f"Current project uses {display_framework(project.framework)}",
                        source="Project Context",
                        evidence=[project.project_name],
                    )
                )
            for slug in project.infrastructure:
                display = slug.replace("-", " ").title()
                knowns.append(
                    PlanningKnown(
                        text=f"Repository uses {display}",
                        source="Project Context",
                        evidence=INFRA_EVIDENCE.get(slug, []),
                    )
                )
            for slug in project.ci_cd:
                display = slug.replace("-", " ").title()
                knowns.append(
                    PlanningKnown(
                        text=f"Repository uses {display}",
                        source="Project Context",
                        evidence=CI_EVIDENCE.get(slug, []),
                    )
                )

        workspace = ctx.workspace_context
        if workspace and workspace.languages:
            lang_names = list(workspace.languages.keys())[:5]
            langs = ", ".join(lang_names)
            knowns.append(
                PlanningKnown(
                    text=f"Workspace languages include {langs}",
                    source="Workspace Context",
                    evidence=lang_names,
                )
            )
        if workspace and workspace.frameworks:
            fw_names = list(workspace.frameworks.keys())[:5]
            fws = ", ".join(fw_names)
            knowns.append(
                PlanningKnown(
                    text=f"Workspace frameworks include {fws}",
                    source="Workspace Context",
                    evidence=fw_names,
                )
            )

        git = ctx.git_context
        if git:
            assessment = git.assessment.label
            knowns.append(
                PlanningKnown(
                    text=f"Working on branch {git.branch} ({assessment})",
                    source="Git Context",
                    evidence=[git.repo_root],
                )
            )

        return knowns

    def identify_constraints(self, ctx: PlanningContext) -> list[PlanningConstraint]:
        constraints: list[PlanningConstraint] = []

        git = ctx.git_context
        if git and git.assessment == DevelopmentAssessment.WORK_IN_PROGRESS:
            constraints.append(
                PlanningConstraint(
                    text="Active uncommitted changes — plan should account for current WIP",
                    source="Git Context",
                )
            )

        project = ctx.project_context
        if project:
            if project.ci_cd:
                ci = ", ".join(project.ci_cd)
                constraints.append(
                    PlanningConstraint(
                        text=f"Must integrate with existing CI/CD ({ci})",
                        source="Project Context",
                    )
                )
            if project.framework and project.language:
                constraints.append(
                    PlanningConstraint(
                        text=(
                            f"Must remain compatible with "
                            f"{display_framework(project.framework)} / "
                            f"{display_language(project.language)}"
                        ),
                        source="Project Context",
                    )
                )

        for goal in ctx.user_context.goals[:3]:
            constraints.append(
                PlanningConstraint(
                    text=f"Align with user goal: {goal}",
                    source="User Context",
                )
            )

        return constraints

    def identify_assumptions(self, ctx: PlanningContext, goal: str) -> list[str]:
        del goal
        assumptions: list[str] = []
        if ctx.project_context is None:
            assumptions.append("Assuming greenfield project (no cached project context)")
        if ctx.workspace_context is None:
            assumptions.append("Assuming single-project scope (no workspace cache)")
        if ctx.project_context and ctx.project_context.framework:
            fw = display_framework(ctx.project_context.framework)
            assumptions.append(f"Assuming {fw} stack based on current project detection")
        if ctx.project_context:
            assumptions.append(
                "Assuming deployment will occur in the current repository environment"
            )
        return assumptions

    def evaluate_readiness(
        self,
        ctx: PlanningContext,
        *,
        force_plan: bool = False,
    ) -> tuple[str, float, list[ContextGap]]:
        gaps = list(ctx.gaps)
        context_quality = calculate_context_quality(
            ctx.user_context,
            ctx.project_context,
            ctx.workspace_context,
            ctx.git_context,
        )
        critical_count = len(critical_dimension_gaps(gaps))
        important_count = len(important_dimension_gaps(gaps))
        confidence = calculate_confidence(
            context_quality,
            len(ctx.knowns),
            critical_count,
            important_count,
            len(ctx.assumptions),
        )

        if context_quality < MINIMUM_CONTEXT_THRESHOLD or len(ctx.knowns) < MIN_KNOWNS_FOR_PLAN:
            return "insufficient_context", confidence, gaps
        if structural_gaps(gaps):
            return "insufficient_context", confidence, gaps
        if len(ctx.assumptions) > MAX_ASSUMPTIONS:
            return "clarification_required", confidence, gaps
        if critical_count > 0:
            return "clarification_required", confidence, gaps
        if important_count > MAX_IMPORTANT_GAPS:
            return "clarification_required", confidence, gaps
        if confidence < MIN_CONFIDENCE_FOR_PLAN:
            return "clarification_required", confidence, gaps

        allowed, _ = can_generate_plan(
            confidence,
            len(ctx.knowns),
            critical_count,
            important_count,
            len(ctx.assumptions),
        )
        if not allowed:
            return "clarification_required", confidence, gaps

        if not force_plan and has_blocking_gaps(gaps):
            return "clarification_required", confidence, gaps

        return "ready_to_plan", confidence, gaps

    def generate_plan(
        self,
        goal: str,
        ctx: PlanningContext,
        *,
        knowns: list[PlanningKnown] | None = None,
        gaps: list[ContextGap] | None = None,
        assumptions: list[str] | None = None,
        constraints: list[PlanningConstraint] | None = None,
    ) -> str:
        provider = self._provider or get_llm_provider(self._config)
        if provider is None:
            raise RuntimeError("No LLM provider configured. Run smith setup.")
        prompt = build_compact_planning_prompt(
            goal,
            ctx,
            knowns=knowns or ctx.knowns,
            gaps=gaps or ctx.gaps,
            assumptions=assumptions or ctx.assumptions,
            constraints=constraints or ctx.constraints,
        )
        plan = provider.generate(prompt, system=_PLAN_SYSTEM)
        return _validate_plan_length(plan)

    def create_plan(
        self,
        goal: str,
        *,
        prioritize: bool = False,
        force_plan: bool = False,
    ) -> PlanningResult:
        ctx = self.build_context(goal)
        gaps = ctx.gaps
        if prioritize:
            gaps = prioritize_gaps_with_llm(
                gaps, goal, provider=self._provider, config=self._config
            )
            ctx.gaps = gaps

        mode, confidence, gaps = self.evaluate_readiness(ctx, force_plan=force_plan)
        ctx.gaps = gaps
        questions = generate_questions_from_gaps(gaps)

        plan_text: str | None = None
        if mode == "ready_to_plan":
            allowed, _ = can_generate_plan(
                confidence,
                len(ctx.knowns),
                len(critical_dimension_gaps(gaps)),
                len(important_dimension_gaps(gaps)),
                len(ctx.assumptions),
            )
            if allowed:
                plan_text = self.generate_plan(goal, ctx, gaps=gaps)

        planning_mode = mode
        if mode == "ready_to_plan" and plan_text is None:
            planning_mode = "clarification_required"

        result = PlanningResult(
            goal=goal,
            knowns=ctx.knowns,
            gaps=gaps,
            assumptions=ctx.assumptions,
            constraints=ctx.constraints,
            decisions=ctx.decisions,
            questions=questions,
            plan=plan_text,
            confidence=confidence,
            planning_mode=planning_mode,
        )
        set_last_planning_result(result)
        return result

    def assess_readiness(self, goal: str | None = None) -> PlanningReadiness:
        ctx = self.build_context(goal)
        mode, confidence, gaps = self.evaluate_readiness(ctx)
        return PlanningReadiness(
            known_count=len(ctx.knowns),
            gap_count=len(gaps),
            critical_gap_count=len(critical_dimension_gaps(gaps)),
            important_gap_count=len(important_dimension_gaps(gaps)),
            assumption_count=len(ctx.assumptions),
            constraint_count=len(ctx.constraints),
            context_quality=calculate_context_quality(
                ctx.user_context,
                ctx.project_context,
                ctx.workspace_context,
                ctx.git_context,
            ),
            confidence=confidence,
            status=_mode_label(mode),
        )


def prioritize_gaps_with_llm(
    gaps: list[ContextGap],
    goal: str,
    *,
    provider: LLMProvider | None = None,
    config: Config | None = None,
) -> list[ContextGap]:
    dimension_gaps = [g for g in gaps if g.dimension is not None]
    if len(dimension_gaps) <= 1:
        return gaps

    llm = provider or get_llm_provider(config or Config.load())
    if llm is None:
        return gaps

    dim_lines = [
        f"- {g.dimension.value}: {g.name}" for g in dimension_gaps if g.dimension
    ]
    prompt = f"Goal: {goal}\nDimensions:\n" + "\n".join(dim_lines)
    try:
        raw = llm.generate(prompt, system=_RANK_SYSTEM)
        data = json.loads(raw)
        order = [str(item) for item in data.get("order", [])]
    except (json.JSONDecodeError, TypeError, AttributeError):
        logger.debug("Gap prioritization returned invalid JSON")
        return gaps

    by_dim = {g.dimension: g for g in dimension_gaps if g.dimension}
    expected_ids = {d.value for d in by_dim}
    if len(order) != len(by_dim) or set(order) != expected_ids:
        return gaps

    reordered_dims: list[ContextGap] = []
    for dim_id in order:
        try:
            dim = PlanningDimension(dim_id)
        except ValueError:
            continue
        if dim in by_dim and dim not in {g.dimension for g in reordered_dims}:
            reordered_dims.append(by_dim[dim])

    for gap in dimension_gaps:
        if gap not in reordered_dims:
            reordered_dims.append(gap)

    reordered = structural_gaps(gaps) + reordered_dims
    optional = [g for g in gaps if g.severity == GapSeverity.OPTIONAL and g not in reordered]
    reordered.extend(optional)

    if not validate_gap_order(gaps, reordered):
        return gaps
    return reordered


def can_generate_plan(
    confidence: float,
    known_count: int,
    critical_gap_count: int,
    important_gap_count: int,
    assumption_count: int,
) -> tuple[bool, str]:
    if confidence < MIN_CONFIDENCE_FOR_PLAN:
        return False, "Confidence below minimum threshold"
    if known_count < MIN_KNOWNS_FOR_PLAN:
        return False, "Too few known facts"
    if critical_gap_count > 0:
        return False, "Critical planning gaps remain"
    if important_gap_count > MAX_IMPORTANT_GAPS:
        return False, "Too many important gaps"
    if assumption_count > MAX_ASSUMPTIONS:
        return False, "Too many assumptions"
    return True, ""


def build_compact_planning_prompt(
    goal: str,
    ctx: PlanningContext,
    *,
    knowns: list[PlanningKnown],
    gaps: list[ContextGap],
    assumptions: list[str],
    constraints: list[PlanningConstraint],
) -> str:
    user = ctx.user_context
    lines = [f"Goal: {goal}"]
    if user.primary_languages:
        lines.append(f"User languages: {', '.join(user.primary_languages[:3])}")
    if user.preferred_frameworks:
        lines.append(f"User frameworks: {', '.join(user.preferred_frameworks[:3])}")
    if user.goals:
        lines.append(f"User goals: {', '.join(user.goals[:3])}")

    project = ctx.project_context
    if project:
        lines.append(
            "Project: "
            f"{display_language(project.language)} / "
            f"{display_framework(project.framework)} / "
            f"{display_build(project.build_system)}"
        )

    workspace = ctx.workspace_context
    if workspace:
        tech: list[str] = []
        tech.extend(list(workspace.languages.keys())[:3])
        tech.extend(list(workspace.frameworks.keys())[:3])
        if tech:
            lines.append(f"Workspace technologies: {', '.join(tech[:5])}")

    git = ctx.git_context
    if git:
        state = "clean" if git.is_clean else "dirty"
        lines.append(f"Git: branch {git.branch}, {state}")

    if knowns:
        lines.append("Knowns:")
        lines.extend(f"- {item.text}" for item in knowns[:10])
    if constraints:
        lines.append("Constraints:")
        lines.extend(f"- {item.text}" for item in constraints[:8])
    if assumptions:
        lines.append("Assumptions:")
        lines.extend(f"- {item}" for item in assumptions[:5])
    if gaps:
        lines.append("Remaining gaps:")
        for gap in gaps[:8]:
            lines.append(f"- {gap.name}: {gap.reason.splitlines()[0]}")

    lines.append(
        "Produce markdown with sections: Goal, Knowns, Constraints, Plan "
        "(Phase 1-3), Risks, Confidence."
    )
    return "\n".join(lines)[:MAX_PROMPT_CHARS]


def _validate_plan_length(plan: str) -> str:
    steps = len(re.findall(r"^\s*(?:\d+\.|[-*])\s+", plan, flags=re.MULTILINE))
    if steps > MAX_PLAN_STEPS:
        lines = plan.splitlines()
        return "\n".join(lines[: MAX_PLAN_STEPS + 20])
    return plan


def _mode_label(mode: str) -> str:
    return {
        "insufficient_context": "Insufficient Context",
        "clarification_required": "Clarification Required",
        "ready_to_plan": "Ready to Plan",
    }.get(mode, mode.replace("_", " ").title())


def format_planning_readiness(readiness: PlanningReadiness) -> str:
    lines = [
        "Planning Readiness",
        f"Knowns: {readiness.known_count}",
        f"Gaps: {readiness.gap_count}",
        f"Critical gaps: {readiness.critical_gap_count}",
        f"Important gaps: {readiness.important_gap_count}",
        f"Assumptions: {readiness.assumption_count}",
        f"Constraints: {readiness.constraint_count}",
        f"Context Quality: {readiness.context_quality:.0%}",
        f"Status: {readiness.status}",
        f"Confidence: {readiness.confidence:.0%}",
        "",
        "Planning Philosophy",
        "Evidence-based",
        "Deterministic-first",
        "Read-only",
        "Context gaps, not domain templates",
    ]
    return "\n".join(lines)


def format_planning_result(result: PlanningResult) -> str:
    lines = [
        f"Goal: {result.goal}",
        f"Mode: {_mode_label(result.planning_mode)}",
        f"Confidence: {result.confidence:.0%}",
        "",
    ]
    if result.knowns:
        lines.append("Knowns:")
        for known in result.knowns[:10]:
            lines.append(f"- {known.text}")
        lines.append("")
    if result.gaps:
        lines.append("Detected Gaps:")
        for gap in result.gaps[:10]:
            lines.append(f"- {gap.name} ({gap.severity.value})")
        lines.append("")
    if result.assumptions:
        lines.append("Assumptions:")
        for assumption in result.assumptions:
            lines.append(f"- {assumption}")
        lines.append("")
    if result.questions:
        lines.append("Questions:")
        for idx, question in enumerate(result.questions, start=1):
            lines.append(f"{idx}. {question.question}")
            lines.append(f"   Reason: {question.reason}")
        lines.append("")
        if result.planning_mode != "ready_to_plan":
            lines.append("Next: smith plan answer <dimension>=<value>")
            lines.append("")
    if result.plan:
        lines.append(result.plan)
    elif result.planning_mode != "ready_to_plan":
        lines.append("No plan generated — provide answers and run smith plan-refresh.")
    return "\n".join(lines).rstrip()


def format_planning_explain(
    ctx: PlanningContext,
    *,
    gaps: list[ContextGap] | None = None,
) -> str:
    gap_list = gaps if gaps is not None else ctx.gaps
    lines = ["Planning Explanation", "", "Knowns", ""]
    for known in ctx.knowns:
        lines.append(f"✓ {known.text}")
        lines.append(f"  Source: {known.source}")
        if known.evidence:
            lines.append("  Evidence:")
            lines.extend(f"  - {item}" for item in known.evidence)
        else:
            lines.append("  Evidence: —")
        lines.append("")

    lines.extend(["Detected Gaps", ""])
    for gap in gap_list:
        lines.append(f"! {gap.name}")
        lines.append("  Reason:")
        for reason_line in gap.reason.splitlines():
            lines.append(f"  {reason_line}")
        lines.append("")

    if ctx.decisions:
        lines.extend(["Explicit Decisions", ""])
        for decision in ctx.decisions:
            label = decision.dimension.value.replace("_", " ").title()
            lines.append(f"• {label}: {decision.answer}")
            lines.append("  Source: User Answer")
            lines.append("")

    lines.extend(["Constraints", ""])
    for constraint in ctx.constraints:
        lines.append(f"! {constraint.text}")
        lines.append(f"  Source: {constraint.source}")
        lines.append("")

    if ctx.assumptions:
        lines.extend(["Assumptions", ""])
        for assumption in ctx.assumptions:
            lines.append(f"• {assumption}")
        lines.append("")

    return "\n".join(lines).rstrip()
