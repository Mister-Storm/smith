import logging
import sys
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from smith.core.config import (
    MIN_PYTHON_VERSION,
    Config,
    describe_provider_selection,
    get_smith_home,
    is_key_set,
    resolve_provider,
)
from smith.core.exceptions import ConfigurationError
from smith.llm.factory import get_llm_provider
from smith.memory.service import MemoryService

logger = logging.getLogger(__name__)


class CheckStatus(StrEnum):
    OK = "ok"
    WARN = "warn"
    CRITICAL = "critical"


@dataclass
class CheckResult:
    status: CheckStatus
    lines: list[str] = field(default_factory=list)


@dataclass
class DoctorReport:
    sections: list[tuple[str, CheckResult]] = field(default_factory=list)
    connectivity: CheckResult | None = None

    @property
    def exit_code(self) -> int:
        all_checks = [r for _, r in self.sections]
        if self.connectivity:
            all_checks.append(self.connectivity)
        if any(r.status == CheckStatus.CRITICAL for r in all_checks):
            return 2
        if any(r.status == CheckStatus.WARN for r in all_checks):
            return 1
        return 0

    @property
    def overall_message(self) -> str:
        code = self.exit_code
        if code == 0:
            return "✓ Smith is healthy"
        if code == 1:
            return "⚠ Smith has warnings"
        return "✗ Smith has critical issues"


def _display_path(path: Path) -> str:
    home = Path.home()
    try:
        rel = path.relative_to(home)
        return f"~/{rel}"
    except ValueError:
        return str(path)


def _section_header(title: str) -> str:
    return f"{title}\n{'-' * len(title)}"


def _check_python() -> CheckResult:
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    if (version.major, version.minor) < MIN_PYTHON_VERSION:
        return CheckResult(
            status=CheckStatus.CRITICAL,
            lines=[f"Version: {version_str}", "Status: CRITICAL (below minimum 3.12)"],
        )
    return CheckResult(
        status=CheckStatus.OK,
        lines=[f"Version: {version_str}", "Status: OK"],
    )


def _check_configuration(config: Config) -> CheckResult:
    path = config.config_file_path
    lines = [f"Config File: {_display_path(path)}"]
    if config.config_file_loaded:
        lines.append("Status: OK")
        return CheckResult(status=CheckStatus.OK, lines=lines)
    lines.append("Status: WARN (file not found, using environment variables)")
    return CheckResult(status=CheckStatus.WARN, lines=lines)


def _check_providers(config: Config) -> tuple[CheckResult, CheckResult]:
    openai_configured = is_key_set("OPENAI_API_KEY") or config.openai_api_key
    openai_status = "Configured" if openai_configured else "Not Configured"
    deepseek_configured = is_key_set("DEEPSEEK_API_KEY") or config.deepseek_api_key
    deepseek_status = "Configured" if deepseek_configured else "Not Configured"

    provider_lines = [
        f"OpenAI API Key: {openai_status}",
        f"DeepSeek API Key: {deepseek_status}",
    ]

    provider_name, reason = describe_provider_selection(config)
    resolution_lines = [
        f"Active Provider: {provider_name}",
        f"Reason: {reason}",
    ]

    provider_check_status = CheckStatus.OK
    if openai_status == "Not Configured" or deepseek_status == "Not Configured":
        provider_check_status = CheckStatus.WARN

    try:
        resolve_provider(config)
        resolution_status = CheckStatus.OK
    except ConfigurationError:
        resolution_status = CheckStatus.CRITICAL

    return (
        CheckResult(status=provider_check_status, lines=provider_lines),
        CheckResult(status=resolution_status, lines=resolution_lines),
    )


def _check_memory(config: Config) -> CheckResult:
    db_path = config.db_path
    lines = [f"Database: {_display_path(db_path)}"]

    db_exists = db_path.is_file()
    if not db_exists:
        lines.append("Status: WARN (database will be created on first use)")

    try:
        memory = MemoryService(db_path)
        count = memory.count_conversations()
        memory.close()
        lines.append("Connection: OK")
        lines.append(f"Conversations: {count}")
        status = CheckStatus.OK if db_exists else CheckStatus.WARN
        return CheckResult(status=status, lines=lines)
    except Exception as exc:
        lines.append(f"Connection: FAILED ({exc})")
        return CheckResult(status=CheckStatus.CRITICAL, lines=lines)


def _check_filesystem(config: Config) -> CheckResult:
    smith_dir = get_smith_home()
    lines: list[str] = []

    try:
        smith_dir.mkdir(parents=True, exist_ok=True)
        test_file = smith_dir / f".doctor_{uuid.uuid4().hex[:8]}"
        test_file.write_text("ok")
        test_file.unlink()
        lines.append("Read Access: OK")
        lines.append("Write Access: OK")
        read_ok = True
        write_ok = True
    except OSError as exc:
        lines.append(f"Read Access: FAILED ({exc})")
        lines.append(f"Write Access: FAILED ({exc})")
        read_ok = False
        write_ok = False

    db_parent = config.db_path.parent
    try:
        db_parent.mkdir(parents=True, exist_ok=True)
        if not db_parent.exists():
            raise OSError("parent directory inaccessible")
    except OSError as exc:
        lines.append(f"Database Directory: FAILED ({exc})")
        return CheckResult(status=CheckStatus.CRITICAL, lines=lines)

    if read_ok and write_ok:
        return CheckResult(status=CheckStatus.OK, lines=lines)
    return CheckResult(status=CheckStatus.CRITICAL, lines=lines)


def _check_connectivity(config: Config) -> CheckResult:
    try:
        provider = get_llm_provider(config)
    except ConfigurationError as exc:
        return CheckResult(
            status=CheckStatus.WARN,
            lines=["Provider: None", f"Status: SKIPPED ({exc})"],
        )

    start = time.perf_counter()
    try:
        provider.generate("Reply with: ok", system="Reply with exactly: ok")
        elapsed = time.perf_counter() - start
        return CheckResult(
            status=CheckStatus.OK,
            lines=[
                f"Provider: {provider.name}",
                "Status: OK",
                f"Latency: {elapsed:.1f}s",
            ],
        )
    except Exception as exc:
        elapsed = time.perf_counter() - start
        return CheckResult(
            status=CheckStatus.WARN,
            lines=[
                f"Provider: {provider.name}",
                f"Status: FAILED ({exc})",
                f"Latency: {elapsed:.1f}s",
            ],
        )


def run_doctor(*, test_provider: bool = False, config: Config | None = None) -> DoctorReport:
    config = config or Config.load()
    logger.info("Running doctor diagnostics")

    sections: list[tuple[str, CheckResult]] = []

    sections.append(("Python", _check_python()))
    sections.append(("Configuration", _check_configuration(config)))

    providers_check, resolution_check = _check_providers(config)
    sections.append(("Providers", providers_check))
    sections.append(("Provider Resolution", resolution_check))
    sections.append(("Memory", _check_memory(config)))
    sections.append(("Filesystem", _check_filesystem(config)))

    connectivity = _check_connectivity(config) if test_provider else None

    return DoctorReport(sections=sections, connectivity=connectivity)


def format_doctor_report(report: DoctorReport) -> str:
    lines = ["Smith Doctor Report", "===================", ""]

    for title, check in report.sections:
        lines.append(_section_header(title))
        lines.extend(check.lines)
        lines.append("")

    if report.connectivity:
        lines.append(_section_header("Provider Connectivity"))
        lines.extend(report.connectivity.lines)
        lines.append("")

    lines.append(_section_header("Overall Status"))
    lines.append(report.overall_message)

    return "\n".join(lines)
