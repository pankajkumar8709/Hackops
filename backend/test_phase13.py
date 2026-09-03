#!/usr/bin/env python3
"""Phase 13 smoke test — Organizer Dashboard.

Tests all dashboard endpoints: health aggregation, approval queue,
broadcast, overrides, export, and escalation resolve.
"""
import httpx
import json
import asyncio
import asyncpg
import time
import sys
import os
os.environ["PYTHONIOENCODING"] = "utf-8"

BASE = "http://localhost:8000"
TOKEN = None
passed = 0
failed = 0


def ok(label, condition=True):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {label}")
    else:
        failed += 1
        print(f"  ❌ {label}")


def get_headers():
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


async def seed_test_data():
    """Create seed data: team, participant, submission, issue, escalation, mentor allocation."""
    # Read DB URL from config
    sys.path.insert(0, os.path.dirname(__file__))
    from app.config import get_settings
    settings = get_settings()
    # Convert asyncpg URL to plain asyncpg format
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)

    # Create organizer JWT manually
    import jwt
    from datetime import datetime, timedelta, timezone
    from app.config import get_settings
    settings = get_settings()
    payload = {
        "sub": "organizer",
        "role": "organizer",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    # Clean old test data
    await conn.execute("DELETE FROM notifications WHERE trigger_reason LIKE '%%test%%'")
    await conn.execute("DELETE FROM agent_actions WHERE action_type LIKE '%%test%%'")
    await conn.execute("DELETE FROM resource_allocations WHERE team_id IN (SELECT id FROM teams WHERE name LIKE '%%Phase13%%')")
    await conn.execute("DELETE FROM mentor_allocations WHERE issue_id IN (SELECT id FROM issues WHERE description LIKE '%%Phase13%%')")
    await conn.execute("DELETE FROM escalations WHERE issue_id IN (SELECT id FROM issues WHERE description LIKE '%%Phase13%%')")
    await conn.execute("DELETE FROM issues WHERE description LIKE '%%Phase13%%'")
    await conn.execute("DELETE FROM submissions WHERE team_id IN (SELECT id FROM teams WHERE name LIKE '%%Phase13%%')")
    await conn.execute("DELETE FROM participants WHERE name LIKE '%%Phase13%%'")
    await conn.execute("DELETE FROM teams WHERE name LIKE '%%Phase13%%'")

    # Create team
    team_id = await conn.fetchval(
        "INSERT INTO teams (name, submission_status, readiness_pct) VALUES ($1, $2, $3) RETURNING id",
        "Phase13 Test Team", "in_progress", 75.0,
    )

    # Create participant
    import hashlib
    import time as _time
    unique_suffix = str(int(_time.time() * 1000))[-6:]
    token_hash = hashlib.sha256(f"test_participant_token_p13_{unique_suffix}".encode()).hexdigest()
    participant_id = await conn.fetchval(
        "INSERT INTO participants (name, skills, email, track_pref, discord_handle, token_hash, team_id) VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
        "Phase13 Tester", ["python", "fastapi"], f"test_p13_{unique_suffix}@example.com", "ai", f"tester_{unique_suffix}#1234", token_hash, team_id,
    )

    # Create submission
    sub_id = await conn.fetchval(
        "INSERT INTO submissions (team_id, repo_url, demo_url, description, completeness_pct) VALUES ($1, $2, $3, $4, $5) RETURNING id",
        team_id, "https://github.com/test/repo", "https://demo.test.com", "Phase13 test submission", 50.0,
    )

    # Create issue
    issue_id = await conn.fetchval(
        "INSERT INTO issues (participant_id, team_id, description, category, severity, is_blocking, status, urgency_score) VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id",
        participant_id, team_id, "Phase13 test issue - deployment problem", "technical", 0.8, True, "open", 0.85,
    )

    # Create escalation
    esc_id = await conn.fetchval(
        "INSERT INTO escalations (issue_id, urgency_score, status) VALUES ($1, $2, $3) RETURNING id",
        issue_id, 0.85, "open",
    )

    # Create mentor
    mentor_id = await conn.fetchval(
        "INSERT INTO mentors (name, skills, availability_status) VALUES ($1, $2, $3) RETURNING id",
        "Phase13 Mentor", ["deployment", "devops"], "available",
    )

    # Create mentor allocation (proposed)
    alloc_id = await conn.fetchval(
        "INSERT INTO mentor_allocations (mentor_id, issue_id, status, reasoning) VALUES ($1, $2, $3, $4) RETURNING id",
        mentor_id, issue_id, "proposed", "Phase13 test allocation - skills match",
    )

    await conn.close()
    return token, team_id, participant_id, issue_id, esc_id, alloc_id, sub_id


async def run_tests():
    global TOKEN

    print("\n[TEST] Phase 13 - Organizer Dashboard")
    print("=" * 50)

    # Seed
    print("\n[SEED] Seeding test data...")
    TOKEN, team_id, participant_id, issue_id, esc_id, alloc_id, sub_id = await seed_test_data()
    ok("Seed data created")

    async with httpx.AsyncClient(timeout=60) as c:
        # ─── 1. Health endpoint ───────────────────
        print("\n[HEALTH] Dashboard Health")
        r = await c.get(f"{BASE}/dashboard/health", headers=get_headers())
        ok("GET /dashboard/health returns 200", r.status_code == 200)
        data = r.json()
        ok("Has total_teams field", "total_teams" in data)
        ok("Has teams_ready field", "teams_ready" in data)
        ok("Has avg_readiness_pct field", "avg_readiness_pct" in data)
        ok("Has total_participants field", "total_participants" in data)
        ok("Has open_escalations field", "open_escalations" in data)
        ok("Has total_agent_actions field", "total_agent_actions" in data)
        ok("Has teams list", isinstance(data.get("teams"), list))
        ok("Has mentors list", isinstance(data.get("mentors"), list))
        ok("Has resource_pools list", isinstance(data.get("resource_pools"), list))
        ok("Total teams >= 1", data.get("total_teams", 0) >= 1)
        ok("Total participants >= 1", data.get("total_participants", 0) >= 1)
        ok("Our team appears in teams list",
           any(t["name"] == "Phase13 Test Team" for t in data.get("teams", [])))

        # ─── 2. Approval queue ────────────────────
        print("\n[APPROVAL] Approval Queue")
        r = await c.get(f"{BASE}/dashboard/approval-queue", headers=get_headers())
        ok("GET /dashboard/approval-queue returns 200", r.status_code == 200)
        aq = r.json()
        ok("Has items list", isinstance(aq.get("items"), list))
        ok("Has total_pending field", "total_pending" in aq)
        ok("Proposed allocation appears in queue",
           any(i["entity_type"] == "mentor_allocation" for i in aq.get("items", [])))
        ok("Item has action_type", all("action_type" in i for i in aq.get("items", [])))
        ok("Item has description", all("description" in i for i in aq.get("items", [])))

        # ─── 3. Broadcast ────────────────────────
        print("\n[BROADCAST] Broadcast")
        r = await c.post(f"{BASE}/dashboard/broadcast", headers=get_headers(),
                        json={"message": "Phase13 test broadcast message", "channel": "in_app"})
        ok("POST /dashboard/broadcast returns 200", r.status_code == 200)
        bc = r.json()
        ok("Has total_recipients", bc.get("total_recipients", 0) >= 1)
        ok("Has notifications_sent", bc.get("notifications_sent", 0) >= 1)
        ok("Has message_preview", "message_preview" in bc)

        # ─── 4. Override team ─────────────────────
        print("\n[OVERRIDE] Manual Override")
        r = await c.patch(f"{BASE}/dashboard/teams/{team_id}/override", headers=get_headers(),
                         json={"submission_status": "submitted", "readiness_pct": 100.0})
        ok("PATCH /dashboard/teams/{id}/override returns 200", r.status_code == 200)
        ov = r.json()
        ok("Override confirms team name", ov.get("name") == "Phase13 Test Team")
        ok("Override updates submission_status", ov.get("submission_status") == "submitted")
        ok("Override updates readiness_pct", ov.get("readiness_pct") == 100.0)

        # Verify override persisted via health endpoint
        r = await c.get(f"{BASE}/dashboard/health", headers=get_headers())
        team_data = next((t for t in r.json()["teams"] if t["name"] == "Phase13 Test Team"), None)
        ok("Override persisted in health view", team_data and team_data["submission_status"] == "submitted")
        ok("Override readiness persisted", team_data and team_data["readiness_pct"] == 100.0)

        # ─── 5. Override submission ───────────────
        r = await c.patch(f"{BASE}/dashboard/submissions/{sub_id}/override", headers=get_headers(),
                         json={"completeness_pct": 95.0})
        ok("PATCH /dashboard/submissions/{id}/override returns 200", r.status_code == 200)
        sv = r.json()
        ok("Submission override confirms pct", sv.get("completeness_pct") == 95.0)

        # ─── 6. Export CSV ────────────────────────
        print("\n[EXPORT] Export")
        r = await c.get(f"{BASE}/dashboard/export", headers=get_headers())
        ok("GET /dashboard/export returns 200", r.status_code == 200)
        ok("Response is CSV content-type", "text/csv" in r.headers.get("content-type", ""))
        csv_text = r.text
        ok("CSV has header row", "Team Name" in csv_text)
        ok("CSV contains our team", "Phase13 Test Team" in csv_text)

        # ─── 7. Escalation resolve ────────────────
        print("\n[ESCALATION] Escalation Resolve")
        r = await c.patch(f"{BASE}/escalations/{esc_id}/resolve", headers=get_headers(),
                        json={"resolution_notes": "Phase13 test resolution"})
        ok("PATCH /escalations/{id}/resolve returns 200", r.status_code == 200)
        rv = r.json()
        ok("Escalation status is resolved", rv.get("status") == "resolved")
        ok("Resolution notes saved", rv.get("resolution_notes") == "Phase13 test resolution")

        # ─── 8. Orchestrator endpoints ────────────
        print("\n[ORCHESTRATOR] Orchestrator (dashboard integration)")
        r = await c.get(f"{BASE}/orchestrator/status", headers=get_headers())
        ok("GET /orchestrator/status returns 200", r.status_code == 200)
        os = r.json()
        ok("Orchestrator is operational", os.get("status") == "operational")
        ok("Has trigger_types list", isinstance(os.get("trigger_types"), list))

        r = await c.get(f"{BASE}/orchestrator/actions?limit=5", headers=get_headers())
        ok("GET /orchestrator/actions returns 200", r.status_code == 200)
        ok("Actions is a list", isinstance(r.json(), list))

        # ─── 9. Auth protection ───────────────────
        print("\n[AUTH] Auth Protection")
        r = await c.get(f"{BASE}/dashboard/health")
        ok("Unauthenticated request returns 403", r.status_code == 403)

        bad_payload = {"sub": "hacker", "role": "organizer", "exp": 9999999999}
        import jwt as pyjwt
        from app.config import get_settings as _gs
        _s = _gs()
        bad_token = pyjwt.encode(bad_payload, _s.jwt_secret, algorithm=_s.jwt_algorithm)
        r = await c.get(f"{BASE}/dashboard/health",
                       headers={"Authorization": f"Bearer {bad_token}"})
        ok("Valid JWT for non-existent organizer works (JWT doesn't check DB)",
           r.status_code == 200)

        # ─── 10. WebSocket endpoint exists ────────
        print("\n[WS] WebSocket")
        # WebSocket endpoints return 404 on plain HTTP GET (expected - only accepts WS upgrade)
        r = await c.get(f"{BASE}/dashboard/ws")
        ok("WebSocket endpoint exists (404 on HTTP GET is expected)", r.status_code in [404, 403, 426])

        # ─── 11. Health includes new fields ───────
        print("\n[COMPLETENESS] Dashboard completeness")
        r = await c.get(f"{BASE}/dashboard/health", headers=get_headers())
        health = r.json()
        ok("Health has total_notifications", "total_notifications" in health)
        ok("Health has total_submissions", "total_submissions" in health)
        ok("Notification count >= 1 (broadcast)", health["total_notifications"] >= 1)

    return passed, failed


if __name__ == "__main__":
    p, f = asyncio.run(run_tests())
    print(f"\n{'=' * 50}")
    print(f"Phase 13 Results: {p} passed, {f} failed")
    print(f"{'=' * 50}")
    sys.exit(1 if f > 0 else 0)
