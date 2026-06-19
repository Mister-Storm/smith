import json
from dataclasses import asdict, dataclass, field
from typing import Any

from smith.services.doctor import CheckResult, CheckStatus


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
