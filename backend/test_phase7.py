"""
Phase 7 smoke test - Mentor Allocation
Run with:
    python test_phase7.py
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


async def seed_data(db_url: str):
    """
    Seed Event, Track, Team, Participant, and Mentors directly in the DB.
    Returns (event_id, track_id, team_id, participant_id, mentor_id_1, mentor_id_2, mentor_id_3).
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
        mentor_id_1 = uuid.uuid4()
        mentor_id_2 = uuid.uuid4()
        mentor_id_3 = uuid.uuid4()

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

        # Create participant
        import hashlib
        participant_token = "test_token_p7_" + uuid.uuid4().hex[:16]
        token_hash = hashlib.sha256(participant_token.encode()).hexdigest()

        await conn.execute(
            "INSERT INTO participants (id, name, email, skills, track_pref, "
            "discord_handle, token_hash, team_id, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())",
            participant_id, "Test User P7", f"test_p7_{uuid.uuid4().hex[:8]}@example.com",
            ["python", "ml"], "ai", "test_user", token_hash, team_id,
        )

        # Create mentors with different skills
        await conn.execute(
            "INSERT INTO mentors (id, name, skills, availability_status, discord_handle, created_at) "
            "VALUES ($1, $2, $3, $4, $5, NOW())",
            mentor_id_1, "DevOps Dan", ["docker", "deployment", "aws", "ci-cd"],
            "available", "devops_dan",
        )
        await conn.execute(
            "INSERT INTO mentors (id, name, skills, availability_status, discord_handle, created_at) "
            "VALUES ($1, $2, $3, $4, $5, NOW())",
            mentor_id_2, "ML Maya", ["machine-learning", "python", "deep-learning"],
            "available", "ml_maya",
        )
        await conn.execute(
            "INSERT INTO mentors (id, name, skills, availability_status, discord_handle, created_at) "
            "VALUES ($1, $2, $3, $4, $5, NOW())",
            mentor_id_3, "Busy Bob", ["frontend", "react", "css"],
            "busy", "busy_bob",
        )

        # Create a JWT for the participant
        from app.auth import create_jwt
        jwt_token = create_jwt({"sub": str(participant_id), "role": "participant"})

        return (event_id, track_id, team_id, participant_id,
                mentor_id_1, mentor_id_2, mentor_id_3, jwt_token)
    finally:
        await conn.close()


def run_tests():
    global passed, failed

    print("=" * 60)
    print("Phase 7: Mentor Allocation - Smoke Test")
    print("=" * 60)

    # Load DB URL
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
    print("\n[setup] Seeding data...")
    (event_id, track_id, team_id, participant_id,
     mentor_id_1, mentor_id_2, mentor_id_3, participant_token) = asyncio.run(seed_data(db_url))
    print(f"  event_id={event_id}")
    print(f"  track_id={track_id}")
    print(f"  team_id={team_id}")
    print(f"  participant_id={participant_id}")
    print(f"  mentor_1={mentor_id_1} (DevOps Dan)")
    print(f"  mentor_2={mentor_id_2} (ML Maya)")
    print(f"  mentor_3={mentor_id_3} (Busy Bob - busy)")

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

    # ─── Test 1: Create an issue ────────────────────────────
    print("\n[POST /issues] Creating issue...")

    r = h("POST /issues (deployment issue)", httpx.post(
        f"{BASE}/issues",
        headers=part_h,
        json={
            "description": "Cannot deploy to AWS - Docker build fails with error",
            "category": "deployment",
            "severity": 0.8,
            "is_blocking": True,
        },
        timeout=30,
    ))
    check(r.status_code == 201, "Issue created (201)")
    issue1_id = r.json().get("id")
    check(issue1_id is not None, f"issue1_id={issue1_id}")

    # ─── Test 2: Request mentor allocation ───────────────────
    print("\n[POST /mentor-allocations] Requesting mentor...")

    r = h("POST /mentor-allocations (request help)", httpx.post(
        f"{BASE}/mentor-allocations",
        headers=part_h,
        json={"issue_id": issue1_id},
        timeout=30,
    ))
    check(r.status_code == 201, "Allocation created (201)")
    alloc1 = r.json()
    alloc1_id = alloc1.get("id")
    check(alloc1_id is not None, f"alloc1_id={alloc1_id}")
    check(alloc1.get("status") == "proposed", "Status is 'proposed'")
    check(alloc1.get("mentor") is not None, "Mentor info included")
    check(alloc1.get("mentor", {}).get("name") is not None, "Mentor name included")
    check(alloc1.get("issue_summary") is not None, "Issue summary included")
    check(alloc1.get("reasoning") is not None, "Reasoning included")

    # Verify the matched mentor has relevant skills
    mentor_skills = alloc1.get("mentor", {}).get("skills", [])
    print(f"  Matched mentor: {alloc1.get('mentor', {}).get('name')}")
    print(f"  Mentor skills: {mentor_skills}")
    check(len(mentor_skills) > 0, "Mentor has skills")

    # ─── Test 3: Duplicate allocation should fail ────────────
    print("\n[POST /mentor-allocations] Duplicate check...")

    r = h("POST /mentor-allocations (duplicate)", httpx.post(
        f"{BASE}/mentor-allocations",
        headers=part_h,
        json={"issue_id": issue1_id},
        timeout=30,
    ))
    check(r.status_code == 409, "Duplicate allocation returns 409")

    # ─── Test 4: Accept allocation ───────────────────────────
    print("\n[PATCH /mentor-allocations/{id}/accept] Accept...")

    r = h("PATCH /mentor-allocations/{id}/accept", httpx.patch(
        f"{BASE}/mentor-allocations/{alloc1_id}/accept",
        headers=part_h,
        json={"notes": "I can help with Docker deployment issues."},
        timeout=30,
    ))
    check(r.status_code == 200, "Accept allocation 200")
    check(r.json().get("status") == "accepted", "Status changed to 'accepted'")
    check(r.json().get("responded_at") is not None, "responded_at set")

    # ─── Test 5: Cannot accept again ─────────────────────────
    print("\n[PATCH /mentor-allocations/{id}/accept] Already accepted...")

    r = h("PATCH /mentor-allocations/{id}/accept (already accepted)", httpx.patch(
        f"{BASE}/mentor-allocations/{alloc1_id}/accept",
        headers=part_h,
        json={},
        timeout=30,
    ))
    check(r.status_code == 409, "Cannot accept again -> 409")

    # ─── Test 6: Create another issue and test decline ───────
    print("\n[POST /issues] Creating second issue...")

    r = h("POST /issues (ML issue)", httpx.post(
        f"{BASE}/issues",
        headers=part_h,
        json={
            "description": "Need help with deep learning model training",
            "category": "machine-learning",
            "severity": 0.6,
            "is_blocking": False,
        },
        timeout=30,
    ))
    check(r.status_code == 201, "Second issue created (201)")
    issue2_id = r.json().get("id")

    r = h("POST /mentor-allocations (request ML mentor)", httpx.post(
        f"{BASE}/mentor-allocations",
        headers=part_h,
        json={"issue_id": issue2_id},
        timeout=30,
    ))
    check(r.status_code == 201, "Second allocation created (201)")
    alloc2_id = r.json().get("id")

    # Decline
    r = h("PATCH /mentor-allocations/{id}/decline", httpx.patch(
        f"{BASE}/mentor-allocations/{alloc2_id}/decline",
        headers=part_h,
        json={"reason": "Sorry, I'm overloaded this week."},
        timeout=30,
    ))
    check(r.status_code == 200, "Decline allocation 200")
    check(r.json().get("status") == "declined", "Status changed to 'declined'")
    check(r.json().get("responded_at") is not None, "responded_at set")

    # ─── Test 7: GET /mentor-allocations/mine ────────────────
    print("\n[GET /mentor-allocations/mine] List allocations...")

    r = h("GET /mentor-allocations/mine", httpx.get(
        f"{BASE}/mentor-allocations/mine",
        headers=part_h,
        timeout=30,
    ))
    check(r.status_code == 200, "GET /mine 200")
    allocs = r.json()
    check(len(allocs) >= 2, f"Found {len(allocs)} allocations (expected >= 2)")

    # Filter by status
    r = h("GET /mentor-allocations/mine?status=proposed", httpx.get(
        f"{BASE}/mentor-allocations/mine",
        headers=part_h,
        params={"status": "proposed"},
        timeout=30,
    ))
    check(r.status_code == 200, "GET /mine?status=proposed 200")

    # ─── Test 8: GET /mentor-allocations (organizer) ─────────
    print("\n[GET /mentor-allocations] Organizer list...")

    r = h("GET /mentor-allocations (organizer)", httpx.get(
        f"{BASE}/mentor-allocations",
        headers=org_h,
        timeout=30,
    ))
    check(r.status_code == 200, "Organizer list 200")
    check(len(r.json()) >= 2, f"Organizer sees >= 2 allocations")

    # ─── Test 9: GET /mentor-allocations/{id} ────────────────
    print("\n[GET /mentor-allocations/{id}] View specific...")

    r = h("GET /mentor-allocations/{id}", httpx.get(
        f"{BASE}/mentor-allocations/{alloc1_id}",
        headers=part_h,
        timeout=30,
    ))
    check(r.status_code == 200, "GET specific allocation 200")
    check(r.json().get("id") == alloc1_id, "Returned correct allocation")

    # ─── Test 10: POST /mentor-allocations (invalid issue) ───
    print("\n[POST /mentor-allocations] Invalid issue...")

    fake_id = str(uuid.uuid4())
    r = h("POST /mentor-allocations (invalid issue)", httpx.post(
        f"{BASE}/mentor-allocations",
        headers=part_h,
        json={"issue_id": fake_id},
        timeout=30,
    ))
    check(r.status_code == 404, "Invalid issue returns 404")

    # ─── Test 11: POST /mentor-allocations (no team) ─────────
    print("\n[POST /mentor-allocations] No team participant...")

    # Create orphan participant
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if "?" in sync_url:
        sync_url = sync_url.split("?")[0]

    async def create_orphan():
        conn = await asyncpg.connect(sync_url)
        try:
            orphan_id = uuid.uuid4()
            import hashlib
            orphan_token = "orphan_token_p7_" + uuid.uuid4().hex[:16]
            token_hash = hashlib.sha256(orphan_token.encode()).hexdigest()
            await conn.execute(
                "INSERT INTO participants (id, name, email, skills, track_pref, "
                "discord_handle, token_hash, team_id, created_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, NULL, NOW())",
                orphan_id, "Orphan P7", f"orphan_p7_{uuid.uuid4().hex[:8]}@example.com",
                ["python"], "ai", "orphan", token_hash,
            )
            from app.auth import create_jwt
            return create_jwt({"sub": str(orphan_id), "role": "participant"})
        finally:
            await conn.close()

    orphan_jwt = asyncio.run(create_orphan())
    orphan_h = {"Authorization": f"Bearer {orphan_jwt}"}

    r = h("POST /mentor-allocations (no team)", httpx.post(
        f"{BASE}/mentor-allocations",
        headers=orphan_h,
        json={"issue_id": str(uuid.uuid4())},
        timeout=30,
    ))
    check(r.status_code == 409, "No team returns 409")

    # ─── Test 12: Authorization tests ────────────────────────
    print("\n[auth] Authorization tests...")

    r = h("GET /mentor-allocations (no auth)", httpx.get(
        f"{BASE}/mentor-allocations",
        timeout=30,
    ))
    check(r.status_code in (401, 403), "No auth returns 401/403")

    r = h("POST /mentor-allocations (no auth)", httpx.post(
        f"{BASE}/mentor-allocations",
        json={"issue_id": str(uuid.uuid4())},
        timeout=30,
    ))
    check(r.status_code in (401, 403), "POST without auth returns 401/403")

    # ─── Test 13: Timeout check endpoint ─────────────────────
    print("\n[POST /mentor-allocations/check-timeouts] Timeout check...")

    r = h("POST /mentor-allocations/check-timeouts", httpx.post(
        f"{BASE}/mentor-allocations/check-timeouts",
        headers=org_h,
        timeout=30,
    ))
    check(r.status_code == 200, "Timeout check 200")
    check(isinstance(r.json(), list), "Returns a list")

    # ─── Test 14: Mentor with no matching skills ─────────────
    print("\n[POST /mentor-allocations] No matching mentors...")

    # Create a frontend-only issue when no available mentors have frontend skills
    r = h("POST /issues (frontend issue)", httpx.post(
        f"{BASE}/issues",
        headers=part_h,
        json={
            "description": "React component rendering issue with CSS Grid layout",
            "category": "frontend",
            "severity": 0.3,
            "is_blocking": False,
        },
        timeout=30,
    ))
    check(r.status_code == 201, "Frontend issue created (201)")
    issue3_id = r.json().get("id")

    r = h("POST /mentor-allocations (no match)", httpx.post(
        f"{BASE}/mentor-allocations",
        headers=part_h,
        json={"issue_id": issue3_id},
        timeout=30,
    ))
    # Should either find a match (fallback) or return 404
    check(r.status_code in (201, 404), f"No match result: {r.status_code}")

    # ─── Test 15: Final state check ──────────────────────────
    print("\n[final] Final allocation state...")

    r = h("GET /mentor-allocations (final)", httpx.get(
        f"{BASE}/mentor-allocations",
        headers=org_h,
        timeout=30,
    ))
    check(r.status_code == 200, "Final list 200")
    final_allocs = r.json()
    print(f"  Total allocations: {len(final_allocs)}")

    statuses = [a.get("status") for a in final_allocs]
    check("accepted" in statuses, "At least one accepted allocation")
    check("declined" in statuses, "At least one declined allocation")

    # ─── Summary ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
