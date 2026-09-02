"""Clean up Phase 6 test data to speed up testing."""
import asyncio, asyncpg
from pathlib import Path

async def clean():
    env_path = Path(__file__).resolve().parent.parent / ".env"
    db_url = None
    with open(env_path) as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                db_url = line.strip().split("=", 1)[1]
                break
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if "?" in sync_url:
        sync_url = sync_url.split("?")[0]

    conn = await asyncpg.connect(sync_url)
    try:
        await conn.execute("DELETE FROM escalations")
        print("Deleted all escalations")
        await conn.execute("DELETE FROM issues")
        print("Deleted all issues")

        for t in ["escalations", "issues"]:
            c = await conn.fetchval(f"SELECT count(*) FROM {t}")
            print(f"  {t}: {c} remaining")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(clean())
