"""Quick Phase 1 verification: tables, pgvector, alembic stamp."""
from app.config import get_settings
from sqlalchemy import create_engine, text

s = get_settings()
engine = create_engine(s.database_sync_url)

EXPECTED = [
    "agent_actions", "alembic_version", "documents", "escalations",
    "events", "issues", "mentor_allocations", "mentors",
    "notifications", "participants", "resource_allocations",
    "resource_items", "rules", "schedule_events", "submission_requirements",
    "submissions", "teams", "tracks",
]

with engine.connect() as conn:
    rows = conn.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    )).fetchall()
    found = [r[0] for r in rows]

    print(f"\n=== {len(found)} Tables Found ===")
    for t in found:
        status = "✓" if t in EXPECTED else "?"
        print(f"  {status} {t}")

    missing = set(EXPECTED) - set(found)
    if missing:
        print(f"\n✗ MISSING tables: {missing}")
    else:
        print("\n✓ All expected tables present")

    ext = conn.execute(text("SELECT extname FROM pg_extension WHERE extname='vector'")).fetchone()
    print(f"pgvector: {'✓ enabled' if ext else '✗ MISSING'}")

    ver = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
    print(f"Alembic stamp: {ver[0] if ver else 'NOT STAMPED'}\n")
