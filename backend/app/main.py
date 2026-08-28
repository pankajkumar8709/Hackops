from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, participants, teams

settings = get_settings()

app = FastAPI(
    title="Pulse — Hackathon Concierge API",
    version="0.2.0",
    description="Autonomous Hackathon Event Operations Agent",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(participants.router)
app.include_router(teams.router)


@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "service": "pulse-backend", "version": "0.2.0"}

