"""Context confidence scoring for evidence bundles."""

from __future__ import annotations

from pathlib import Path

from smith.models.assistant import ContextConfidence, EvidenceItem


def evaluate_confidence(
    items: list[EvidenceItem],
    paths: dict[str, Path],
) -> ContextConfidence:
    repo_score = 1.0 if paths else 0.3 if items else 0.0
    framework_score = 0.0
    architecture_score = 0.0
    for item in items:
        meta = item.metadata or {}
        if meta.get("language") or meta.get("framework"):
            framework_score = max(framework_score, 0.8)
        modules = meta.get("modules", 0)
        if isinstance(modules, list) and modules:
            architecture_score = max(architecture_score, 0.75)
        elif isinstance(modules, int) and modules > 0:
            architecture_score = max(architecture_score, 0.75)
        if item.source == "analyze":
            if meta.get("language"):
                framework_score = max(framework_score, 0.85)
            modules = meta.get("modules", 0)
            if isinstance(modules, int) and modules > 0:
                architecture_score = max(architecture_score, 0.9)
            elif isinstance(modules, list) and modules:
                architecture_score = max(architecture_score, 0.9)
            elif meta.get("health_score"):
                architecture_score = max(architecture_score, 0.5)
        if item.source == "filesystem":
            level = meta.get("evidence_level")
            if level == "configuration":
                framework_score = max(framework_score, 0.7)
            if level == "structure":
                architecture_score = max(architecture_score, 0.65)
        if item.source == "repository_knowledge":
            framework_score = max(framework_score, 0.85)
            architecture_score = max(architecture_score, 0.85)
    if items and framework_score == 0.0:
        framework_score = 0.4
    if items and architecture_score == 0.0:
        architecture_score = 0.35
    understanding = min(
        1.0,
        (repo_score + framework_score + architecture_score) / 3 + min(0.15, len(items) * 0.05),
    )
    return ContextConfidence(
        repository_identification=round(repo_score, 3),
        framework_detection=round(framework_score, 3),
        architecture_detection=round(architecture_score, 3),
        project_understanding=round(understanding, 3),
    )
