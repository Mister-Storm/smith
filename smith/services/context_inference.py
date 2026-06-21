"""AI-assisted project context inference when deterministic detection gaps exist."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from smith.core.config import Config
from smith.llm.base import LLMProvider
from smith.llm.factory import get_llm_provider
from smith.models.project_context import ProjectContext

logger = logging.getLogger(__name__)

INFERENCE_CONFIDENCE_THRESHOLD = 0.40

_SYSTEM_PROMPT = (
    "You infer project metadata from a compact summary. "
    "Respond with strict JSON only, no markdown. "
    "Use null for unknown fields. "
    'Schema: {"framework": str|null, "database": [str], "build_system": str|null, "reason": str}'
)


@dataclass(slots=True)
class InferenceResult:
    framework: str | None = None
    database: list[str] | None = None
    build_system: str | None = None
    reason: str = ""


def should_infer(context: ProjectContext, *, workspace_confidence: float) -> bool:
    if workspace_confidence >= INFERENCE_CONFIDENCE_THRESHOLD:
        return False
    missing_framework = not context.framework
    missing_build = not context.build_system
    missing_db = not context.database
    return missing_framework or missing_build or missing_db


def build_compact_summary(project_root: Path) -> str:
    root = project_root.expanduser().resolve()
    lines = [f"Project Name: {root.name}"]

    files: list[str] = []
    deps: list[str] = []
    dirs: list[str] = []

    markers = (
        "pyproject.toml",
        "package.json",
        "build.gradle",
        "pom.xml",
        "Cargo.toml",
        "go.mod",
        "Dockerfile",
        "docker-compose.yml",
    )
    for name in markers:
        if (root / name).is_file():
            files.append(name)
            if name == "pyproject.toml":
                deps.extend(_extract_pyproject_deps(root / name))
            elif name == "package.json":
                deps.extend(_extract_package_deps(root / name))

    py_count = sum(1 for _ in root.rglob("*.py") if _should_count_file(root, _))
    if py_count:
        lines.append(f"Python files: {py_count}")

    if files:
        lines.append(f"Files: {', '.join(files[:10])}")
    if deps:
        lines.append(f"Dependencies: {', '.join(deps[:12])}")

    try:
        for child in sorted(root.iterdir()):
            if (
                child.is_dir()
                and not child.name.startswith(".")
                and child.name
                not in (
                    "node_modules",
                    ".venv",
                    "venv",
                )
            ):
                dirs.append(f"{child.name}/")
    except OSError:
        pass
    if dirs:
        lines.append(f"Directory Summary: {', '.join(dirs[:8])}")

    readme = root / "README.md"
    if readme.is_file():
        try:
            first_line = readme.read_text(encoding="utf-8", errors="replace").splitlines()[0][:120]
            if first_line.strip():
                lines.append(f"README: {first_line.strip()}")
        except OSError:
            pass

    return "\n".join(lines)


def _should_count_file(root: Path, path: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    parts = rel.parts
    skip = {".git", "node_modules", ".venv", "venv", ".smith", "__pycache__"}
    return not any(part in skip for part in parts)


def _extract_pyproject_deps(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return re.findall(r'["\']([\w-]+)["\']\s*=', text)[:8]


def _extract_package_deps(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    deps = data.get("dependencies", {})
    if isinstance(deps, dict):
        return list(deps.keys())[:8]
    return []


def parse_inference_response(text: str) -> InferenceResult | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    framework = data.get("framework")
    build_system = data.get("build_system")
    database = data.get("database")
    reason = data.get("reason", "")
    if framework is not None and not isinstance(framework, str):
        return None
    if build_system is not None and not isinstance(build_system, str):
        return None
    if database is not None and not isinstance(database, list):
        return None
    db_list = [str(d) for d in database] if database else []
    return InferenceResult(
        framework=framework,
        database=db_list,
        build_system=build_system,
        reason=str(reason) if reason else "",
    )


def infer_project_context(
    project_root: Path,
    context: ProjectContext,
    *,
    workspace_confidence: float,
    provider: LLMProvider | None = None,
) -> InferenceResult | None:
    if not should_infer(context, workspace_confidence=workspace_confidence):
        return None

    summary = build_compact_summary(project_root)
    prompt = (
        "Infer framework, database, and build_system from this project summary.\n\n"
        f"{summary}\n\n"
        "Return JSON only."
    )

    llm = provider or get_llm_provider(Config.load())
    try:
        raw = llm.generate(prompt, system=_SYSTEM_PROMPT)
    except Exception as exc:
        logger.warning("Context inference LLM call failed: %s", exc)
        return None

    result = parse_inference_response(raw)
    if result is None:
        logger.warning("Context inference returned invalid JSON")
    return result


def apply_inference(context: ProjectContext, inference: InferenceResult) -> ProjectContext:
    """Merge inference without overwriting deterministic values."""
    framework = context.framework or inference.framework
    build_system = context.build_system or inference.build_system
    database = list(context.database)
    if not database and inference.database:
        database = list(inference.database)
    return ProjectContext(
        project_name=context.project_name,
        language=context.language,
        framework=framework,
        build_system=build_system,
        database=database,
        infrastructure=context.infrastructure,
        ci_cd=context.ci_cd,
        modules=context.modules,
        generated_at=context.generated_at,
    )
