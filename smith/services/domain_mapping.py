"""Deterministic working-domain keyword mapping."""

from __future__ import annotations

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "AI Assistants": ["smith", "ai", "assistant", "llm", "agent", "chat"],
    "Drones": ["drone", "uav", "flight", "quadcopter"],
    "Backend Systems": ["api", "server", "backend", "service", "microservice"],
    "DevOps": ["docker", "k8s", "kubernetes", "terraform", "ci", "deploy", "devops"],
    "Developer Tools": ["cli", "tool", "devtools", "developer"],
    "Embedded Systems": ["embedded", "firmware", "hardware", "iot"],
    "Research": ["research", "lab", "experiment", "study"],
    "Education": ["course", "tutorial", "learn", "education", "teaching"],
}


def tokenize(text: str) -> list[str]:
    normalized = text.lower().replace("_", "-").replace(" ", "-")
    return [part for part in normalized.split("-") if part]


def score_domains(texts: list[str]) -> dict[str, int]:
    scores: dict[str, int] = {}
    combined = " ".join(texts).lower()
    tokens = set()
    for text in texts:
        tokens.update(tokenize(text))
    for domain, keywords in DOMAIN_KEYWORDS.items():
        count = 0
        for keyword in keywords:
            if keyword in combined or keyword in tokens:
                count += 1
        if count:
            scores[domain] = count
    return scores


def top_domains(texts: list[str], *, limit: int = 5) -> list[str]:
    ranked = sorted(score_domains(texts).items(), key=lambda x: (-x[1], x[0]))
    return [name for name, _ in ranked[:limit]]
