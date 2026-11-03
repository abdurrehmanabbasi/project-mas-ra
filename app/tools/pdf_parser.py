"""Academic PDF parser extracting structured text, sections, and metadata."""

import io
import logging
import re
from typing import Dict, List, Optional
from pypdf import PdfReader

from app.schemas.papers import Paper, PaperContent

logger = logging.getLogger(__name__)


class PDFParser:
    """Extracts, cleans, and structures text from academic PDF documents."""

    LIGATURES = {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\ufb05": "ft",
        "\ufb06": "st",
    }

    # Standard academic section markers
    SECTION_PATTERNS = [
        (r"(?i)\babstract\b", "Abstract"),
        (r"(?i)\b1\.?\s+introduction\b|\bintroduction\b", "Introduction"),
        (r"(?i)\b(2|3)\.?\s+(related\s+work|background)\b", "Related Work"),
        (r"(?i)\b(2|3|4)\.?\s+(methodology|method|architecture|framework|approach|system\s+design)\b", "Methodology"),
        (r"(?i)\b(3|4|5)\.?\s+(experiments|evaluation|experimental\s+setup|benchmark)\b", "Evaluation"),
        (r"(?i)\b(4|5|6)\.?\s+(results|findings)\b", "Results"),
        (r"(?i)\b(5|6|7)\.?\s+(discussion|limitations|threats\s+to\s+validity)\b", "Limitations"),
        (r"(?i)\b(6|7|8)\.?\s+(conclusion|concluding\s+remarks)\b", "Conclusion"),
        (r"(?i)\breferences\b|\bbibliography\b", "References"),
    ]

    @classmethod
    def clean_text(cls, raw_text: str) -> str:
        """Clean ligature characters, join hyphenated line wraps, and normalize whitespace."""
        if not raw_text:
            return ""

        text = raw_text
        for lig, repl in cls.LIGATURES.items():
            text = text.replace(lig, repl)

        # Reconnect hyphenated words split across lines
        text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)

        # Replace excessive whitespace while keeping paragraph breaks
        lines = [line.strip() for line in text.splitlines()]
        cleaned = "\n".join(lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    @classmethod
    def extract_sections(cls, pages_text: List[str]) -> Dict[str, str]:
        """Identify standard academic sections and split text accordingly."""
        full_document = "\n\n".join(pages_text)
        sections: Dict[str, str] = {}

        # Find match indices of section headings
        found_markers = []
        for regex, name in cls.SECTION_PATTERNS:
            match = re.search(regex, full_document)
            if match:
                found_markers.append((match.start(), name))

        # Sort markers by position in document
        found_markers.sort(key=lambda x: x[0])

        for i, (start_idx, name) in enumerate(found_markers):
            end_idx = found_markers[i + 1][0] if i + 1 < len(found_markers) else len(full_document)
            section_content = full_document[start_idx:end_idx].strip()
            # Omit References section text to reduce token bloat for LLMs
            if name != "References":
                sections[name] = cls.clean_text(section_content)

        return sections

    @classmethod
    def parse_pdf_bytes(cls, paper_id: str, pdf_bytes: bytes) -> PaperContent:
        """Parse raw PDF bytes into a PaperContent record.

        Args:
            paper_id: Canonical paper ID.
            pdf_bytes: Raw binary content of PDF.

        Returns:
            PaperContent with parsed text and 'full_text' scope.
        """
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            pages_text: List[str] = []

            for page in reader.pages:
                text = page.extract_text() or ""
                if text.strip():
                    pages_text.append(text)

            full_text = cls.clean_text("\n\n".join(pages_text))

            if len(full_text) < 50:
                logger.warning(
                    f"PDF for {paper_id} produced negligible text ({len(full_text)} chars). Likely scanned or encrypted."
                )
                return PaperContent(
                    paper_id=paper_id,
                    text="",
                    content_scope="metadata_only",
                    retrieval_status="failed",
                    file_size_bytes=len(pdf_bytes),
                )

            return PaperContent(
                paper_id=paper_id,
                text=full_text,
                content_scope="full_text",
                retrieval_status="success",
                file_size_bytes=len(pdf_bytes),
            )

        except Exception as e:
            logger.warning(f"Error parsing PDF bytes for paper {paper_id}: {e}")
            return PaperContent(
                paper_id=paper_id,
                text="",
                content_scope="metadata_only",
                retrieval_status="failed",
                file_size_bytes=len(pdf_bytes) if pdf_bytes else 0,
            )

    @classmethod
    def parse_paper(cls, paper: Paper, pdf_bytes: Optional[bytes] = None) -> PaperContent:
        """Extract paper content from PDF if provided, otherwise safely fall back to abstract."""
        if pdf_bytes:
            content = cls.parse_pdf_bytes(paper.paper_id, pdf_bytes)
            if content.content_scope == "full_text" and content.retrieval_status == "success":
                return content

        # Graceful fallback to abstract_only if PDF is absent or unparseable
        if paper.abstract and len(paper.abstract.strip()) > 30:
            return PaperContent(
                paper_id=paper.paper_id,
                text=paper.abstract.strip(),
                content_scope="abstract_only",
                retrieval_status="success",
                file_size_bytes=None,
            )

        # Fallback to metadata_only if even abstract is absent
        return PaperContent(
            paper_id=paper.paper_id,
            text=f"Title: {paper.title}. Authors: {', '.join(paper.authors)}.",
            content_scope="metadata_only",
            retrieval_status="partial",
            file_size_bytes=None,
        )
