from unittest.mock import MagicMock, patch

from smith.services.tool_runner import run_analyze, run_duplicates, run_organize


def test_run_duplicates_success(tmp_path):
    (tmp_path / "a.txt").write_text("same")
    (tmp_path / "b.txt").write_text("same")

    result = run_duplicates(tmp_path)

    assert result.success
    assert result.execution_time_ms >= 0
    assert result.metadata is not None
    assert "execution_time_ms" in result.metadata
    assert result.metadata["duplicate_groups"] == 1


def test_run_duplicates_exception(tmp_path):
    with patch("smith.services.tool_runner.FindDuplicateFilesTool") as mock_cls:
        mock_tool = MagicMock()
        mock_tool.name = "duplicates"
        mock_tool.execute.side_effect = RuntimeError("disk error")
        mock_cls.return_value = mock_tool

        result = run_duplicates(tmp_path)

    assert not result.success
    assert "disk error" in result.message


def test_run_analyze_structure_only(tmp_path):
    (tmp_path / "Main.kt").write_text("fun main() {}")

    result = run_analyze(tmp_path, None, structure_only=True)

    assert result.success
    assert "Project Structure" in result.message
    assert result.metadata["structure_only"] is True


def test_run_analyze_writes_output(tmp_path, fake_llm):
    (tmp_path / "Main.kt").write_text("fun main() {}")
    fake_llm._response = "# Project Analysis"
    out = tmp_path / "report.md"

    result = run_analyze(tmp_path, fake_llm, output=out, structure_only=True)

    assert result.success
    assert result.output_path == out
    assert out.read_text() == result.message


def test_run_organize_dry_run(tmp_path):
    (tmp_path / "file.md").write_text("# doc")

    result = run_organize(tmp_path, dry_run=True)

    assert result.success
    assert result.metadata["dry_run"] is True
    assert "dry-run" in result.message
