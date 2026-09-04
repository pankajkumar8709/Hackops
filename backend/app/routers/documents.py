"""Documents router — file upload with live ingestion pipeline.

Uploads are chunked, sanitized, embedded, and written to the `rules`
table (pgvector) synchronously so `POST /qa` can answer from them
immediately. Each document exposes an ingestion status for the UI:
"processing" | "ready" | "failed".
"""
import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.auth import require_organizer
from app.models.document import Document
from app.schemas.documents import DocumentOut
from app.services.ingestion import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])

# Where uploaded files are stored on disk
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}


def _sanitize_filename(filename: str) -> str:
    """Return a safe basename — blocks path traversal (../, absolute paths)."""
    name = Path(filename or "").name
    if not name or name in (".", ".."):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )
    if any(sep in filename.lower() for sep in ("/", "\\", "%2f", "%5c", "..")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename must not contain path separators or traversal sequences",
        )
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext or 'none'}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )
    return name


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form("rules"),
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    """Upload a rules/FAQ/rubric document and ingest it into the RAG pipeline.

    The file is chunked, sanitized, embedded, and stored in the `rules`
    pgvector table before the endpoint returns.
    """
    safe_name = _sanitize_filename(file.filename or "")

    # Save file to disk
    dest = UPLOAD_DIR / safe_name
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    doc = Document(filename=safe_name, type=doc_type, ingestion_status="processing")
    db.add(doc)
    await db.flush()

    # Run the ingestion pipeline synchronously so /qa can answer right away.
    try:
        chunk_count = await ingest_document(db, doc.id)
        if chunk_count == 0:
            doc.ingestion_status = "failed"
            doc.error = doc.error or "No usable text extracted from the document"
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Document was stored but produced no searchable chunks",
            )
    except HTTPException:
        raise
    except Exception as e:
        doc.ingestion_status = "failed"
        doc.error = str(e)[:500]
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {e}",
        )

    await db.refresh(doc)
    return doc


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).order_by(Document.created_at))
    return result.scalars().all()


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: uuid.UUID,
    _org=Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    # Remove file from disk if it exists
    file_path = UPLOAD_DIR / doc.filename
    if file_path.exists():
        file_path.unlink()
    await db.delete(doc)
    await db.commit()