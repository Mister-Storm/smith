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
        pages_limit = kwargs.get("pages")

        if not pdf_path.is_file():
            return ToolResult(success=False, message=f"File not found: {pdf_path}")

        try:
            reader = PdfReader(str(pdf_path))
            total_pages = len(reader.pages)
            pages_to_read = reader.pages
            if pages_limit is not None:
                pages_to_read = reader.pages[: int(pages_limit)]

            pages_text = []
            for page in pages_to_read:
                text = page.extract_text() or ""
                pages_text.append(text)
            full_text = "\n".join(pages_text).strip()
        except Exception as exc:
            return ToolResult(success=False, message=f"Failed to read PDF: {exc}")

        if not full_text:
            return ToolResult(
                success=False,
                message="No extractable text found in PDF (may be image-only).",
            )

        truncated = len(full_text) > MAX_CHARS
        text_for_llm = full_text[:MAX_CHARS]
        truncation_note = "\n\n(Note: document was truncated for analysis.)" if truncated else ""

        sections = "## Summary\n\n## Key Insights"
        if study_notes:
            sections += "\n\n## Study Notes"

        prompt = f"""Summarize the following document. Use these exact markdown sections:

{sections}

Document:
{text_for_llm}"""

        system = "You are a helpful document analyst. Be clear and structured."
        summary = self._llm.generate(prompt, system=system)

        header = (
            f"# Summary: {pdf_path.name}\n\n"
            f"**Pages:** {total_pages} total"
            + (f", {len(pages_to_read)} processed" if pages_limit else "")
            + f" | **Characters extracted:** {len(full_text)}\n\n"
        )
        message = header + summary + truncation_note

        metadata = {
            "pages": total_pages,
            "pages_processed": len(pages_to_read),
            "chars_extracted": len(full_text),
            "truncated": truncated,
        }
        logger.info(
            "Tool summarize path=%s chars=%d truncated=%s",
            pdf_path,
            len(full_text),
            truncated,
        )
        return ToolResult(success=True, message=message, metadata=metadata)
