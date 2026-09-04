"""Q&A router — POST /qa.

Roadmap Phase 4:
  - POST /qa: embed incoming question -> similarity search top-k chunks ->
    LLM call with retrieved context -> return answer with citation.

Auth: participants and the organizer-authenticated Discord bot both call
this endpoint. A participant's identity is always derived from their JWT
(never from the request body), so low-confidence issues attach to the
right team.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import require_any_role
from app.models.participant import Participant
from app.schemas.knowledge import QARequest, QAResponse, CitationOut
from app.services.qa import ask

router = APIRouter(tags=["knowledge"])


@router.post("/qa", response_model=QAResponse)
async def question_answer(
    body: QARequest,
    payload: dict = Depends(require_any_role),
    db: AsyncSession = Depends(get_db),
):
    """Ask a question — answered from ingested event documents via RAG.

    If confidence is too low, returns 'no confirmed rule found' and
    auto-creates an Issue for organizer escalation.
    """
    participant_id = None
    team_id = None

    if payload.get("role") == "participant":
        # Identity always comes from the JWT — body ids are ignored.
        result = await db.execute(
            select(Participant).where(Participant.id == payload.get("sub"))
        )
        participant = result.scalar_one_or_none()
        if not participant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Participant not found",
            )
        participant_id = participant.id
        team_id = participant.team_id
    else:
        participant_id = body.participant_id
        team_id = body.team_id

    result = await ask(
        db,
        question=body.question,
        participant_id=participant_id,
        team_id=team_id,
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