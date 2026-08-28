"""Q&A router — POST /qa and GET /tracks.

Roadmap Phase 4:
  - POST /qa: embed incoming question -> similarity search top-k chunks ->
    LLM call with retrieved context -> return answer with citation.
  - Track/problem-statement browser: simple GET /tracks list.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import Track
from app.schemas.knowledge import QARequest, QAResponse, CitationOut, TrackOut
from app.services.qa import ask

router = APIRouter(tags=["knowledge"])


@router.post("/qa", response_model=QAResponse)
async def question_answer(
    body: QARequest,
    db: AsyncSession = Depends(get_db),
):
    """Ask a question — gets answered from ingested event documents via RAG.

    If confidence is too low, returns 'no confirmed rule found' and
    auto-creates an Issue for organizer escalation.
    """
    result = await ask(
        db,
        question=body.question,
        participant_id=body.participant_id,
        team_id=body.team_id,
    )

    return QAResponse(
        answer=result.answer,
        citations=[
            CitationOut(
                source_doc=c.source_doc,
                chunk_text=c.chunk_text,
                similarity_score=c.similarity_score,
            )
            for c in result.citations
        ],
        confident=result.confident,
        issue_id=result.issue_id,
    )


@router.get("/tracks", response_model=list[TrackOut])
async def list_tracks(
    db: AsyncSession = Depends(get_db),
):
    """Simple track/problem-statement browser — byproduct of ingested data."""
    result = await db.execute(select(Track).order_by(Track.name))
    return result.scalars().all()
