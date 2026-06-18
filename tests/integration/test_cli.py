from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from smith.cli.app import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "smith" in result.output.lower()


def test_duplicates_command(tmp_path):
    (tmp_path / "a.txt").write_text("same")
    (tmp_path / "b.txt").write_text("same")

    result = runner.invoke(app, ["duplicates", str(tmp_path)])
    assert result.exit_code == 0
    assert "Group 1" in result.output
    assert "Execution time:" in result.output


def test_organize_dry_run(tmp_path):
    (tmp_path / "file.md").write_text("# doc")

    result = runner.invoke(app, ["organize", str(tmp_path), "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.output


def test_analyze_command(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    (tmp_path / "Main.kt").write_text("fun main(){}")

    with patch("smith.cli.commands.analyze.get_llm_provider") as mock_get:
        fake = MagicMock()
        fake.generate.return_value = "# Project Analysis\n\n## Stack"
        mock_get.return_value = fake

        result = runner.invoke(app, ["analyze", str(tmp_path)])

    assert result.exit_code == 0
    assert "Project Analysis" in result.output
    assert "✓ Analysis completed" in result.output
    assert "Execution time:" in result.output


def test_analyze_structure_only(tmp_path):
    (tmp_path / "Main.kt").write_text("fun main(){}")

    result = runner.invoke(app, ["analyze", str(tmp_path), "--structure-only"])
    assert result.exit_code == 0
    assert "Project Context" in result.output


def test_analyze_output_file(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    (tmp_path / "Main.java").write_text("class Main {}")
    out_file = tmp_path / "report.md"

    with patch("smith.cli.commands.analyze.get_llm_provider") as mock_get:
        fake = MagicMock()
        fake.generate.return_value = "# Project Analysis"
        mock_get.return_value = fake

        result = runner.invoke(app, ["analyze", str(tmp_path), "--output", str(out_file)])

    assert result.exit_code == 0
    content = out_file.read_text()
    assert "# Project Analysis" in content
    assert "Java" in content


def test_context_command(tmp_path, monkeypatch):
    monkeypatch.setenv("SMITH_DB_PATH", str(tmp_path / "ctx.db"))
    (tmp_path / "build.gradle.kts").write_text('plugins { kotlin("jvm") }')
    (tmp_path / "Main.kt").write_text("fun main() {}")

    result = runner.invoke(app, ["context", str(tmp_path)])
    assert result.exit_code == 0
    assert "Project Context" in result.output
    assert "✓ Context completed" in result.output


def test_analyze_json(tmp_path):
    (tmp_path / "build.gradle.kts").write_text('plugins { kotlin("jvm") }')
    (tmp_path / "Main.kt").write_text("fun main() {}")

    result = runner.invoke(app, ["analyze", str(tmp_path), "--json"])
    assert result.exit_code == 0
    assert "health_score" in result.output


def test_summarize_command(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF")

    with patch("smith.cli.commands.summarize.get_llm_provider") as mock_get:
        fake = MagicMock()
        fake.generate.return_value = "Summary of the document."
        mock_get.return_value = fake

        with patch("smith.tools.summarize_pdf.PdfReader") as mock_reader:
            page = MagicMock()
            page.extract_text.return_value = "Content"
            instance = MagicMock()
            instance.pages = [page]
            mock_reader.return_value = instance

            result = runner.invoke(app, ["summarize", str(pdf)])

    assert result.exit_code == 0
    assert "✓ Summarization completed" in result.output


def test_doctor_command(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SMITH_DB_PATH", str(tmp_path / "mem.db"))
    monkeypatch.setenv("SMITH_CONFIG_PATH", str(tmp_path / "missing.toml"))
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / "smith_home"))

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code in (0, 1)
    assert "Smith Doctor Report" in result.output


def test_doctor_no_keys(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("SMITH_DB_PATH", str(tmp_path / "mem.db"))

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 2


def test_organize_with_confirm(tmp_path):
    (tmp_path / "file.md").write_text("# doc")

    result = runner.invoke(app, ["organize", str(tmp_path)], input="y\n")
    assert result.exit_code == 0
    assert (tmp_path / "Documents" / "file.md").exists()


def test_organize_cancelled(tmp_path):
    (tmp_path / "file.md").write_text("# doc")

    result = runner.invoke(app, ["organize", str(tmp_path)], input="n\n")
    assert result.exit_code == 0
    assert "cancelled" in result.output.lower()
    assert (tmp_path / "file.md").exists()


def test_summarize_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    pdf = tmp_path / "missing.pdf"

    result = runner.invoke(app, ["summarize", str(pdf)])
    assert result.exit_code == 1


def test_analyze_missing_config(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    (tmp_path / "Main.kt").write_text("fun main(){}")

    result = runner.invoke(app, ["analyze", str(tmp_path)])
    assert result.exit_code == 1
    assert "smith setup" in result.output


def test_help_command():
    result = runner.invoke(app, ["help"])
    assert result.exit_code == 0
    assert "Smith" in result.output
    assert "smith setup" in result.output


def test_version_command_integration(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Provider:" in result.output


def test_chat_missing_config(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("SMITH_HOME", str(tmp_path / "smith"))
    monkeypatch.setenv("SMITH_CONFIG_PATH", str(tmp_path / "smith/config.toml"))
    monkeypatch.setenv("SMITH_DB_PATH", str(tmp_path / "smith/memory.db"))

    def fake_setup(config):
        from smith.core.config import Config

        return Config.load(load_env=False)

    with patch("smith.cli.commands.chat.ensure_provider_configured", fake_setup):
        with patch("smith.cli.commands.chat.get_llm_provider") as mock_llm:
            fake = MagicMock()
            fake.name = "Fake"
            mock_llm.return_value = fake
            with patch("smith.services.chat.ChatService.run"):
                result = runner.invoke(app, ["chat"])

    assert result.exit_code == 0
