from unittest.mock import MagicMock, patch

from smith.tools.analyze_project import AnalyzeProjectTool, _scan_project
from smith.tools.summarize_pdf import SummarizePdfTool


def test_scan_kotlin_project(tmp_path):
    (tmp_path / "build.gradle.kts").write_text('plugins { kotlin("jvm") }')
    src = tmp_path / "src"
    src.mkdir()
    (src / "Main.kt").write_text("fun main() {}")

    metadata = _scan_project(tmp_path)
    assert "Kotlin" in metadata["languages"]
    assert metadata["build_system"] == "Gradle (Kotlin DSL)"


def test_scan_spring_boot_project(tmp_path):
    (tmp_path / "pom.xml").write_text(
        "<project><dependency>spring-boot-starter</dependency></project>"
    )
    (tmp_path / "application.yml").write_text("spring:\n  application:\n    name: demo")
    (tmp_path / "App.java").write_text("@SpringBootApplication\npublic class App {}")

    metadata = _scan_project(tmp_path)
    assert "Java" in metadata["languages"]
    assert "Spring Boot" in metadata["languages"]
    assert metadata["build_system"] == "Maven"


def test_analyze_project_tool(tmp_path, fake_llm):
    (tmp_path / "Main.kt").write_text("fun main() {}")
    fake_llm._response = "# Project Analysis\n\n## Stack & Framework\nKotlin"

    tool = AnalyzeProjectTool(fake_llm)
    result = tool.execute(path=str(tmp_path))

    assert result.success
    assert "Project Analysis" in result.output
    assert "Kotlin" in result.output
    assert len(fake_llm.calls) == 1


def test_analyze_invalid_path(tmp_path, fake_llm):
    tool = AnalyzeProjectTool(fake_llm)
    result = tool.execute(path=str(tmp_path / "nope"))
    assert not result.success


def test_summarize_pdf(tmp_path, fake_llm):
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    fake_llm._response = "Summary content here."

    with patch("smith.tools.summarize_pdf.PdfReader") as mock_reader:
        page = MagicMock()
        page.extract_text.return_value = "Document text content."
        instance = MagicMock()
        instance.pages = [page]
        mock_reader.return_value = instance

        tool = SummarizePdfTool(fake_llm)
        result = tool.execute(path=str(pdf_path), study_notes=True)

    assert result.success
    assert "Summary content here" in result.output
    assert len(fake_llm.calls) == 1


def test_summarize_empty_pdf(tmp_path, fake_llm):
    pdf_path = tmp_path / "empty.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    with patch("smith.tools.summarize_pdf.PdfReader") as mock_reader:
        page = MagicMock()
        page.extract_text.return_value = ""
        instance = MagicMock()
        instance.pages = [page]
        mock_reader.return_value = instance

        tool = SummarizePdfTool(fake_llm)
        result = tool.execute(path=str(pdf_path))

    assert not result.success
    assert "No extractable text" in result.output


def test_summarize_truncation(tmp_path, fake_llm):
    pdf_path = tmp_path / "long.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    fake_llm._response = "Short summary."

    with patch("smith.tools.summarize_pdf.PdfReader") as mock_reader:
        page = MagicMock()
        page.extract_text.return_value = "x" * 15000
        instance = MagicMock()
        instance.pages = [page]
        mock_reader.return_value = instance

        tool = SummarizePdfTool(fake_llm)
        result = tool.execute(path=str(pdf_path))

    assert result.success
    assert "truncated" in result.output.lower()
