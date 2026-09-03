from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, participants, teams, events, documents, mentors, resources, qa, submissions, issues, allocations, resource_requests, reminders, orchestrator, notifications, dashboard

settings = get_settings()

app = FastAPI(
    title="Pulse — Hackathon Concierge API",
    version="1.2.0",
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
app.include_router(events.router)
app.include_router(documents.router)
app.include_router(mentors.router)
app.include_router(resources.router)
app.include_router(qa.router)
app.include_router(submissions.router)
app.include_router(issues.router)
app.include_router(allocations.router)
app.include_router(resource_requests.router)
app.include_router(reminders.router)
app.include_router(orchestrator.router)
app.include_router(notifications.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "service": "pulse-backend", "version": "1.2.0"}
