import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class ProjectContext:
    project_name: str
    language: str | None
    framework: str | None
    build_system: str | None
    database: list[str]
    infrastructure: list[str]
    ci_cd: list[str]
    modules: list[str]
    generated_at: datetime

    def to_dict(self) -> dict:
        data = asdict(self)
        data["generated_at"] = self.generated_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectContext":
        generated = data.get("generated_at", "")
        if isinstance(generated, str):
            generated_at = datetime.fromisoformat(generated.replace("Z", "+00:00"))
        else:
            generated_at = datetime.now(UTC)
        return cls(
            project_name=data.get("project_name", ""),
            language=data.get("language"),
            framework=data.get("framework"),
            build_system=data.get("build_system"),
            database=list(data.get("database", [])),
            infrastructure=list(data.get("infrastructure", [])),
            ci_cd=list(data.get("ci_cd", [])),
            modules=list(data.get("modules", [])),
            generated_at=generated_at,
        )

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, text: str) -> "ProjectContext":
        return cls.from_dict(json.loads(text))

    def to_prompt_block(self, *, max_chars: int = 500) -> str:
        language = self.language or "Unknown"
        framework = self.framework or "Unknown"
        database = ", ".join(self.database) or "None"
        build = self.build_system or "Unknown"
        modules = ", ".join(self.modules) or "None"
        block = (
            "Current Project Context\n\n"
            f"Language: {language}\n"
            f"Framework: {framework}\n"
            f"Database: {database}\n"
            f"Build: {build}\n"
            f"Modules: {modules}"
        )
        return block[:max_chars]
