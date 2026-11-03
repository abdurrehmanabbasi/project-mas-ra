"""Paper retrieval tool downloading open-access academic PDFs."""

import logging
from typing import Optional
import httpx

from app.config import get_settings
from app.schemas.papers import Paper

logger = logging.getLogger(__name__)


class PaperRetriever:
    """Tool that downloads full-text academic PDFs with strict size limits and safety checks."""

    def __init__(self, timeout_seconds: Optional[int] = None, max_size_mb: Optional[int] = None):
        settings = get_settings()
        self.timeout = timeout_seconds or settings.PDF_DOWNLOAD_TIMEOUT_SECONDS
        self.max_bytes = (max_size_mb or settings.MAX_PDF_SIZE_MB) * 1024 * 1024

    def retrieve_pdf_bytes(self, paper: Paper) -> Optional[bytes]:
        """Download raw PDF bytes for a given paper if a direct PDF URL is available.

        Args:
            paper: Paper schema containing sources with potential PDF URLs.

        Returns:
            Raw PDF bytes if successfully downloaded and validated, else None.
        """
        # Find first valid direct PDF URL across providers
        pdf_url = None
        for source in paper.sources:
            if source.pdf_url:
                pdf_url = source.pdf_url
                break

        if not pdf_url:
            return None

        # Normalize arXiv PDF URLs (e.g., http -> https)
        if "arxiv.org/pdf/" in pdf_url and not pdf_url.endswith(".pdf"):
            pdf_url = f"{pdf_url}.pdf"

        headers = {
            "User-Agent": "MAS-Research-Assistant/1.0 (academic; mailto:research@example.org)",
            "Accept": "application/pdf,*/*",
        }

        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                with client.stream("GET", pdf_url, headers=headers) as response:
                    if response.status_code != 200:
                        logger.warning(
                            f"Failed to download PDF for '{paper.title}' from {pdf_url}: status {response.status_code}"
                        )
                        return None

                    # Check Content-Length if reported
                    content_length = response.headers.get("content-length")
                    if content_length and int(content_length) > self.max_bytes:
                        logger.warning(
                            f"PDF for '{paper.title}' exceeds size limit ({content_length} bytes > {self.max_bytes} bytes). Skipping."
                        )
                        return None

                    # Read content in chunks while monitoring size
                    chunks = []
                    total_downloaded = 0
                    for chunk in response.iter_bytes(chunk_size=65536):
                        total_downloaded += len(chunk)
                        if total_downloaded > self.max_bytes:
                            logger.warning(
                                f"PDF download for '{paper.title}' aborted: exceeded {self.max_bytes} bytes."
                            )
                            return None
                        chunks.append(chunk)

                    data = b"".join(chunks)

                    # Validate PDF magic header
                    if not data.startswith(b"%PDF"):
                        logger.warning(
                            f"Downloaded file for '{paper.title}' does not have valid %PDF magic header (likely HTML redirect/block). Skipping."
                        )
                        return None

                    return data

        except Exception as e:
            logger.warning(f"Error retrieving PDF for '{paper.title}' from {pdf_url}: {e}")
            return None

