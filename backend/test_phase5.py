"""
Phase 5 smoke test - Submission Audit Module
Run with:
    python test_phase5.py
Requires backend to be running on :8000.
"""
import httpx
import json
import sys
import time
import uuid
import asyncio
import asyncpg

BASE = "http://localhost:8000"
passed = 0
failed = 0


def h(label, r):
    print(f"\n--- {label} ---")
    print(f"  Status : {r.status_code}")
    try:
        print(f"  Body   : {json.dumps(r.json(), indent=2)[:500]}")
    except Exception:
        print(f"  Body   : {r.text[:300]}")
    return r


def check(condition, msg):
    global passed, failed
    if not condition:
        print(f"  FAIL: {msg}")
        failed += 1
        return False
    print(f"  PASS: {msg}")
    passed += 1
    return True


async def seed_track_and_requirements(db_url: str):
    """
    Create a test Event, Track, and SubmissionRequirement rows
    directly in the DB (Phase 3 admin endpoints don't exist yet).
    Returns (event_id, track_id).
    """
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if "?" in sync_url:
        sync_url = sync_url.split("?")[0]

    conn = await asyncpg.connect(sync_url)
    try:
        event_id = uuid.uuid4()
        track_id = uuid.uuid4()

        await conn.execute(
            "INSERT INTO events (id, name, current_phase, timezone, created_at) "
            "VALUES ($1, $2, $3, $4, NOW())",
            event_id, "Test Hackathon 2026", "submissions", "UTC",
        )

        await conn.execute(
            "INSERT INTO tracks (id, name, eligibility_rules, event_id, created_at) "
            "VALUES ($1, $2, $3, $4, NOW())",
            track_id, "AI/ML Track", "Open to all", event_id,
        )

        # Create 4 submission requirements
        for field_name in ("repo_url", "readme_url", "demo_url", "description"):
            req_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO submission_requirements (id, track_id, field_name, required) "
                "VALUES ($1, $2, $3, TRUE)",
                req_id, track_id, field_name,
            )

        return event_id, track_id
    finally:
        await conn.close()


async def get_db_url():
    """Read DATABASE_URL from the app config."""
    from app.config import get_settings
    settings = get_settings()
    return settings.database_url


print("=" * 50)
print("Phase 5 Smoke Test - Submission Audit Module")
print("=" * 50)

ts = int(time.time())

# Seed track + requirements
db_url = asyncio.run(get_db_url())
event_id, track_id = asyncio.run(seed_track_and_requirements(db_url))
print(f"\n  Seeded event_id={event_id}")
print(f"  Seeded track_id={track_id}")
print(f"  Created 4 submission_requirements for this track")

with httpx.Client(base_url=BASE, timeout=30) as c:

    # 1. Health check
    r = h("GET /health", c.get("/health"))
    check(r.status_code == 200, "/health returns 200")
    check(r.json()["version"] == "0.5.0", "version = 0.5.0")

    # 2. Organizer login
    r = h("POST /auth/organizer/login", c.post("/auth/organizer/login",
        json={"username": "organizer", "password": "pulse_admin_2026"}))
    check(r.status_code == 200, "organizer login 200")
    org_token = r.json()["access_token"]
    OHD = {"Authorization": f"Bearer {org_token}"}

    # 3. Register participant A
    r = h("Register Participant A", c.post("/participants/register",
        json={"name": "Alice", "email": f"alice_phase5_{ts}@example.com",
              "skills": ["Python", "ML"]}))
    check(r.status_code == 201, "register A: 201")
    token_a = r.json()["token"]
    AHD = {"Authorization": f"Bearer {token_a}"}

    # 4. Register participant B (for row-level scoping test)
    r = h("Register Participant B", c.post("/participants/register",
        json={"name": "Bob", "email": f"bob_phase5_{ts}@example.com",
              "skills": ["Go"]}))
    check(r.status_code == 201, "register B: 201")
    token_b = r.json()["token"]
    BHD = {"Authorization": f"Bearer {token_b}"}

    # 5. Create team as A (with the seeded track)
    r = h("POST /teams (A creates Team Alpha)", c.post("/teams",
        json={"name": f"Team Alpha {ts}", "track_id": str(track_id)},
        headers=AHD))
    check(r.status_code == 201, "create team: 201")
    team_a_id = r.json()["id"]

    # 6. B joins Team Alpha
    r = h(f"POST /teams/{team_a_id}/join (B joins)", c.post(f"/teams/{team_a_id}/join", headers=BHD))
    check(r.status_code == 200, "B joins team: 200")

    # 7. POST /submissions - incomplete submission (only repo_url)
    r = h("POST /submissions (incomplete - only repo_url)", c.post("/submissions",
        json={"repo_url": "https://github.com/team-alpha/project"},
        headers=AHD))
    check(r.status_code == 201, "create submission: 201")
    sub = r.json()
    sub_id = sub["id"]
    check(sub["team_id"] == team_a_id, "submission linked to correct team")
    check(sub["completeness_pct"] == 25.0,
          f"completeness_pct = {sub['completeness_pct']} (expected 25.0 - 1 of 4 required fields)")
    check(sub["last_audited_at"] is not None, "last_audited_at is set")

    # 8. GET /submissions/mine
    r = h("GET /submissions/mine", c.get("/submissions/mine", headers=AHD))
    check(r.status_code == 200, "GET /submissions/mine: 200")
    check(r.json()["id"] == sub_id, "mine returns the correct submission")

    # 9. GET /submissions/{id}/audit - detailed audit
    r = h(f"GET /submissions/{sub_id}/audit", c.get(f"/submissions/{sub_id}/audit", headers=AHD))
    check(r.status_code == 200, "GET audit: 200")
    audit = r.json()
    check(audit["total_required"] == 4, f"total_required = {audit['total_required']} (expected 4)")
    check(audit["total_present"] == 1, f"total_present = {audit['total_present']} (expected 1)")
    check(audit["completeness_pct"] == 25.0, "audit completeness = 25%")

    # Check individual field results
    fields = {f["field_name"]: f for f in audit["fields"]}
    check(fields["repo_url"]["passed"] is True, "repo_url passed")
    check(fields["readme_url"]["passed"] is False, "readme_url failed")
    check(fields["demo_url"]["passed"] is False, "demo_url failed")
    check(fields["description"]["passed"] is False, "description failed")

    # 10. PATCH /submissions/{id} - add more fields
    r = h("PATCH /submissions (add readme_url + demo_url)", c.patch(f"/submissions/{sub_id}",
        json={"readme_url": "https://github.com/team-alpha/project/blob/main/README.md",
              "demo_url": "https://youtu.be/demo123"},
        headers=AHD))
    check(r.status_code == 200, "PATCH submission: 200")
    updated = r.json()
    check(updated["completeness_pct"] == 75.0,
          f"completeness_pct = {updated['completeness_pct']} (expected 75.0 - 3 of 4)")
    check(updated["repo_url"] == "https://github.com/team-alpha/project", "repo_url preserved")
    check(updated["readme_url"] is not None, "readme_url updated")
    check(updated["demo_url"] is not None, "demo_url updated")

    # 11. PATCH - add description to reach 100%
    r = h("PATCH /submissions (add description -> 100%)", c.patch(f"/submissions/{sub_id}",
        json={"description": "An AI-powered hackathon concierge that helps teams succeed."},
        headers=AHD))
    check(r.status_code == 200, "PATCH submission: 200")
    final = r.json()
    check(final["completeness_pct"] == 100.0,
          f"completeness_pct = {final['completeness_pct']} (expected 100.0 - all 4 fields)")

    # 12. Row-level scoping: B (same team) can view
    r = h("GET audit as B (same team - should 200)", c.get(f"/submissions/{sub_id}/audit", headers=BHD))
    check(r.status_code == 200, "B can view same team's audit")

    # 13. Row-level scoping: register C (different team), try to view A's submission
    r = h("Register Participant C", c.post("/participants/register",
        json={"name": "Carol", "email": f"carol_phase5_{ts}@example.com",
              "skills": ["JS"]}))
    check(r.status_code == 201, "register C: 201")
    token_c = r.json()["token"]
    CHD = {"Authorization": f"Bearer {token_c}"}

    r = h("POST /teams (C creates Team Bravo)", c.post("/teams",
        json={"name": f"Team Bravo {ts}"},
        headers=CHD))
    check(r.status_code == 201, "C creates team: 201")

    r = h("GET audit as C (different team - should 403)", c.get(f"/submissions/{sub_id}/audit", headers=CHD))
    check(r.status_code == 403, "C cannot view A's team submission -> 403")

    # 14. Organizer endpoints
    r = h("GET /submissions (organizer)", c.get("/submissions", headers=OHD))
    check(r.status_code == 200, "organizer list submissions: 200")
    check(isinstance(r.json(), list), "returns a list")
    check(len(r.json()) >= 1, "at least 1 submission listed")

    r = h("GET audit-organizer (organizer views any submission)",
          c.get(f"/submissions/{sub_id}/audit-organizer", headers=OHD))
    check(r.status_code == 200, "organizer audit: 200")
    check(r.json()["completeness_pct"] == 100.0, "organizer sees 100% completeness")

    # 15. Re-submit (POST again - should update existing)
    r = h("POST /submissions (re-submit - overwrites)", c.post("/submissions",
        json={"repo_url": "https://github.com/team-alpha/project-v2"},
        headers=AHD))
    check(r.status_code == 201, "re-submit: 201")
    resub = r.json()
    # Re-submit preserves existing fields, only updates provided ones
    check(resub["completeness_pct"] == 100.0,
          f"re-submit completeness = {resub['completeness_pct']} (expected 100.0 - fields preserved)")
    check(resub["repo_url"] == "https://github.com/team-alpha/project-v2",
          "repo_url updated to v2")
    check(resub["readme_url"] is not None, "readme_url preserved")

    # 16. No token -> 403
    r = h("POST /submissions (no token - should 403)", c.post("/submissions",
        json={"repo_url": "https://example.com"}))
    check(r.status_code == 403, "no token -> 403")

    # 17. GET /submissions/mine when not in team (C has no submission)
    r = h("GET /submissions/mine (C has no submission - edge case)",
          c.get("/submissions/mine", headers=CHD))
    check(r.status_code == 404, "C has no submission -> 404")


print(f"\n{'=' * 50}")
print(f"Results: {passed} passed, {failed} failed out of {passed + failed} checks")
if failed == 0:
    print("ALL PHASE 5 CHECKS PASSED")
else:
    print("SOME CHECKS FAILED")
    sys.exit(1)
print("=" * 50)
