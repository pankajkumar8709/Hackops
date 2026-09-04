import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.routers import auth, participants, teams, events, documents, mentors, resources, qa, submissions, issues, allocations, resource_requests, reminders, orchestrator, notifications, dashboard

settings = get_settings()

logger = logging.getLogger(__name__)

APP_VERSION = "1.3.0"

# ─── Background scheduler (autonomous loop) ─────────────────
# The closed-loop orchestrator, reminder sweep, mentor-allocation
# timeout check, and resource-overdue check all run unattended on
# real intervals. Manual POST triggers remain for demo/testing.
_scheduler = AsyncIOScheduler()


async def _job_orchestrator_sweep():
    """Run the full orchestrator sweep (all 3 loop instances)."""
    from app.database import AsyncSessionLocal
    from app.services.orchestrator import run_full_sweep

    logger.info("[scheduler] orchestrator sweep starting")
    async with AsyncSessionLocal() as session:
        try:
            result = await run_full_sweep(session)
            await session.commit()
            logger.info(
                "[scheduler] sweep complete: runs=%d verified=%d failed=%d",
                result.get("total_runs"), result.get("verified_runs"),
                result.get("failed_verifications"),
            )
        except Exception:
            logger.exception("[scheduler] orchestrator sweep failed")
            await session.rollback()


async def _job_reminder_sweep():
    """Run the proactive reminder sweep."""
    from app.database import AsyncSessionLocal
    from app.services.reminder import sweep_reminders

    logger.info("[scheduler] reminder sweep starting")
    async with AsyncSessionLocal() as session:
        try:
            result = await sweep_reminders(session)
            await session.commit()
            logger.info(
                "[scheduler] reminder sweep: checked=%d needing=%d sent=%d",
                result.teams_checked, result.teams_needing_reminders,
                result.total_notifications_sent,
            )
        except Exception:
            logger.exception("[scheduler] reminder sweep failed")
            await session.rollback()


async def _job_mentor_timeouts():
    """Re-offer timed-out mentor allocations."""
    from app.database import AsyncSessionLocal
    from app.services.mentor_allocation import check_and_handle_timeouts

    logger.info("[scheduler] mentor timeout check starting")
    async with AsyncSessionLocal() as session:
        try:
            reoffered = await check_and_handle_timeouts(session)
            await session.commit()
            if reoffered:
                logger.info("[scheduler] re-offered %d timed-out allocation(s)", len(reoffered))
        except Exception:
            logger.exception("[scheduler] mentor timeout check failed")
            await session.rollback()


async def _job_resource_overdue():
    """Mark overdue resource allocations."""
    from app.database import AsyncSessionLocal
    from app.services.resource_allocation import check_overdue_allocations

    logger.info("[scheduler] resource overdue check starting")
    async with AsyncSessionLocal() as session:
        try:
            overdue = await check_overdue_allocations(session)
            await session.commit()
            if overdue:
                logger.info("[scheduler] marked %d allocation(s) overdue", len(overdue))
        except Exception:
            logger.exception("[scheduler] resource overdue check failed")
            await session.rollback()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background jobs on startup, shut them down cleanly on exit."""
    if settings.scheduler_enabled:
        _scheduler.add_job(
            _job_orchestrator_sweep,
            trigger=IntervalTrigger(minutes=settings.sweep_interval_minutes),
            id="orchestrator_sweep",
            replace_existing=True,
            max_instances=1,
        )
        _scheduler.add_job(
            _job_reminder_sweep,
            trigger=IntervalTrigger(minutes=settings.reminder_interval_minutes),
            id="reminder_sweep",
            replace_existing=True,
            max_instances=1,
        )
        _scheduler.add_job(
            _job_mentor_timeouts,
            trigger=IntervalTrigger(minutes=settings.mentor_timeout_interval_minutes),
            id="mentor_timeout_check",
            replace_existing=True,
            max_instances=1,
        )
        _scheduler.add_job(
            _job_resource_overdue,
            trigger=IntervalTrigger(minutes=settings.resource_overdue_interval_minutes),
            id="resource_overdue_check",
            replace_existing=True,
            max_instances=1,
        )
        _scheduler.start()
        logger.info(
            "[scheduler] started: sweep=%sm reminder=%sm mentor-timeout=%sm resource-overdue=%sm",
            settings.sweep_interval_minutes,
            settings.reminder_interval_minutes,
            settings.mentor_timeout_interval_minutes,
            settings.resource_overdue_interval_minutes,
        )
    yield
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


app = FastAPI(
    title="Pulse — Hackathon Concierge API",
    version=APP_VERSION,
    description="Autonomous Hackathon Event Operations Agent",
    lifespan=lifespan,
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
    return {
        "status": "ok",
        "service": "pulse-backend",
        "version": APP_VERSION,
        "scheduler_enabled": settings.scheduler_enabled,
    }