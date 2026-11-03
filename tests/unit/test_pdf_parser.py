"""Unit tests for PDF parsing, text cleaning, section extraction, and fallbacks."""

import io
from reportlab.pdfgen import canvas
from app.schemas.papers import Paper
from app.tools.pdf_parser import PDFParser


def create_in_memory_pdf(text: str) -> bytes:
    """Helper creating a valid PDF binary stream in memory using reportlab."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    # Write text across lines
    y = 750
    for line in text.splitlines():
        c.drawString(100, y, line)
        y -= 20
    c.save()
    return buf.getvalue()


def test_clean_text_ligatures_and_hyphens():
    """Verify clean_text unifies ligatures and merges hyphenated wraps."""
    raw = "The ar\ufb01cial in\ufb02uence of multi- \nagent sys-\ntems was measured."
    cleaned = PDFParser.clean_text(raw)
    assert "artificial" in cleaned or "arfi" in cleaned
    assert "influence" in cleaned or "influ" in cleaned
    assert "multi-agent" in cleaned or "multiagent" in cleaned
    assert "systems" in cleaned


def test_extract_sections():
    """Verify identification of standard academic sections."""
    doc_pages = [
        "Abstract\nThis paper evaluates autonomous software engineering agents.",
        "1. Introduction\nLarge language models act as cooperative agents.\n\n3. Methodology\nWe use a communicative graph.",
        "4. Evaluation\nTested on SWE-bench benchmarks.",
    ]
    sections = PDFParser.extract_sections(doc_pages)
    assert "Abstract" in sections
    assert "Introduction" in sections
    assert "Methodology" in sections
    assert "Evaluation" in sections
    assert "autonomous software engineering" in sections["Abstract"]


def test_parse_valid_pdf_bytes():
    """Verify parsing a valid PDF bytes payload into full_text PaperContent."""
    pdf_text = "Abstract\nAutonomous agents improve software quality.\n1. Introduction\nBackground details here."
    pdf_bytes = create_in_memory_pdf(pdf_text)

    paper = Paper(
        title="Valid Test Paper",
        abstract="Short abstract",
        authors=["Alice Test"],
    )

    content = PDFParser.parse_paper(paper, pdf_bytes=pdf_bytes)
    assert content.content_scope == "full_text"
    assert content.retrieval_status == "success"
    assert "Autonomous agents improve" in content.text
    assert content.file_size_bytes == len(pdf_bytes)


def test_fallback_to_abstract_when_pdf_empty_or_corrupt():
    """Verify graceful fallback to abstract_only when PDF is corrupted."""
    corrupt_bytes = b"Not a real PDF file content"
    paper = Paper(
        title="Corrupted Paper",
        abstract="A robust abstract describing multi-agent benchmark evaluation in detail.",
        authors=["Bob Test"],
    )

    content = PDFParser.parse_paper(paper, pdf_bytes=corrupt_bytes)
    assert content.content_scope == "abstract_only"
    assert content.retrieval_status == "success"
    assert "robust abstract" in content.text


def test_fallback_to_metadata_when_abstract_missing():
    """Verify fallback to metadata_only when neither PDF nor abstract is accessible."""
    paper = Paper(
        title="Metadata Only Paper",
        abstract=None,
        authors=["Charlie Test"],
    )

    content = PDFParser.parse_paper(paper, pdf_bytes=None)
    assert content.content_scope == "metadata_only"
    assert content.retrieval_status == "partial"
    assert "Charlie Test" in content.text
