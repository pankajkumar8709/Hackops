"""
Phase 1 — Seed script stub.
Populated with real data in Phase 15.
"""
import asyncio
from app.database import AsyncSessionLocal, engine
from app.database import Base


async def main():
    # Phase 15 will fill this in with 15-20 fake teams,
    # mentors, resources, issues, and a compressed timeline.
    print("Seed stub — no data seeded yet. Will be implemented in Phase 15.")


if __name__ == "__main__":
    asyncio.run(main())
