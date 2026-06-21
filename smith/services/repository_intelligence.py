"""Deterministic repository intelligence — architecture, quality, and risk detection."""

from __future__ import annotations

import re
from pathlib import Path

from smith.models.assistant import EvidenceBundle, RepositoryKnowledge

_LARGE_MODULE_THRESHOLD = 25


def build_repository_knowledge(
    bundle: EvidenceBundle,
    repo_path: Path,
) -> RepositoryKnowledge:
    corpus = _build_corpus(bundle)
    paths = _collect_paths(bundle, repo_path)
    modules = _extract_modules(bundle, paths)

    arch = ArchitectureDetector(corpus, paths).detect()
    quality = QualityDetector(corpus, paths, repo_path).detect()
    risks, strengths = RiskDetector(corpus, paths, modules, quality).detect()

    technologies = _detect_technologies(corpus)
    frameworks = _detect_frameworks(corpus)
    deployment = _detect_deployment(corpus, paths)
    observations = _build_observations(technologies, frameworks, modules, arch, quality, deployment)

    return RepositoryKnowledge(
        technologies=technologies,
        frameworks=frameworks,
        modules=modules,
        architectural_patterns=arch,
        strengths=strengths,
        risks=risks,
        testing_signals=quality,
        deployment_signals=deployment,
        observations=observations,
    )


class ArchitectureDetector:
    def __init__(self, corpus: str, paths: list[str]) -> None:
        self._corpus = corpus.lower()
        self._paths = [p.lower() for p in paths]

    def detect(self) -> list[str]:
        patterns: list[str] = []
        if self._has_spring_boot():
            patterns.append("Spring Boot")
        if self._has_modular_monolith():
            patterns.append("Modular Monolith")
        if self._has_ddd():
            patterns.append("Domain-Driven Design (partial)")
        if self._has_clean_architecture():
            patterns.append("Clean Architecture (partial)")
        if self._has_hexagonal():
            patterns.append("Partial Hexagonal Architecture")
        if self._has_event_driven():
            patterns.append("Event-Driven Architecture")
        if not patterns and ("fastapi" in self._corpus or "django" in self._corpus):
            patterns.append("Layered Web Application")
        return patterns

    def _has_spring_boot(self) -> bool:
        return (
            "@springbootapplication" in self._corpus.replace(" ", "")
            or "spring-boot-starter" in self._corpus
            or "org.springframework.boot" in self._corpus
        )

    def _has_modular_monolith(self) -> bool:
        module_markers = sum(1 for p in self._paths if "settings.gradle" in p or "/modules/" in p)
        gradle_modules = self._corpus.count("include(") + self._corpus.count("include '")
        return gradle_modules >= 2 or module_markers > 0

    def _has_ddd(self) -> bool:
        segments = ("domain/", "application/", "infrastructure/")
        hits = sum(1 for seg in segments if any(seg in p for p in self._paths))
        return hits >= 2

    def _has_clean_architecture(self) -> bool:
        markers = ("usecase", "use_case", "use-case", "/port/", "/adapter/")
        return sum(1 for m in markers if m in self._corpus or any(m in p for p in self._paths)) >= 2

    def _has_hexagonal(self) -> bool:
        markers = ("inbound", "outbound", "adapter", "port")
        hits = sum(1 for m in markers if any(m in p for p in self._paths))
        return hits >= 2

    def _has_event_driven(self) -> bool:
        markers = ("kafka", "rabbitmq", "eventpublisher", "event_publisher", "spring-cloud-stream")
        return any(m in self._corpus for m in markers)


class QualityDetector:
    def __init__(self, corpus: str, paths: list[str], repo_path: Path) -> None:
        self._corpus = corpus.lower()
        self._paths = [p.lower() for p in paths]
        self._repo = repo_path

    def detect(self) -> list[str]:
        signals: list[str] = []
        if self._has_test_tree():
            signals.append("Unit tests detected")
        if self._has_integration_tests():
            signals.append("Integration tests detected")
        if self._has_contract_tests():
            signals.append("Contract tests detected")
        if self._has_ci():
            signals.append("CI pipeline detected")
        else:
            signals.append("No CI pipeline detected")
        if self._has_coverage_tool():
            signals.append("Coverage tooling detected")
        else:
            signals.append("No coverage enforcement found")
        if not any("test" in s.lower() for s in signals[:3]):
            signals.append("Limited testing evidence")
        return signals

    def _has_test_tree(self) -> bool:
        test_dirs = ("src/test", "src/tests", "test/", "tests/", "__tests__")
        return any(any(td in p for td in test_dirs) for p in self._paths) or bool(
            list(self._repo.glob("**/src/test/**"))[:1] or list(self._repo.glob("**/tests/**"))[:1]
        )

    def _has_integration_tests(self) -> bool:
        markers = ("integration", "inttest", "it/")
        return any(any(m in p for m in markers) for p in self._paths)

    def _has_contract_tests(self) -> bool:
        markers = ("contract", "pact", "wiremock")
        return any(m in self._corpus or any(m in p for p in self._paths) for m in markers)

    def _has_ci(self) -> bool:
        ci_paths = (".github/workflows", ".gitlab-ci.yml", "jenkinsfile", "azure-pipelines")
        return any(any(ci in p for ci in ci_paths) for p in self._paths)

    def _has_coverage_tool(self) -> bool:
        markers = ("jacoco", "coverage.py", "pytest-cov", "istanbul", "codecov")
        return any(m in self._corpus for m in markers)


class RiskDetector:
    def __init__(
        self,
        corpus: str,
        paths: list[str],
        modules: list[str],
        quality_signals: list[str],
    ) -> None:
        self._corpus = corpus
        self._paths = paths
        self._modules = modules
        self._quality = quality_signals

    def detect(self) -> tuple[list[str], list[str]]:
        risks: list[str] = []
        strengths: list[str] = []

        if self._modules:
            strengths.append(f"Clear module separation ({len(self._modules)} modules)")
        if len(self._modules) >= 3:
            strengths.append("Multi-module organization supports bounded contexts")

        large_modules = self._large_module_risks()
        risks.extend(large_modules)

        if "Limited testing evidence" in self._quality or (
            not any("Unit tests" in s for s in self._quality)
            and any(p.endswith((".kt", ".java", ".py", ".ts")) for p in self._paths)
        ):
            risks.append("Production code present with limited test evidence")

        if "No CI pipeline detected" in self._quality:
            risks.append("No CI pipeline detected — quality gates may be manual")

        if "No coverage enforcement found" in self._quality:
            risks.append("No coverage enforcement found")

        coupling = self._coupling_risk()
        if coupling:
            risks.append(coupling)

        if not risks:
            strengths.append("No major structural risks detected from sampled evidence")

        return risks, strengths

    def _large_module_risks(self) -> list[str]:
        risks: list[str] = []
        for module in self._modules:
            prefix = module.replace(":", "/")
            count = sum(
                1 for p in self._paths if prefix in p and p.endswith((".kt", ".java", ".py"))
            )
            if count > _LARGE_MODULE_THRESHOLD:
                risks.append(
                    f"Large module '{module}' contains many source files ({count} sampled)"
                )
        return risks

    def _coupling_risk(self) -> str | None:
        if len(self._modules) < 2:
            return None
        cross_refs = 0
        for module in self._modules[:5]:
            token = module.split("/")[-1]
            if self._corpus.lower().count(token.lower()) > 8:
                cross_refs += 1
        if cross_refs >= 2 and len(self._modules) >= 3:
            names = ", ".join(self._modules[:3])
            return f"Potential high coupling between modules ({names})"
        return None


def _build_corpus(bundle: EvidenceBundle) -> str:
    parts: list[str] = []
    for item in bundle.items:
        parts.append(item.summary)
        parts.append(item.detail)
        if item.path:
            parts.append(item.path)
    return "\n".join(parts)


def _collect_paths(bundle: EvidenceBundle, repo_path: Path) -> list[str]:
    paths: list[str] = []
    for item in bundle.items:
        if item.path:
            paths.append(item.path)
        meta = item.metadata or {}
        rel = meta.get("relative_path")
        if rel:
            paths.append(str(repo_path / rel))
    return paths


def _extract_modules(bundle: EvidenceBundle, paths: list[str]) -> list[str]:
    for item in bundle.items:
        meta = item.metadata or {}
        modules = meta.get("modules")
        if isinstance(modules, list) and modules:
            return [str(m) for m in modules]
    module_names: list[str] = []
    for path in paths:
        for part in Path(path).parts:
            if part in ("modules", "services", "apps") and len(module_names) < 20:
                continue
    settings_text = ""
    for item in bundle.items:
        if "settings.gradle" in (item.path or "") or "module" in item.summary.lower():
            settings_text += item.detail
    for match in re.finditer(r"include\s*\(\s*[\"']([^\"']+)[\"']", settings_text):
        module_names.append(match.group(1))
    return sorted(set(module_names))[:20]


def _detect_technologies(corpus: str) -> list[str]:
    text = corpus.lower()
    tech: list[str] = []
    mapping = {
        "kotlin": "Kotlin",
        "java": "Java",
        "python": "Python",
        "typescript": "TypeScript",
        "javascript": "JavaScript",
        "go": "Go",
        "rust": "Rust",
        "postgresql": "PostgreSQL",
        "postgres": "PostgreSQL",
        "mysql": "MySQL",
        "redis": "Redis",
        "mongodb": "MongoDB",
    }
    for key, label in mapping.items():
        if re.search(rf"\b{re.escape(key)}\b", text):
            tech.append(label)
    return sorted(set(tech))


def _detect_frameworks(corpus: str) -> list[str]:
    text = corpus.lower()
    frameworks: list[str] = []
    mapping = {
        "spring boot": "Spring Boot",
        "spring-boot": "Spring Boot",
        "fastapi": "FastAPI",
        "django": "Django",
        "flask": "Flask",
        "react": "React",
        "next.js": "Next.js",
        "nextjs": "Next.js",
        "express": "Express",
    }
    for key, label in mapping.items():
        if key in text:
            frameworks.append(label)
    return sorted(set(frameworks))


def _detect_deployment(corpus: str, paths: list[str]) -> list[str]:
    signals: list[str] = []
    text = corpus.lower()
    if "dockerfile" in text or any("dockerfile" in p.lower() for p in paths):
        signals.append("Docker containerization detected")
    if "docker-compose" in text or any("docker-compose" in p.lower() for p in paths):
        signals.append("Docker Compose configuration detected")
    if "kubernetes" in text or "k8s" in text:
        signals.append("Kubernetes references detected")
    if "helm" in text:
        signals.append("Helm charts detected")
    return signals


def _build_observations(
    technologies: list[str],
    frameworks: list[str],
    modules: list[str],
    patterns: list[str],
    quality: list[str],
    deployment: list[str],
) -> list[str]:
    obs: list[str] = []
    if technologies:
        obs.append(f"Technologies: {', '.join(technologies)}")
    if frameworks:
        obs.append(f"Frameworks: {', '.join(frameworks)}")
    if modules:
        obs.append(f"Modules: {', '.join(modules[:8])}")
    if patterns:
        obs.append(f"Architecture: {', '.join(patterns)}")
    if quality:
        obs.append(f"Quality signals: {quality[0]}")
    if deployment:
        obs.append(deployment[0])
    return obs
