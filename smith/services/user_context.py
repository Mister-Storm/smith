"""User context aggregation and profile rendering."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from smith.models.project_context import ProjectContext
from smith.models.user_context import (
    ProfileCompletenessResult,
    ProvenanceEntry,
    UserContext,
    UserContextDerived,
    UserContextDocument,
    UserContextExplanation,
    UserContextProvenance,
)
from smith.models.workspace import WorkspaceSummary
from smith.services.context_inference import apply_inference, infer_project_context
from smith.services.domain_mapping import DOMAIN_KEYWORDS, score_domains, top_domains
from smith.services.project_context import (
    ProjectContextService,
    display_framework,
    display_language,
)
from smith.services.user_context_store import UserContextStore
from smith.services.workspace_intelligence import WorkspaceIntelligenceService

logger = logging.getLogger(__name__)

TOP_N = 5

COMPLETENESS_WEIGHTS = {
    "interests": 15,
    "goals": 15,
    "primary_languages": 20,
    "preferred_frameworks": 15,
    "working_domains": 15,
    "active_projects": 20,
}

SUGGESTED_COMMANDS = {
    "interests": "smith profile set-interest drones",
    "goals": "smith profile set-goal build-open-source-ai-assistant",
    "primary_languages": "smith refresh-workspace-context",
    "preferred_frameworks": "smith refresh-context .",
    "working_domains": "smith profile refresh",
    "active_projects": "smith workspace .",
}


def compute_profile_completeness(ctx: UserContext) -> ProfileCompletenessResult:
    score = 0
    missing: list[str] = []
    suggested: list[str] = []

    checks = {
        "interests": bool(ctx.interests),
        "goals": bool(ctx.goals),
        "primary_languages": bool(ctx.primary_languages),
        "preferred_frameworks": bool(ctx.preferred_frameworks),
        "working_domains": bool(ctx.working_domains),
        "active_projects": bool(ctx.active_projects),
    }
    for field, present in checks.items():
        weight = COMPLETENESS_WEIGHTS[field]
        if present:
            score += weight
        else:
            missing.append(field.replace("_", " "))
            cmd = SUGGESTED_COMMANDS.get(field)
            if cmd and cmd not in suggested:
                suggested.append(cmd)

    return ProfileCompletenessResult(
        score=min(100, score),
        missing=missing,
        suggested_commands=suggested,
    )


def _merge_document(doc: UserContextDocument) -> UserContext:
    ctx = UserContext(
        interests=list(doc.user.interests),
        goals=list(doc.user.goals),
        primary_languages=list(doc.derived.primary_languages),
        preferred_frameworks=list(doc.derived.preferred_frameworks),
        working_domains=list(doc.derived.working_domains),
        active_projects=list(doc.derived.active_projects),
        recent_projects=list(doc.derived.recent_projects),
        generated_at=_parse_generated_at(doc.generated_at),
        confidence=doc.confidence,
        confidence_reason=doc.confidence_reason,
        profile_completeness=0,
    )
    ctx.profile_completeness = compute_profile_completeness(ctx).score
    return ctx


def _parse_generated_at(value: str) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return datetime.now(UTC)


def _top_counter(items: list[str], *, limit: int = TOP_N) -> list[str]:
    ranked = Counter(items).most_common()
    return [name for name, _ in ranked[:limit]]


def _readme_snippet(project_path: Path) -> str:
    readme = project_path / "README.md"
    if not readme.is_file():
        return ""
    try:
        return readme.read_text(encoding="utf-8", errors="replace").splitlines()[0][:120]
    except OSError:
        return ""


class UserContextService:
    def __init__(self, workspace_root: Path | None = None) -> None:
        self._workspace_root = (workspace_root or Path.cwd()).expanduser().resolve()
        self._project_service = ProjectContextService()
        self._store = UserContextStore()

    def load(self) -> UserContext:
        return _merge_document(self._store.load())

    def build(self, *, infer: bool = False) -> tuple[UserContext, UserContextDocument]:
        existing = self._store.load()
        doc = self._derive_document(existing.user, infer=infer)
        return _merge_document(doc), doc

    def refresh(self, *, infer: bool = False) -> UserContext:
        existing = self._store.load()
        doc = self._derive_document(existing.user, infer=infer)
        self._store.save(doc)
        return _merge_document(doc)

    def explain(self) -> UserContextExplanation:
        doc = self._store.load()
        fields: list[tuple[str, str, ProvenanceEntry]] = []

        def add_section(category: str, provenance_map: dict[str, ProvenanceEntry]) -> None:
            for value, entry in provenance_map.items():
                fields.append((category, value, entry))

        add_section("Interest", doc.provenance.interests)
        add_section("Goal", doc.provenance.goals)
        add_section("Language", doc.provenance.primary_languages)
        add_section("Framework", doc.provenance.preferred_frameworks)
        add_section("Domain", doc.provenance.working_domains)
        add_section("Active Project", doc.provenance.active_projects)
        add_section("Recent Project", doc.provenance.recent_projects)

        for interest in doc.user.interests:
            if interest not in doc.provenance.interests:
                fields.append(
                    (
                        "Interest",
                        interest,
                        ProvenanceEntry(source="user", evidence=[], reason="User-defined"),
                    )
                )
        for goal in doc.user.goals:
            if goal not in doc.provenance.goals:
                fields.append(
                    (
                        "Goal",
                        goal,
                        ProvenanceEntry(source="user", evidence=[], reason="User-defined"),
                    )
                )

        return UserContextExplanation(fields=fields)

    def set_interest(self, value: str) -> UserContext:
        doc = self._store.load()
        normalized = value.strip()
        if normalized and normalized not in doc.user.interests:
            doc.user.interests.append(normalized)
            doc.provenance.interests[normalized] = ProvenanceEntry(
                source="user", evidence=[], reason="User-defined"
            )
        self._store.save(doc)
        return _merge_document(doc)

    def remove_interest(self, value: str) -> UserContext:
        doc = self._store.load()
        normalized = value.strip()
        doc.user.interests = [i for i in doc.user.interests if i != normalized]
        doc.provenance.interests.pop(normalized, None)
        self._store.save(doc)
        return _merge_document(doc)

    def set_goal(self, value: str) -> UserContext:
        doc = self._store.load()
        normalized = value.strip()
        if normalized and normalized not in doc.user.goals:
            doc.user.goals.append(normalized)
            doc.provenance.goals[normalized] = ProvenanceEntry(
                source="user", evidence=[], reason="User-defined"
            )
        self._store.save(doc)
        return _merge_document(doc)

    def remove_goal(self, value: str) -> UserContext:
        doc = self._store.load()
        normalized = value.strip()
        doc.user.goals = [g for g in doc.user.goals if g != normalized]
        doc.provenance.goals.pop(normalized, None)
        self._store.save(doc)
        return _merge_document(doc)

    def _derive_document(self, user_overrides, *, infer: bool = False) -> UserContextDocument:
        workspace = WorkspaceIntelligenceService(self._workspace_root).load_workspace_context()
        project_contexts: list[tuple[str, Path, ProjectContext]] = []

        if workspace and workspace.projects:
            for wp in workspace.projects:
                path = Path(wp.path)
                ctx = self._project_service.load(path)
                if ctx is None:
                    continue
                project_contexts.append((wp.name, path, ctx))
        else:
            cwd_ctx = self._project_service.load(self._workspace_root)
            if cwd_ctx:
                project_contexts.append((self._workspace_root.name, self._workspace_root, cwd_ctx))

        pre_confidence = self._estimate_pre_confidence(workspace, project_contexts)

        if infer:
            enriched: list[tuple[str, Path, ProjectContext]] = []
            for name, path, ctx in project_contexts:
                inference = infer_project_context(path, ctx, workspace_confidence=pre_confidence)
                if inference:
                    ctx = apply_inference(ctx, inference)
                enriched.append((name, path, ctx))
            project_contexts = enriched

        languages: list[str] = []
        frameworks: list[str] = []
        lang_prov: dict[str, ProvenanceEntry] = {}
        fw_prov: dict[str, ProvenanceEntry] = {}
        domain_texts: list[str] = list(user_overrides.interests)

        for name, path, ctx in project_contexts:
            if ctx.language:
                lang = display_language(ctx.language)
                languages.append(lang)
                entry = lang_prov.setdefault(
                    lang,
                    ProvenanceEntry(source="deterministic", evidence=[], reason=""),
                )
                entry.evidence.append(name)
                if (path / "pyproject.toml").is_file():
                    entry.evidence.append("pyproject.toml")
            if ctx.framework:
                fw = display_framework(ctx.framework)
                frameworks.append(fw)
                entry = fw_prov.setdefault(
                    fw,
                    ProvenanceEntry(source="deterministic", evidence=[], reason=""),
                )
                entry.evidence.append(name)
            domain_texts.extend([name, _readme_snippet(path)])

        if workspace:
            for lang, count in workspace.languages.items():
                languages.extend([lang] * count)
            for fw, count in workspace.frameworks.items():
                frameworks.extend([fw] * count)

        primary_languages = _top_counter(languages)
        preferred_frameworks = _top_counter(frameworks)

        for lang in primary_languages:
            lang_prov.setdefault(
                lang,
                ProvenanceEntry(source="deterministic", evidence=[lang], reason="Frequency rank"),
            )
        for fw in preferred_frameworks:
            fw_prov.setdefault(
                fw,
                ProvenanceEntry(source="deterministic", evidence=[fw], reason="Frequency rank"),
            )

        domain_scores = score_domains(domain_texts)
        working_domains = top_domains(domain_texts, limit=TOP_N)
        domain_prov: dict[str, ProvenanceEntry] = {}
        for domain in working_domains:
            keywords = DOMAIN_KEYWORDS.get(domain, [])
            matched = [k for k in keywords if any(k in t.lower() for t in domain_texts)]
            domain_prov[domain] = ProvenanceEntry(
                source="deterministic",
                evidence=matched[:5],
                reason=f"Matched keywords in {domain_scores.get(domain, 0)} signal(s)",
                confidence=min(1.0, 0.5 + 0.1 * domain_scores.get(domain, 0)),
            )

        active_projects: list[str] = []
        recent_projects: list[str] = []
        active_prov: dict[str, ProvenanceEntry] = {}
        recent_prov: dict[str, ProvenanceEntry] = {}

        if workspace:
            active_projects = list(workspace.active_projects[:TOP_N])
            if not active_projects:
                active_projects = [p.name for p in workspace.projects[:TOP_N]]
            for name in active_projects:
                active_prov[name] = ProvenanceEntry(
                    source="deterministic",
                    evidence=[name],
                    reason="Listed as active in workspace cache",
                )
            recent_projects = [p.name for p in workspace.projects[:TOP_N]]
            for name in recent_projects:
                recent_prov[name] = ProvenanceEntry(
                    source="deterministic",
                    evidence=[name],
                    reason="Recent activity from workspace cache",
                )

        projects_analyzed = len(project_contexts)
        active_count = len(active_projects)
        framework_count = len(set(frameworks))
        has_workspace = workspace is not None
        confidence = min(
            1.0,
            0.1
            + 0.08 * projects_analyzed
            + 0.05 * active_count
            + 0.04 * framework_count
            + (0.15 if has_workspace else 0.0),
        )

        reason_lines = [
            "Based on:",
            f"- {projects_analyzed} analyzed projects",
            f"- {active_count} active repositories",
            f"- {framework_count} detected frameworks",
        ]
        if has_workspace:
            reason_lines.append("- workspace cache available")
        else:
            reason_lines.append("- workspace cache missing")

        derived = UserContextDerived(
            primary_languages=primary_languages,
            preferred_frameworks=preferred_frameworks,
            working_domains=working_domains,
            active_projects=active_projects,
            recent_projects=recent_projects,
        )

        provenance = UserContextProvenance(
            primary_languages=lang_prov,
            preferred_frameworks=fw_prov,
            working_domains=domain_prov,
            active_projects=active_prov,
            recent_projects=recent_prov,
            interests={
                i: ProvenanceEntry(source="user", evidence=[], reason="User-defined")
                for i in user_overrides.interests
            },
            goals={
                g: ProvenanceEntry(source="user", evidence=[], reason="User-defined")
                for g in user_overrides.goals
            },
        )

        return UserContextDocument(
            generated_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            confidence=round(confidence, 2),
            confidence_reason="\n".join(reason_lines),
            derived=derived,
            user=user_overrides,
            provenance=provenance,
        )

    @staticmethod
    def _estimate_pre_confidence(
        workspace: WorkspaceSummary | None,
        projects: list[tuple[str, Path, ProjectContext]],
    ) -> float:
        count = len(projects)
        has_ws = workspace is not None
        return min(1.0, 0.1 + 0.08 * count + (0.15 if has_ws else 0.0))


def _append_profile_section(lines: list[str], title: str, items: list[str]) -> None:
    lines.extend(["", title])
    if items:
        lines.extend(f"- {item}" for item in items)
    else:
        lines.append("- —")


def format_user_profile(ctx: UserContext) -> str:
    completeness = compute_profile_completeness(ctx)
    lines = ["User Profile"]
    _append_profile_section(lines, "Interests", ctx.interests)
    _append_profile_section(lines, "Goals", ctx.goals)
    _append_profile_section(lines, "Primary Languages", ctx.primary_languages)
    _append_profile_section(lines, "Preferred Frameworks", ctx.preferred_frameworks)
    _append_profile_section(lines, "Working Domains", ctx.working_domains)
    _append_profile_section(lines, "Active Projects", ctx.active_projects)
    _append_profile_section(lines, "Recent Projects", ctx.recent_projects)
    lines.extend(
        [
            "",
            f"Confidence: {ctx.confidence:.0%}",
            "",
            "Reason:",
            ctx.confidence_reason,
            "",
            f"Profile Completeness: {completeness.score}%",
        ]
    )
    if completeness.missing:
        lines.append("")
        lines.append("Missing:")
        for item in completeness.missing:
            lines.append(f"- {item}")
    if completeness.suggested_commands:
        lines.append("")
        lines.append("Suggested:")
        for cmd in completeness.suggested_commands:
            lines.append(cmd)
    age = ctx.age_days()
    if age is not None:
        lines.extend(["", f"Last refreshed: {age} days ago", f"Status: {ctx.freshness_status()}"])
    return "\n".join(lines)


def format_user_context_explain(explanation: UserContextExplanation) -> str:
    lines = ["Profile Explanation", ""]
    for category, value, entry in explanation.fields:
        lines.append(f"{category}: {value}")
        lines.append(f"Source: {entry.source.title()}")
        if entry.evidence:
            lines.append(f"Evidence: {', '.join(entry.evidence)}")
        if entry.reason:
            lines.append(f"Reason: {entry.reason}")
        if entry.confidence is not None:
            lines.append(f"Confidence: {entry.confidence:.0%}")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_user_profile(ctx: UserContext, console) -> None:
    from rich.markup import escape
    from rich.panel import Panel
    from rich.table import Table

    console.print("[bold]User Profile[/bold]\n")
    completeness = compute_profile_completeness(ctx)

    def section_table(title: str, items: list[str]) -> None:
        table = Table(title=title, show_header=False, expand=False)
        table.add_column("Item")
        if items:
            for item in items:
                table.add_row(item)
        else:
            table.add_row("—")
        console.print(table)
        console.print()

    section_table("Interests", ctx.interests)
    section_table("Goals", ctx.goals)
    section_table("Primary Languages", ctx.primary_languages)
    section_table("Preferred Frameworks", ctx.preferred_frameworks)
    section_table("Working Domains", ctx.working_domains)
    section_table("Active Projects", ctx.active_projects)
    section_table("Recent Projects", ctx.recent_projects)

    meta = Table(show_header=True, header_style="bold")
    meta.add_column("Metric")
    meta.add_column("Value")
    meta.add_row("Confidence", f"{ctx.confidence:.0%}")
    meta.add_row("Profile Completeness", f"{completeness.score}%")
    age = ctx.age_days()
    if age is not None:
        meta.add_row("Last refreshed", f"{age} days ago")
        meta.add_row("Freshness", ctx.freshness_status())
    console.print(meta)
    console.print()

    console.print(
        Panel(
            escape(ctx.confidence_reason),
            title="Confidence Reason",
            border_style="cyan",
            expand=False,
        )
    )
    console.print()

    if completeness.missing or completeness.suggested_commands:
        hint_lines: list[str] = []
        if completeness.missing:
            hint_lines.append("Missing:")
            hint_lines.extend(f"  - {m}" for m in completeness.missing)
        if completeness.suggested_commands:
            hint_lines.append("Suggested:")
            hint_lines.extend(f"  {c}" for c in completeness.suggested_commands)
        console.print(
            Panel(
                "\n".join(escape(ln) for ln in hint_lines),
                title="Completeness",
                border_style="yellow",
                expand=False,
            )
        )


def render_user_context_explain(explanation: UserContextExplanation, console) -> None:
    from rich.markup import escape

    console.print("[bold]Profile Explanation[/bold]\n")
    for category, value, entry in explanation.fields:
        lines = [
            f"[bold]{category}:[/bold] {escape(value)}",
            f"Source: {escape(entry.source.title())}",
        ]
        if entry.evidence:
            lines.append(f"Evidence: {escape(', '.join(entry.evidence))}")
        if entry.reason:
            lines.append(f"Reason: {escape(entry.reason)}")
        if entry.confidence is not None:
            lines.append(f"Confidence: {entry.confidence:.0%}")
        console.print("\n".join(lines))
        console.print()
