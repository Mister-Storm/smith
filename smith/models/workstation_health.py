import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from smith.services.doctor import CheckResult, CheckStatus

WORKSTATION_HEALTH_SCHEMA_VERSION = 1
WORKSTATION_HEALTH_CACHE_FILE = "workstation_health.json"


@dataclass(slots=True)
class CachedHealthRecommendation:
    title: str
    suggested_command: str | None = None


@dataclass(slots=True)
class WorkstationHealthCache:
    schema_version: int = WORKSTATION_HEALTH_SCHEMA_VERSION
    generated_at: str = ""
    score: int = 0
    issues: list[str] = field(default_factory=list)
    recommendations: list[CachedHealthRecommendation] = field(default_factory=list)
    scanned_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "score": self.score,
            "issues": self.issues,
            "recommendations": [asdict(r) for r in self.recommendations],
            "scanned_paths": self.scanned_paths,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkstationHealthCache":
        recs = [
            CachedHealthRecommendation(
                title=r.get("title", ""),
                suggested_command=r.get("suggested_command"),
            )
            for r in data.get("recommendations", [])
        ]
        return cls(
            schema_version=int(data.get("schema_version", WORKSTATION_HEALTH_SCHEMA_VERSION)),
            generated_at=data.get("generated_at", ""),
            score=int(data.get("score", 0)),
            issues=list(data.get("issues", [])),
            recommendations=recs,
            scanned_paths=list(data.get("scanned_paths", [])),
        )

    @classmethod
    def from_json(cls, text: str) -> "WorkstationHealthCache":
        return cls.from_dict(json.loads(text))

    @classmethod
    def from_report(cls, report: "WorkstationHealthReport") -> "WorkstationHealthCache":
        return cls(
            schema_version=WORKSTATION_HEALTH_SCHEMA_VERSION,
            generated_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            score=report.score,
            issues=report.issues[:5],
            recommendations=[
                CachedHealthRecommendation(
                    title=r.title,
                    suggested_command=r.suggested_command,
                )
                for r in report.recommendations[:5]
            ],
            scanned_paths=report.scanned_paths,
        )


@dataclass(slots=True)
class RawFinding:
    scanner: str
    category: str
    severity: CheckStatus
    key: str
    summary: str
    detail_lines: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConsolidatedFinding:
    key: str
    category: str
    primary_scanner: str
    severity: CheckStatus
    summary: str
    detail_lines: list[str] = field(default_factory=list)
    related_scanners: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CorrelationInsight:
    related_keys: list[str]
    insight: str


@dataclass(slots=True)
class Recommendation:
    severity: str
    category: str
    title: str
    detail: str
    impact_reason: str | None = None
    suggested_command: str | None = None
    correlated_insight: str | None = None
    finding_keys: list[str] = field(default_factory=list)


@dataclass(slots=True)
class WorkstationHealthReport:
    score: int
    score_breakdown: dict[str, int]
    issues: list[str]
    recommendations: list[Recommendation]
    correlations: list[CorrelationInsight]
    findings: list[ConsolidatedFinding]
    sections: list[tuple[str, CheckResult]]
    scanned_paths: list[str]

    @property
    def exit_code(self) -> int:
        if self.score >= 80:
            return 0
        if self.score >= 50:
            return 1
        return 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "score_breakdown": self.score_breakdown,
            "issues": self.issues,
            "correlations": [asdict(c) for c in self.correlations],
            "recommendations": [asdict(r) for r in self.recommendations],
            "findings": [
                {
                    "key": f.key,
                    "category": f.category,
                    "primary_scanner": f.primary_scanner,
                    "severity": f.severity.value,
                    "summary": f.summary,
                    "detail_lines": f.detail_lines,
                    "related_scanners": f.related_scanners,
                    "metrics": f.metrics,
                }
                for f in self.findings
            ],
            "sections": [
                {"title": title, "status": check.status.value, "lines": check.lines}
                for title, check in self.sections
            ],
            "scanned_paths": self.scanned_paths,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkstationHealthReport":
        findings = [
            ConsolidatedFinding(
                key=f["key"],
                category=f["category"],
                primary_scanner=f["primary_scanner"],
                severity=CheckStatus(f["severity"]),
                summary=f["summary"],
                detail_lines=f.get("detail_lines", []),
                related_scanners=f.get("related_scanners", []),
                metrics=f.get("metrics", {}),
            )
            for f in data.get("findings", [])
        ]
        correlations = [
            CorrelationInsight(related_keys=c["related_keys"], insight=c["insight"])
            for c in data.get("correlations", [])
        ]
        recommendations = [
            Recommendation(
                severity=r["severity"],
                category=r["category"],
                title=r["title"],
                detail=r["detail"],
                impact_reason=r.get("impact_reason"),
                suggested_command=r.get("suggested_command"),
                correlated_insight=r.get("correlated_insight"),
                finding_keys=r.get("finding_keys", []),
            )
            for r in data.get("recommendations", [])
        ]
        sections = [
            (s["title"], CheckResult(status=CheckStatus(s["status"]), lines=s["lines"]))
            for s in data.get("sections", [])
        ]
        return cls(
            score=data["score"],
            score_breakdown=data.get("score_breakdown", {}),
            issues=data.get("issues", []),
            recommendations=recommendations,
            correlations=correlations,
            findings=findings,
            sections=sections,
            scanned_paths=data.get("scanned_paths", []),
        )
