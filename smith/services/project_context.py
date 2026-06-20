import logging
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from smith.models.project_context import ProjectContext
from smith.services.context_detection import (
    BUILD_DISPLAY,
    CI_DISPLAY,
    DATABASE_DISPLAY,
    FRAMEWORK_SLUG_TO_DISPLAY,
    INFRA_DISPLAY,
    LANGUAGE_DISPLAY,
    DetectionTrace,
    detect_project_context,
)

logger = logging.getLogger(__name__)

CONTEXT_DIR = ".smith"
CONTEXT_FILE = "project_context.json"

MISSING = "—"


def _display_language(slug: str | None) -> str:
    if not slug:
        return MISSING
    return LANGUAGE_DISPLAY.get(slug, slug.title())


def _display_framework(slug: str | None) -> str:
    if not slug:
        return MISSING
    return FRAMEWORK_SLUG_TO_DISPLAY.get(slug, slug.replace("-", " ").title())


def _display_build(slug: str | None) -> str:
    if not slug:
        return MISSING
    return BUILD_DISPLAY.get(slug, slug.title())


def _display_database(slug: str) -> str:
    return DATABASE_DISPLAY.get(slug, slug.replace("-", " ").title())


def _display_infra(slug: str) -> str:
    return INFRA_DISPLAY.get(slug, slug.replace("-", " ").title())


def _display_ci(slug: str) -> str:
    return CI_DISPLAY.get(slug, slug.replace("-", " ").title())


def display_language(slug: str | None) -> str:
    return _display_language(slug)


def display_framework(slug: str | None) -> str:
    return _display_framework(slug)


def display_build(slug: str | None) -> str:
    return _display_build(slug)


class ProjectContextService:
    @staticmethod
    def context_path(project_root: Path) -> Path:
        return project_root.expanduser().resolve() / CONTEXT_DIR / CONTEXT_FILE

    def build(self, path: Path, *, debug: bool = False) -> tuple[ProjectContext, DetectionTrace]:
        root = path.expanduser().resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"Not a directory: {root}")

        detected, trace = detect_project_context(root, debug=debug)

        context = ProjectContext(
            project_name=root.name,
            language=detected.language,
            framework=detected.framework,
            build_system=detected.build_system,
            database=detected.databases,
            infrastructure=detected.infrastructure,
            ci_cd=detected.ci_cd,
            modules=detected.modules,
            generated_at=datetime.now(UTC),
        )
        return context, trace

    def load(self, path: Path) -> ProjectContext | None:
        context_file = self.context_path(path)
        if not context_file.is_file():
            return None
        try:
            return ProjectContext.from_json(context_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError) as exc:
            logger.warning("Failed to load project context from %s: %s", context_file, exc)
            return None

    def save(self, path: Path, context: ProjectContext) -> Path:
        from smith.services.gitignore import ensure_smith_gitignore_entry

        context_file = self.context_path(path)
        context_file.parent.mkdir(parents=True, exist_ok=True)
        context_file.write_text(context.to_json(), encoding="utf-8")
        ensure_smith_gitignore_entry(path)
        logger.info("Saved project context to %s", context_file)
        return context_file

    def refresh(self, path: Path, *, debug: bool = False) -> tuple[ProjectContext, DetectionTrace]:
        context, trace = self.build(path, debug=debug)
        self.save(path, context)
        return context, trace


def render_detection_debug(trace: DetectionTrace, console: Console) -> None:
    from rich.markup import escape

    console.print("\n[bold]Detection:[/bold]")
    if trace.detections:
        for label, reason in trace.detections:
            console.print(f"✓ {escape(label)} ({escape(reason)})")
    else:
        console.print("  (none)")

    console.print("\n[bold]Ignored:[/bold]")
    if trace.ignored:
        for path in trace.ignored:
            console.print(f"* {escape(path)}")
    else:
        console.print("  (none)")


def format_context_text(context: ProjectContext) -> str:
    generated = context.generated_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")

    def bullet_list(items: list[str], *, formatter=str) -> str:
        if not items:
            return f"- {MISSING}"
        return "\n".join(f"- {formatter(i)}" for i in items)

    lines = [
        f"Project: {context.project_name}",
        "",
        "Language:",
        bullet_list([context.language] if context.language else [], formatter=_display_language),
        "",
        "Framework:",
        bullet_list([context.framework] if context.framework else [], formatter=_display_framework),
        "",
        "Build:",
        bullet_list(
            [context.build_system] if context.build_system else [], formatter=_display_build
        ),
        "",
        "Database:",
        (
            bullet_list(context.database, formatter=_display_database)
            if context.database
            else f"- {MISSING}"
        ),
        "",
        "Infrastructure:",
        bullet_list(context.infrastructure, formatter=_display_infra)
        if context.infrastructure
        else f"- {MISSING}",
        "",
        "CI/CD:",
        bullet_list(context.ci_cd, formatter=_display_ci) if context.ci_cd else f"- {MISSING}",
        "",
        "Modules:",
        bullet_list(context.modules) if context.modules else f"- {MISSING}",
        "",
        f"Generated:\n{generated}",
    ]
    return "\n".join(lines)


def render_context_tables(context: ProjectContext, console: Console) -> None:
    console.print(f"\n[bold]Project:[/bold] {context.project_name}\n")

    summary = Table(show_header=True, header_style="bold", title="Project Context")
    summary.add_column("Field", style="dim")
    summary.add_column("Value")

    summary.add_row("Language", _display_language(context.language))
    summary.add_row("Framework", _display_framework(context.framework))
    db_value = ", ".join(_display_database(d) for d in context.database) or MISSING
    summary.add_row("Database", db_value)
    summary.add_row("Build System", _display_build(context.build_system))
    summary.add_row(
        "Infrastructure",
        ", ".join(_display_infra(i) for i in context.infrastructure) or MISSING,
    )
    summary.add_row("CI/CD", ", ".join(_display_ci(c) for c in context.ci_cd) or MISSING)
    generated = context.generated_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    summary.add_row("Generated", generated)
    console.print(summary)

    if context.modules:
        modules = Table(show_header=True, header_style="bold", title="Modules")
        modules.add_column("Module")
        for module in context.modules:
            modules.add_row(module)
        console.print()
        console.print(modules)
