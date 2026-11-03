"""Academic literature search and retrieval tools."""

from app.tools.arxiv_search import ArxivSearchTool
from app.tools.semantic_scholar import SemanticScholarTool
from app.tools.paper_dedup import PaperDeduplicator

__all__ = ["ArxivSearchTool", "SemanticScholarTool", "PaperDeduplicator"]

