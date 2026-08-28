"""Document ingestion pipeline — chunk, sanitize, embed, store in Rule table.

Roadmap requirement:
  - Chunk uploaded docs, embed, store in Rule table with pgvector column.
  - Sanitize ingested doc text — strip anything that looks like a prompt
    injection before embedding.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, Rule
from app.services.embeddings import embed_texts

logger = logging.getLogger(__name__)

# ─── Text extraction ────────────────────────────────────────

SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


def extract_text(filepath: str) -> str:
    """Extract plain text from a file. Supports .txt, .md, and .pdf."""
    p = Path(filepath)
    ext = p.suffix.lower()

    if ext in (".txt", ".md"):
        return p.read_text(encoding="utf-8", errors="replace")

    if ext == ".pdf":
        try:
            import pdfplumber

            pages = []
            with pdfplumber.open(p) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
            return "\n\n".join(pages)
        except ImportError:
            logger.warning("pdfplumber not installed — falling back to raw read for PDF")
            return p.read_text(encoding="utf-8", errors="replace")

    raise ValueError(f"Unsupported file extension: {ext}")


# ─── Chunking ────────────────────────────────────────────────


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks by character count.

    Uses paragraph boundaries when possible, falls back to hard split.
    """
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)

        # Try to break at a paragraph or sentence boundary
        if end < length:
            para_break = text.rfind("\n\n", start, end)
            if para_break > start + chunk_size // 3:
                end = para_break
            else:
                sent_break = text.rfind(". ", start, end)
                if sent_break > start + chunk_size // 3:
                    end = sent_break + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = max(end - overlap, start + 1)
        if start >= length:
            break

    return chunks


# ─── Prompt-injection sanitisation ───────────────────────────

_INJECTION_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?previous\s+instructions",
    r"(?i)you\s+are\s+now\s+(?:a|an|my)",
    r"(?i)system\s*:\s*",
    r"(?i)assistant\s*:\s*",
    r"(?i)human\s*:\s*",
    r"(?i)<\|.*?\|>",
    r"(?i)\[INST\]",
    r"(?i)\[/INST\]",
]

_COMPILED = [re.compile(p) for p in _INJECTION_PATTERNS]


def sanitize_chunk(text: str) -> str:
    """Strip common prompt-injection patterns from a text chunk.

    Roadmap note: 'never let retrieved chunks be treated as instructions'.
    """
    cleaned = text
    for pat in _COMPILED:
        cleaned = pat.sub("", cleaned)
    cleaned = re.sub(r"  +", " ", cleaned).strip()
    return cleaned


# ─── Orchestrator ────────────────────────────────────────────


async def ingest_document(db: AsyncSession, doc_id: uuid.UUID) -> int:
    """Full ingestion pipeline for a single document.

    1. Read file from uploads/
    2. Extract text
    3. Chunk
    4. Sanitize each chunk
    5. Batch-embed
    6. Bulk-insert Rule rows
    7. Update Document.ingested_at

    Returns the number of chunks created.
    """
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise ValueError(f"Document {doc_id} not found")

    uploads_dir = Path(__file__).resolve().parents[2] / "uploads"
    filepath = uploads_dir / doc.filename
    if not filepath.exists():
        raise FileNotFoundError(f"Upload not found: {filepath}")

    raw_text = extract_text(str(filepath))
    chunks = chunk_text(raw_text)
    sanitized = [sanitize_chunk(c) for c in chunks]
    sanitized = [c for c in sanitized if c]  # drop empties

    if not sanitized:
        logger.warning("Document %s produced 0 usable chunks", doc_id)
        return 0

    embeddings = embed_texts(sanitized)

    rules = [
        Rule(
            source_doc_id=doc_id,
            text_chunk=chunk,
            embedding=emb,
            chunk_index=i,
        )
        for i, (chunk, emb) in enumerate(zip(sanitized, embeddings))
    ]
    db.add_all(rules)

    doc.ingested_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info("Ingested document %s: %d chunks", doc.filename, len(rules))
    return len(rules)
