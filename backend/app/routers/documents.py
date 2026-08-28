"""Documents router — upload, ingest, and list event documents.

Roadmap Phase 4:
  - POST /documents/upload (upload rules/FAQ/rubric, store file, trigger ingestion).
  - GET /documents (list all).
  - GET /documents/{doc_id} (single document details).
"""
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_organizer
from app.database import get_db
from app.models.document import Document, Rule
from app.schemas.knowledge import DocumentOut
from app.services.ingestion import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}


# ─── Helpers ─────────────────────────────────────────────────

async def _doc_with_chunk_count(db: AsyncSession, doc: Document) -> dict:
    """Serialize a Document with its chunk_count from the rules table."""
    count_result = await db.execute(
        select(func.count(Rule.id)).where(Rule.source_doc_id == doc.id)
    )
    chunk_count = count_result.scalar() or 0
    return {
        "id": doc.id,
        "filename": doc.filename,
        "type": doc.type,
        "ingested_at": doc.ingested_at,
        "created_at": doc.created_at,
        "chunk_count": chunk_count,
    }


# ─── Endpoints ───────────────────────────────────────────────

@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = "rules",
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document (rules/FAQ/rubric), save to disk, and trigger ingestion.

    Supported formats: .txt, .md, .pdf
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Save file with a unique prefix to avoid collisions
    safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    dest = UPLOADS_DIR / safe_name

    async with aiofiles.open(dest, "wb") as f:
        content = await file.read()
        await f.write(content)

    # Create Document row
    doc = Document(filename=safe_name, type=doc_type)
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Trigger ingestion (chunk -> embed -> store in Rule table)
    try:
        chunk_count = await ingest_document(db, doc.id)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Ingestion failed for %s: %s", safe_name, e)
        chunk_count = 0

    # Refresh to pick up updated ingested_at
    await db.refresh(doc)
    data = await _doc_with_chunk_count(db, doc)
    return DocumentOut(**data)


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """List all uploaded documents with their chunk counts."""
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    docs = result.scalars().all()
    out = []
    for doc in docs:
        data = await _doc_with_chunk_count(db, doc)
        out.append(DocumentOut(**data))
    return out


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: uuid.UUID,
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """Get a single document's details."""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    data = await _doc_with_chunk_count(db, doc)
    return DocumentOut(**data)
