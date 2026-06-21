"""User context models for smith profile."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

USER_CONTEXT_SCHEMA_VERSION = 2

FRESHNESS_FRESH_DAYS = 14
FRESHNESS_WARNING_DAYS = 30


@dataclass(slots=True)
class UserContextOverrides:
    interests: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)


@dataclass(slots=True)
class UserContextDerived:
    primary_languages: list[str] = field(default_factory=list)
    preferred_frameworks: list[str] = field(default_factory=list)
    working_domains: list[str] = field(default_factory=list)
    active_projects: list[str] = field(default_factory=list)
    recent_projects: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProvenanceEntry:
    source: str  # deterministic | ai-assisted | user
    evidence: list[str] = field(default_factory=list)
    reason: str = ""
    confidence: float | None = None


@dataclass(slots=True)
class UserContextProvenance:
    primary_languages: dict[str, ProvenanceEntry] = field(default_factory=dict)
    preferred_frameworks: dict[str, ProvenanceEntry] = field(default_factory=dict)
    working_domains: dict[str, ProvenanceEntry] = field(default_factory=dict)
    active_projects: dict[str, ProvenanceEntry] = field(default_factory=dict)
    recent_projects: dict[str, ProvenanceEntry] = field(default_factory=dict)
    interests: dict[str, ProvenanceEntry] = field(default_factory=dict)
    goals: dict[str, ProvenanceEntry] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        def _entries(items: dict[str, ProvenanceEntry]) -> dict[str, Any]:
            return {k: asdict(v) for k, v in items.items()}

        return {
            "primary_languages": _entries(self.primary_languages),
            "preferred_frameworks": _entries(self.preferred_frameworks),
            "working_domains": _entries(self.working_domains),
            "active_projects": _entries(self.active_projects),
            "recent_projects": _entries(self.recent_projects),
            "interests": _entries(self.interests),
            "goals": _entries(self.goals),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserContextProvenance:
        def _parse(section: dict[str, Any]) -> dict[str, ProvenanceEntry]:
            return {
                k: ProvenanceEntry(
                    source=v.get("source", "deterministic"),
                    evidence=list(v.get("evidence", [])),
                    reason=v.get("reason", ""),
                    confidence=v.get("confidence"),
                )
                for k, v in section.items()
            }

        return cls(
            primary_languages=_parse(data.get("primary_languages", {})),
            preferred_frameworks=_parse(data.get("preferred_frameworks", {})),
            working_domains=_parse(data.get("working_domains", {})),
            active_projects=_parse(data.get("active_projects", {})),
            recent_projects=_parse(data.get("recent_projects", {})),
            interests=_parse(data.get("interests", {})),
            goals=_parse(data.get("goals", {})),
        )


@dataclass(slots=True)
class UserContextDocument:
    schema_version: int = USER_CONTEXT_SCHEMA_VERSION
    generated_at: str = ""
    confidence: float = 0.0
    confidence_reason: str = ""
    derived: UserContextDerived = field(default_factory=UserContextDerived)
    user: UserContextOverrides = field(default_factory=UserContextOverrides)
    provenance: UserContextProvenance = field(default_factory=UserContextProvenance)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "confidence": self.confidence,
            "confidence_reason": self.confidence_reason,
            "derived": asdict(self.derived),
            "user": asdict(self.user),
            "provenance": self.provenance.to_dict(),
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserContextDocument:
        derived_data = data.get("derived", {})
        user_data = data.get("user", {})
        return cls(
            schema_version=int(data.get("schema_version", USER_CONTEXT_SCHEMA_VERSION)),
            generated_at=data.get("generated_at", ""),
            confidence=float(data.get("confidence", 0.0)),
            confidence_reason=data.get("confidence_reason", ""),
            derived=UserContextDerived(
                primary_languages=list(derived_data.get("primary_languages", [])),
                preferred_frameworks=list(derived_data.get("preferred_frameworks", [])),
                working_domains=list(derived_data.get("working_domains", [])),
                active_projects=list(derived_data.get("active_projects", [])),
                recent_projects=list(derived_data.get("recent_projects", [])),
            ),
            user=UserContextOverrides(
                interests=list(user_data.get("interests", [])),
                goals=list(user_data.get("goals", [])),
            ),
            provenance=UserContextProvenance.from_dict(data.get("provenance", {})),
        )

    @classmethod
    def from_json(cls, text: str) -> UserContextDocument:
        return cls.from_dict(json.loads(text))

    @classmethod
    def empty(cls) -> UserContextDocument:
        return cls()


@dataclass(slots=True)
class UserContext:
    interests: list[str]
    goals: list[str]
    primary_languages: list[str]
    preferred_frameworks: list[str]
    working_domains: list[str]
    active_projects: list[str]
    recent_projects: list[str]
    generated_at: datetime
    confidence: float
    confidence_reason: str
    profile_completeness: int

    def age_days(self) -> int | None:
        if not self.generated_at:
            return None
        now = datetime.now(UTC)
        dt = self.generated_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return max(0, (now.date() - dt.date()).days)

    def freshness_status(self) -> str:
        days = self.age_days()
        if days is None:
            return "Missing"
        if days <= FRESHNESS_FRESH_DAYS:
            return "Fresh"
        if days <= FRESHNESS_WARNING_DAYS:
            return "Needs Refresh"
        return "Stale"

    def is_stale(self) -> bool:
        days = self.age_days()
        return days is not None and days > FRESHNESS_WARNING_DAYS

    def to_dict(self) -> dict[str, Any]:
        return {
            "interests": self.interests,
            "goals": self.goals,
            "primary_languages": self.primary_languages,
            "preferred_frameworks": self.preferred_frameworks,
            "working_domains": self.working_domains,
            "active_projects": self.active_projects,
            "recent_projects": self.recent_projects,
            "generated_at": self.generated_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "confidence": self.confidence,
            "confidence_reason": self.confidence_reason,
            "profile_completeness": self.profile_completeness,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserContext:
        generated = data.get("generated_at", "")
        if isinstance(generated, str) and generated:
            generated_at = datetime.fromisoformat(generated.replace("Z", "+00:00"))
        else:
            generated_at = datetime.now(UTC)
        return cls(
            interests=list(data.get("interests", [])),
            goals=list(data.get("goals", [])),
            primary_languages=list(data.get("primary_languages", [])),
            preferred_frameworks=list(data.get("preferred_frameworks", [])),
            working_domains=list(data.get("working_domains", [])),
            active_projects=list(data.get("active_projects", [])),
            recent_projects=list(data.get("recent_projects", [])),
            generated_at=generated_at,
            confidence=float(data.get("confidence", 0.0)),
            confidence_reason=data.get("confidence_reason", ""),
            profile_completeness=int(data.get("profile_completeness", 0)),
        )


@dataclass(slots=True)
class ProfileCompletenessResult:
    score: int
    missing: list[str]
    suggested_commands: list[str]


@dataclass(slots=True)
class UserContextExplanation:
    fields: list[tuple[str, str, ProvenanceEntry]]  # category, value, entry
