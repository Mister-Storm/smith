import logging
from pathlib import Path

from pypdf import PdfReader

from smith.llm.base import LLMProvider
from smith.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)

MAX_CHARS = 12_000


class SummarizePdfTool(Tool):
    name = "summarize"
    description = "Summarize a PDF document"

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def execute(self, **kwargs) -> ToolResult:
        pdf_path = Path(kwargs["path"]).expanduser().resolve()
        study_notes = bool(kwargs.get("study_notes", False))

        if not pdf_path.is_file():
            return ToolResult(success=False, output=f"File not found: {pdf_path}")

        try:
            reader = PdfReader(str(pdf_path))
            pages_text = []
            for page in reader.pages:
                text = page.extract_text() or ""
                pages_text.append(text)
            full_text = "\n".join(pages_text).strip()
        except Exception as exc:
            return ToolResult(success=False, output=f"Failed to read PDF: {exc}")

        if not full_text:
            return ToolResult(
                success=False,
                output="No extractable text found in PDF (may be image-only).",
            )

        truncated = len(full_text) > MAX_CHARS
        text_for_llm = full_text[:MAX_CHARS]
        truncation_note = "\n\n(Note: document was truncated for analysis.)" if truncated else ""

        sections = "summary, key insights"
        if study_notes:
            sections += ", and study notes"

        prompt = f"""Summarize the following document. Provide {sections}.

Document:
{text_for_llm}"""

        system = "You are a helpful document analyst. Be clear and structured."
        summary = self._llm.generate(prompt, system=system)

        output = f"# Summary: {pdf_path.name}\n\n{summary}{truncation_note}"
        logger.info(
            "Tool summarize path=%s chars=%d truncated=%s",
            pdf_path,
            len(full_text),
            truncated,
        )
        return ToolResult(success=True, output=output)
