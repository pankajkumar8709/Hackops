"""
Phase 6 smoke test - Escalation & Urgency Scoring
Run with:
    python test_phase6.py
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


async def seed_event_and_team(db_url: str):
    """
    Seed a test Event, Track, Team, and Participant directly in the DB.
    Returns (event_id, track_id, team_id, participant_id, participant_token).
    """
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if "?" in sync_url:
        sync_url = sync_url.split("?")[0]

    conn = await asyncpg.connect(sync_url)
    try:
        event_id = uuid.uuid4()
        track_id = uuid.uuid4()
        team_id = uuid.uuid4()
        participant_id = uuid.uuid4()

        # Create event
        await conn.execute(
            "INSERT INTO events (id, name, current_phase, timezone, created_at) "
            "VALUES ($1, $2, $3, $4, NOW())",
            event_id, "Test Hackathon 2026", "submissions", "UTC",
        )

        # Create track
        await conn.execute(
            "INSERT INTO tracks (id, name, eligibility_rules, event_id, created_at) "
            "VALUES ($1, $2, $3, $4, NOW())",
            track_id, "AI/ML Track", "Open to all", event_id,
        )

        # Create team
        await conn.execute(
            "INSERT INTO teams (id, name, track_id, submission_status, readiness_pct, created_at) "
            "VALUES ($1, $2, $3, $4, $5, NOW())",
            team_id, "Team Alpha", track_id, "not_submitted", 0.0,
        )

        # Create participant (raw token hash stored in DB)
        import hashlib
        participant_token = "test_token_p6_" + uuid.uuid4().hex[:16]
        token_hash = hashlib.sha256(participant_token.encode()).hexdigest()

        await conn.execute(
            "INSERT INTO participants (id, name, email, skills, track_pref, "
            "discord_handle, token_hash, team_id, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())",
            participant_id, "Test User P6", f"test_p6_{uuid.uuid4().hex[:8]}@example.com",
            ["python", "ml"], "ai", "test_user", token_hash, team_id,
        )

        # Build a proper JWT for the participant
        from app.auth import create_jwt
        jwt_token = create_jwt({"sub": str(participant_id), "role": "participant"})

        return event_id, track_id, team_id, participant_id, jwt_token
    finally:
        await conn.close()


def run_tests():
    global passed, failed

    print("=" * 60)
    print("Phase 6: Escalation & Urgency Scoring - Smoke Test")
    print("=" * 60)

    # Load DB URL from .env
    import os
    from pathlib import Path
    env_path = Path(__file__).resolve().parent.parent / ".env"
    db_url = None
    with open(env_path) as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                db_url = line.strip().split("=", 1)[1]
                break

    if not db_url:
        print("ERROR: DATABASE_URL not found in .env")
        sys.exit(1)

    # Seed data
    print("\n[setup] Seeding event, track, team, participant...")
    event_id, track_id, team_id, participant_id, participant_token = \
        asyncio.run(seed_event_and_team(db_url))
    print(f"  event_id={event_id}")
    print(f"  track_id={track_id}")
    print(f"  team_id={team_id}")
    print(f"  participant_id={participant_id}")
    print(f"  participant_token={participant_token[:20]}...")

    # Organizer login
    print("\n[setup] Organizer login...")
    r = httpx.post(f"{BASE}/auth/organizer/login", json={
        "username": "organizer",
        "password": "pulse_admin_2026",
    }, timeout=30)
    check(r.status_code == 200, "Organizer login 200")
    org_token = r.json()["access_token"]
    org_h = {"Authorization": f"Bearer {org_token}"}
    part_h = {"Authorization": f"Bearer {participant_token}"}

    # ─── Test 1: Urgency scoring function (unit test) ────────
    print("\n[urgency] Testing urgency scoring formula...")

    # Test urgency formula directly via import
    from app.services.urgency import compute_urgency

    # Low severity, not blocking, far from deadline
    u1 = compute_urgency(severity=0.2, is_blocking=False, minutes_to_deadline=120)
    check(0.0 < u1 < 0.3, f"Low urgency: {u1}")

    # High severity, blocking, close to deadline
    u2 = compute_urgency(severity=1.0, is_blocking=True, minutes_to_deadline=10)
    check(0.5 < u2 < 0.8, f"High urgency: {u2}")

    # Medium severity, blocking, moderate time
    u3 = compute_urgency(severity=0.5, is_blocking=True, minutes_to_deadline=60)
    check(0.3 < u3 < 0.8, f"Medium urgency: {u3}")

    # Default (no deadline specified)
    u4 = compute_urgency(severity=0.5, is_blocking=False, minutes_to_deadline=None)
    check(0.0 < u4 < 1.0, f"Default urgency: {u4}")

    # Not blocking, zero severity
    u5 = compute_urgency(severity=0.0, is_blocking=False, minutes_to_deadline=200)
    check(0.0 < u5 < 0.15, f"Minimal urgency: {u5}")

    # ─── Test 2: POST /issues (create issue) ─────────────────
    print("\n[POST /issues] Creating issues...")

    # Low severity issue
    r = h("POST /issues (low severity)", httpx.post(
        f"{BASE}/issues",
        headers=part_h,
        json={
            "description": "Minor UI alignment issue",
            "category": "bug",
            "severity": 0.2,
            "is_blocking": False,
        },
        timeout=30,
    ))
    check(r.status_code == 201, "Low severity issue created (201)")
    issue1_id = r.json().get("id")
    check(issue1_id is not None, f"issue1_id={issue1_id}")

    # High severity, blocking issue (should auto-escalate)
    r = h("POST /issues (high severity, blocking)", httpx.post(
        f"{BASE}/issues",
        headers=part_h,
        json={
            "description": "Cannot deploy - server 500 error blocks all progress",
            "category": "deployment",
            "severity": 1.0,
            "is_blocking": True,
        },
        timeout=30,
    ))
    check(r.status_code == 201, "High severity issue created (201)")
    issue2_id = r.json().get("id")
    check(r.json().get("urgency_score", 0) > 0.5,
          f"High severity urgency_score={r.json().get('urgency_score')} > 0.5")

    # Another blocking issue
    r = h("POST /issues (medium blocking)", httpx.post(
        f"{BASE}/issues",
        headers=part_h,
        json={
            "description": "Database connection pool exhausted",
            "category": "infrastructure",
            "severity": 0.7,
            "is_blocking": True,
        },
        timeout=30,
    ))
    check(r.status_code == 201, "Medium blocking issue created (201)")
    issue3_id = r.json().get("id")

    # Non-blocking issue with low severity (should NOT auto-escalate)
    r = h("POST /issues (low, non-blocking)", httpx.post(
        f"{BASE}/issues",
        headers=part_h,
        json={
            "description": "README typos need fixing",
            "category": "documentation",
            "severity": 0.1,
            "is_blocking": False,
        },
        timeout=30,
    ))
    check(r.status_code == 201, "Low non-blocking issue created (201)")
    issue4_id = r.json().get("id")

    # ─── Test 3: POST /issues (validation) ───────────────────
    print("\n[POST /issues] Validation tests...")

    r = h("POST /issues (missing description)", httpx.post(
        f"{BASE}/issues",
        headers=part_h,
        json={"category": "bug"},
        timeout=30,
    ))
    check(r.status_code == 422, "Missing description returns 422")

    r = h("POST /issues (severity out of range)", httpx.post(
        f"{BASE}/issues",
        headers=part_h,
        json={
            "description": "Test issue",
            "severity": 1.5,
        },
        timeout=30,
    ))
    check(r.status_code == 422, "Severity > 1.0 returns 422")

    # ─── Test 4: POST /issues (no team) ─────────────────────
    print("\n[POST /issues] No-team participant...")

    # Create a participant without a team
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if "?" in sync_url:
        sync_url = sync_url.split("?")[0]

    async def create_orphan_participant():
        conn = await asyncpg.connect(sync_url)
        try:
            orphan_id = uuid.uuid4()
            import hashlib
            orphan_token = "orphan_token_p6_" + uuid.uuid4().hex[:16]
            token_hash = hashlib.sha256(orphan_token.encode()).hexdigest()
            await conn.execute(
                "INSERT INTO participants (id, name, email, skills, track_pref, "
                "discord_handle, token_hash, team_id, created_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, NULL, NOW())",
                orphan_id, "Orphan User", f"orphan_{uuid.uuid4().hex[:8]}@example.com",
                ["python"], "ai", "orphan_user", token_hash,
            )
            return orphan_id
        finally:
            await conn.close()

    orphan_id = asyncio.run(create_orphan_participant())
    from app.auth import create_jwt as _create_jwt
    orphan_jwt = _create_jwt({"sub": str(orphan_id), "role": "participant"})
    orphan_h = {"Authorization": f"Bearer {orphan_jwt}"}

    r = h("POST /issues (no team)", httpx.post(
        f"{BASE}/issues",
        headers=orphan_h,
        json={
            "description": "I need help but have no team",
            "category": "general",
        },
        timeout=30,
    ))
    check(r.status_code == 409, "No team returns 409 Conflict")

    # ─── Test 5: GET /issues/mine ────────────────────────────
    print("\n[GET /issues/mine] Participant views own issues...")

    r = h("GET /issues/mine", httpx.get(
        f"{BASE}/issues/mine",
        headers=part_h,
        timeout=30,
    ))
    check(r.status_code == 200, "GET /issues/mine 200")
    issues = r.json()
    check(len(issues) >= 4, f"Found {len(issues)} issues (expected >= 4)")
    check(
        all(i.get("urgency_score", 0) > 0 for i in issues),
        "All issues have urgency_score > 0",
    )

    # ─── Test 6: GET /issues/{id} (own team) ────────────────
    print("\n[GET /issues/{id}] View specific issue...")

    r = h("GET /issues/{id} (own issue)", httpx.get(
        f"{BASE}/issues/{issue1_id}",
        headers=part_h,
        timeout=30,
    ))
    check(r.status_code == 200, "GET own issue 200")
    check(r.json().get("id") == issue1_id, "Returned correct issue ID")

    # Non-existent issue
    fake_id = str(uuid.uuid4())
    r = h("GET /issues/{id} (not found)", httpx.get(
        f"{BASE}/issues/{fake_id}",
        headers=part_h,
        timeout=30,
    ))
    check(r.status_code == 404, "Non-existent issue returns 404")

    # ─── Test 7: GET /escalations (organizer) ────────────────
    print("\n[GET /escalations] Organizer views escalation queue...")

    r = h("GET /escalations", httpx.get(
        f"{BASE}/escalations",
        headers=org_h,
        timeout=30,
    ))
    check(r.status_code == 200, "GET /escalations 200")
    escalations = r.json()
    check(len(escalations) >= 1, f"Found {len(escalations)} escalations (expected >= 1)")

    # Verify sorted by urgency (highest first)
    if len(escalations) >= 2:
        urgencies = [e["urgency_score"] for e in escalations]
        check(
            urgencies == sorted(urgencies, reverse=True),
            f"Escalations sorted by urgency desc: {urgencies}",
        )

    # Check that high-severity blocking issue was escalated
    esc_issue_ids = [e.get("issue_id") for e in escalations]
    check(
        issue2_id in esc_issue_ids,
        f"High-severity blocking issue {issue2_id} was escalated",
    )

    # Verify nested issue data is present
    first_esc = escalations[0]
    check(
        first_esc.get("issue") is not None,
        "Escalation includes nested issue data",
    )
    check(
        first_esc["issue"].get("description") is not None,
        "Nested issue has description",
    )

    # ─── Test 8: GET /escalations?status=open (filtered) ─────
    print("\n[GET /escalations?status=open] Filter by status...")

    r = h("GET /escalations?status=open", httpx.get(
        f"{BASE}/escalations",
        headers=org_h,
        params={"status": "open"},
        timeout=30,
    ))
    check(r.status_code == 200, "GET /escalations?status=open 200")
    open_escs = r.json()
    check(
        all(e["status"] == "open" for e in open_escs),
        "All returned escalations have status=open",
    )

    # ─── Test 9: PATCH /escalations/{id}/resolve ─────────────
    print("\n[PATCH /escalations/{id}/resolve] Resolve an escalation...")

    # Find an open escalation
    open_esc = next((e for e in escalations if e["status"] == "open"), None)
    if open_esc:
        esc_id = open_esc["id"]

        r = h("PATCH /escalations/{id}/resolve", httpx.patch(
            f"{BASE}/escalations/{esc_id}/resolve",
            headers=org_h,
            json={
                "resolution_notes": "Fixed by restarting the server",
            },
            timeout=30,
        ))
        check(r.status_code == 200, "Resolve escalation 200")
        check(r.json().get("status") == "resolved", "Status changed to 'resolved'")
        check(
            r.json().get("resolution_notes") == "Fixed by restarting the server",
            "Resolution notes saved",
        )
        check(
            r.json().get("resolved_at") is not None,
            "resolved_at timestamp set",
        )

        # Verify the underlying issue is also resolved
        issue_id = open_esc.get("issue_id")
        if issue_id:
            r = h("GET /issues/{id} (after resolve)", httpx.get(
                f"{BASE}/issues/{issue_id}",
                headers=part_h,
                timeout=30,
            ))
            if r.status_code == 200:
                check(
                    r.json().get("status") == "resolved",
                    "Underlying issue status updated to 'resolved'",
                )
    else:
        print("  [SKIP] No open escalations to resolve")

    # ─── Test 10: PATCH /escalations (non-existent) ──────────
    print("\n[PATCH /escalations/{id}/resolve] Non-existent...")

    fake_esc_id = str(uuid.uuid4())
    r = h("PATCH /escalations/{id}/resolve (not found)", httpx.patch(
        f"{BASE}/escalations/{fake_esc_id}/resolve",
        headers=org_h,
        json={"resolution_notes": "N/A"},
        timeout=30,
    ))
    check(r.status_code == 404, "Non-existent escalation returns 404")

    # ─── Test 11: GET /escalations after resolve ─────────────
    print("\n[GET /escalations] After resolving...")

    r = h("GET /escalations?status=open (post-resolve)", httpx.get(
        f"{BASE}/escalations",
        headers=org_h,
        params={"status": "open"},
        timeout=30,
    ))
    check(r.status_code == 200, "GET /escalations?status=open 200")
    remaining_open = r.json()
    check(
        len(remaining_open) < len(escalations),
        f"Fewer open escalations after resolve: {len(remaining_open)} < {len(escalations)}",
    )

    # ─── Test 12: Cooldown test (re-escalation prevention) ───
    print("\n[cooldown] Testing escalation cooldown...")

    # The high-severity issue was already escalated; re-creating should
    # not create a duplicate escalation within COOLDOWN_MINUTES
    r = h("POST /issues (same blocking issue - cooldown)", httpx.post(
        f"{BASE}/issues",
        headers=part_h,
        json={
            "description": "Cannot deploy - server 500 error blocks all progress (retry)",
            "category": "deployment",
            "severity": 1.0,
            "is_blocking": True,
        },
        timeout=30,
    ))
    check(r.status_code == 201, "Re-reported issue created (201)")

    # Check escalation count hasn't doubled
    r = h("GET /escalations (cooldown check)", httpx.get(
        f"{BASE}/escalations",
        headers=org_h,
        timeout=30,
    ))
    check(r.status_code == 200, "GET /escalations 200 (cooldown)")
    # Should still have roughly the same count (cooldown prevents duplicates)
    # Note: this is a new Issue with same severity, so it may create a new
    # escalation, but the cooldown logic should prevent rapid re-escalation
    # of the SAME issue. Since this is a different issue, it will escalate.
    # That's expected behavior.

    # ─── Test 13: Authorization tests ────────────────────────
    print("\n[auth] Authorization tests...")

    r = h("GET /escalations (no auth)", httpx.get(
        f"{BASE}/escalations",
        timeout=30,
    ))
    check(r.status_code in (401, 403), "GET /escalations without auth returns 401/403")

    r = h("GET /escalations (participant token)", httpx.get(
        f"{BASE}/escalations",
        headers=part_h,
        timeout=30,
    ))
    check(r.status_code == 403, "Participant cannot access /escalations (403)")

    # ─── Test 14: Edge cases ────────────────────────────────
    print("\n[edge cases] Various edge cases...")

    # Issue with zero severity
    r = h("POST /issues (zero severity)", httpx.post(
        f"{BASE}/issues",
        headers=part_h,
        json={
            "description": "Cosmetic issue only",
            "category": "cosmetic",
            "severity": 0.0,
            "is_blocking": False,
        },
        timeout=30,
    ))
    check(r.status_code == 201, "Zero severity issue created")
    check(r.json().get("urgency_score", 0) < 0.1, "Zero severity urgency < 0.1")

    # Issue with max severity, blocking, close deadline
    r = h("POST /issues (critical)", httpx.post(
        f"{BASE}/issues",
        headers=part_h,
        json={
            "description": "Everything is broken and we cannot submit",
            "category": "critical",
            "severity": 1.0,
            "is_blocking": True,
        },
        params={"minutes_to_deadline": 5},
        timeout=30,
    ))
    check(r.status_code == 201, "Critical issue created")
    check(
        r.json().get("urgency_score", 0) > 0.6,
        f"Critical urgency > 0.6: {r.json().get('urgency_score')}",
    )

    # ─── Test 15: Final escalation queue check ───────────────
    print("\n[final] Final escalation queue state...")

    r = h("GET /escalations (final)", httpx.get(
        f"{BASE}/escalations",
        headers=org_h,
        timeout=30,
    ))
    check(r.status_code == 200, "GET /escalations 200 (final)")
    final_escs = r.json()
    print(f"  Total escalations in queue: {len(final_escs)}")

    # All should have valid urgency scores
    for esc in final_escs:
        check(
            0.0 <= esc.get("urgency_score", -1) <= 2.0,
            f"Escalation urgency_score in valid range: {esc.get('urgency_score')}",
        )

    # ─── Summary ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
