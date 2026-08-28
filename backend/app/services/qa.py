"""RAG Q&A service — similarity search + Groq LLM answer generation.

Roadmap requirements:
  - POST /qa: embed question -> similarity search top-k -> LLM call with
    retrieved context -> return answer with citation to source chunk.
  - Confidence threshold: if top similarity < threshold, return
    "no confirmed rule found" and auto-create an Issue for escalation.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Optional

from groq import Groq
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.document import Rule
from app.models.issue import Issue
from app.services.embeddings import embed_text

logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────

# Cosine distance threshold: lower = stricter (pgvector <=> returns distance).
# With normalized all-MiniLM-L6-v2 embeddings, similar chunks are ~0.2-0.5
# distance, unrelated chunks are ~0.8-1.2+.
CONFIDENCE_THRESHOLD = 0.55  # distance; similarity = 1 - distance
# With normalized all-MiniLM-L6-v2:
#   - Matching query (e.g. deadline question): ~0.2 distance
#   - Unrelated query (e.g. Jupiter moon): ~0.9+ distance
# Threshold of 0.55 gives good margin on both sides.

TOP_K = 5

SYSTEM_PROMPT = """You are Pulse, an AI assistant for hackathon participants.
Answer the user's question using ONLY the provided context chunks from event
documents (rules, FAQ, rubrics). Be concise and accurate.

Rules:
- If the context does not contain enough information, say so honestly.
- Never invent rules or facts not in the context.
- Cite the source document name when referencing specific rules.
- Keep answers under 200 words unless the question requires detail.
"""


# ─── Data structures ─────────────────────────────────────────

@dataclass
class Citation:
    source_doc: str
    chunk_text: str
    similarity_score: float


@dataclass
class QAResult:
    answer: str
    citations: list[Citation]
    confident: bool
    issue_id: Optional[uuid.UUID] = None


# ─── Similarity search ──────────────────────────────────────

async def search_similar_chunks(
    db: AsyncSession,
    query_embedding: list[float],
    top_k: int = TOP_K,
    threshold: float = CONFIDENCE_THRESHOLD,
) -> list[tuple[Rule, float, str]]:
    """Return top-k Rule chunks ordered by cosine distance.

    Uses pgvector's <=> (cosine distance) operator.
    Returns list of (Rule, distance, doc_filename) tuples.

    CRITICAL: We avoid ORDER BY in SQL because asyncpg returns 0 rows
    when ORDER BY is combined with large inline vector literals (~4KB).
    Instead we fetch with a generous distance filter + LIMIT, then
    sort and trim in Python.  This is fast for <10k chunks.
    """
    embedding_str = "[" + ",".join(f"{x:.8f}" for x in query_embedding) + "]"

    # Fetch rows with distance filter, no ORDER BY (asyncpg bug workaround).
    # Over-fetch to ensure enough after Python sort + trim.
    fetch_limit = top_k * 4
    sql = text(f"""
        SELECT r.id, r.text_chunk, r.chunk_index, r.source_doc_id,
               r.embedding <=> '{embedding_str}'::vector AS distance,
               d.filename AS doc_filename
        FROM rules r
        JOIN documents d ON d.id = r.source_doc_id
        WHERE r.embedding IS NOT NULL
          AND r.embedding <=> '{embedding_str}'::vector < {threshold + 0.5}
        LIMIT {fetch_limit}
    """)

    result = await db.execute(sql)
    rows = result.fetchall()

    matches = []
    for row in rows:
        rule = Rule(
            id=row.id,
            text_chunk=row.text_chunk,
            chunk_index=row.chunk_index,
            source_doc_id=row.source_doc_id,
        )
        matches.append((rule, float(row.distance), row.doc_filename))

    # Sort by distance in Python (ascending = most similar first)
    matches.sort(key=lambda x: x[1])
    return matches[:top_k]


# ─── LLM answer generation ──────────────────────────────────

def _build_context(matches: list[tuple[Rule, float, str]]) -> str:
    """Format retrieved chunks into a context block for the LLM."""
    parts = []
    for i, (rule, dist, doc_name) in enumerate(matches, 1):
        similarity = round(1 - dist, 3)
        parts.append(
            f"[Source {i}: {doc_name} | Similarity: {similarity}]\n{rule.text_chunk}"
        )
    return "\n\n---\n\n".join(parts)


def _call_groq(question: str, context: str) -> str:
    """Call Groq LLM to generate an answer from retrieved context."""
    settings = get_settings()
    client = Groq(api_key=settings.groq_api_key)

    response = client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Context from event documents:\n\n{context}\n\n"
                    f"Question: {question}"
                ),
            },
        ],
        temperature=0.2,
        max_tokens=512,
    )

    raw = response.choices[0].message.content.strip()
    # Strip <think>...</think> tags (qwen3 model quirk)
    raw = re.sub(r"<think>[\s\S]*?</think>", "", raw).strip()
    return raw


# ─── Main Q&A function ──────────────────────────────────────

async def ask(
    db: AsyncSession,
    question: str,
    participant_id: Optional[uuid.UUID] = None,
    team_id: Optional[uuid.UUID] = None,
) -> QAResult:
    """Full RAG pipeline: embed -> search -> (LLM answer | low-confidence Issue).

    Returns QAResult with answer, citations, and confidence flag.
    """
    # 1. Embed the question
    query_embedding = embed_text(question)

    # 2. Similarity search
    matches = await search_similar_chunks(db, query_embedding)

    # 3. Check confidence
    if matches:
        logger.info(
            "Q&A distances: %s",
            [(round(d, 4), n[:40]) for _, d, n in matches],
        )
    if not matches or matches[0][1] > CONFIDENCE_THRESHOLD:
        # Low confidence -> auto-create Issue for human escalation
        logger.info("Low-confidence Q&A -- creating Issue for: %s", question[:100])

        # Validate FK references exist before inserting (avoid FK violations)
        valid_participant_id = None
        valid_team_id = None
        if participant_id is not None:
            from app.models.participant import Participant
            p_result = await db.execute(
                select(Participant.id).where(Participant.id == participant_id)
            )
            if p_result.scalar_one_or_none() is not None:
                valid_participant_id = participant_id
        if team_id is not None:
            from app.models.team import Team
            t_result = await db.execute(
                select(Team.id).where(Team.id == team_id)
            )
            if t_result.scalar_one_or_none() is not None:
                valid_team_id = team_id

        issue = Issue(
            description=f"[Auto] Low-confidence Q&A query: {question}",
            category="qa_low_confidence",
            status="open",
            severity=0.3,
            is_blocking=False,
            participant_id=valid_participant_id,
            team_id=valid_team_id,
        )
        db.add(issue)
        await db.commit()
        await db.refresh(issue)

        return QAResult(
            answer="No confirmed rule found for your question. It has been forwarded to the organizers for a manual answer.",
            citations=[],
            confident=False,
            issue_id=issue.id,
        )

    # 4. Build context from top matches
    context = _build_context(matches)

    # 5. Call LLM for answer
    answer = _call_groq(question, context)

    # 6. Build citations
    citations = [
        Citation(
            source_doc=doc_name,
            chunk_text=rule.text_chunk[:200],
            similarity_score=round(1 - dist, 3),
        )
        for rule, dist, doc_name in matches
        if dist <= CONFIDENCE_THRESHOLD
    ]

    return QAResult(
        answer=answer,
        citations=citations,
        confident=True,
    )
