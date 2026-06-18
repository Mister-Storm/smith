from unittest.mock import MagicMock, patch

from smith.tools.analyze_project import AnalyzeProjectTool
from smith.tools.summarize_pdf import SummarizePdfTool


def test_analyze_project_tool(tmp_path, fake_llm):
    (tmp_path / "Main.kt").write_text("fun main() {}")
    fake_llm._response = "# Project Analysis\n\n## Stack & Framework\nKotlin"

    tool = AnalyzeProjectTool(fake_llm)
    result = tool.execute(path=str(tmp_path))

    assert result.success
    assert "Project Analysis" in result.message
    assert result.metadata["language"] == "kotlin"
    assert len(fake_llm.calls) == 1


def test_analyze_structure_only(tmp_path):
    (tmp_path / "Main.kt").write_text("fun main() {}")

    tool = AnalyzeProjectTool(None)
    result = tool.execute(path=str(tmp_path), structure_only=True)

    assert result.success
    assert "# Project Context" in result.message
    assert "## Project Health" in result.message
    assert result.metadata["structure_only"] is True


def test_analyze_json(tmp_path):
    (tmp_path / "build.gradle.kts").write_text('plugins { kotlin("jvm") }')
    (tmp_path / "Main.kt").write_text("fun main() {}")

    tool = AnalyzeProjectTool(None)
    result = tool.execute(path=str(tmp_path), as_json=True)

    assert result.success
    assert "health_score" in result.message
    assert result.metadata["health_score"] >= 0


def test_analyze_invalid_path(tmp_path, fake_llm):
    tool = AnalyzeProjectTool(fake_llm)
    result = tool.execute(path=str(tmp_path / "nope"))
    assert not result.success


def test_analyze_no_llm(tmp_path):
    (tmp_path / "Main.kt").write_text("fun main() {}")
    tool = AnalyzeProjectTool(None)
    result = tool.execute(path=str(tmp_path))
    assert not result.success
    assert "LLM provider required" in result.message


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
    assert "Summary content here" in result.message
    assert result.metadata["pages"] == 1
    assert "Pages:" in result.message


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
    assert "No extractable text" in result.message


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
    assert "truncated" in result.message.lower()
    assert result.metadata["truncated"] is True


def test_summarize_pages_limit(tmp_path, fake_llm):
    pdf_path = tmp_path / "multi.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    fake_llm._response = "Partial summary."

    with patch("smith.tools.summarize_pdf.PdfReader") as mock_reader:
        pages = []
        for i in range(5):
            page = MagicMock()
            page.extract_text.return_value = f"Page {i} content."
            pages.append(page)
        instance = MagicMock()
        instance.pages = pages
        mock_reader.return_value = instance

        tool = SummarizePdfTool(fake_llm)
        result = tool.execute(path=str(pdf_path), pages=2)

    assert result.success
    assert result.metadata["pages_processed"] == 2
    assert "2 processed" in result.message
