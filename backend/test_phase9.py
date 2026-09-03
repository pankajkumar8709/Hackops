"""
Phase 9 smoke test - Proactive Reminders
Run with:
    python test_phase9.py
Requires backend to be running on :8000.
"""
import httpx
import json
import sys
import uuid
import asyncio
import hashlib
from datetime import datetime, timezone, timedelta

import asyncpg

BASE = "http://localhost:8000"
TIMEOUT = 30
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
    Seed Event (with deadline), Track, Team, Participant, Submission, and SubmissionRequirements.
    Returns (event_id, track_id, team_id, participant_id, jwt_token, deadline).
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
        team2_id = uuid.uuid4()
        participant2_id = uuid.uuid4()

        # Deadline 12 hours from now (should trigger reminder)
        deadline = datetime.now(timezone.utc) + timedelta(hours=12)

        # Create event with deadline
        await conn.execute(
            "INSERT INTO events (id, name, current_phase, timezone, deadline_at, created_at) "
            "VALUES ($1, $2, $3, $4, $5, NOW())",
            event_id, "Test Hackathon P9", "submissions", "UTC", deadline,
        )

        # Create track
        await conn.execute(
            "INSERT INTO tracks (id, name, eligibility_rules, event_id, created_at) "
            "VALUES ($1, $2, $3, $4, NOW())",
            track_id, "AI/ML Track", "Open to all", event_id,
        )

        # Create submission requirements (4 fields)
        for field in ["repo_url", "demo_url", "description", "readme_url"]:
            await conn.execute(
                "INSERT INTO submission_requirements (id, track_id, field_name, required) "
                "VALUES ($1, $2, $3, true)",
                uuid.uuid4(), track_id, field,
            )

        # Create team (incomplete submission)
        await conn.execute(
            "INSERT INTO teams (id, name, track_id, submission_status, readiness_pct, created_at) "
            "VALUES ($1, $2, $3, $4, $5, NOW())",
            team_id, "Team Incomplete", track_id, "not_submitted", 25.0,
        )

        # Create participant 1
        token1 = "test_token_p9_" + uuid.uuid4().hex[:16]
        token_hash1 = hashlib.sha256(token1.encode()).hexdigest()
        await conn.execute(
            "INSERT INTO participants (id, name, email, skills, track_pref, "
            "discord_handle, token_hash, team_id, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())",
            participant_id, "Test User P9a", f"p9a_{uuid.uuid4().hex[:8]}@example.com",
            ["python", "ml"], "ai", "test_user_a", token_hash1, team_id,
        )

        # Create team 2 (also incomplete, same track)
        await conn.execute(
            "INSERT INTO teams (id, name, track_id, submission_status, readiness_pct, created_at) "
            "VALUES ($1, $2, $3, $4, $5, NOW())",
            team2_id, "Team Incomplete 2", track_id, "not_submitted", 50.0,
        )

        # Create participant 2
        token2 = "test_token_p9_" + uuid.uuid4().hex[:16]
        token_hash2 = hashlib.sha256(token2.encode()).hexdigest()
        await conn.execute(
            "INSERT INTO participants (id, name, email, skills, track_pref, "
            "discord_handle, token_hash, team_id, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())",
            participant2_id, "Test User P9b", f"p9b_{uuid.uuid4().hex[:8]}@example.com",
            ["python"], "ai", "test_user_b", token_hash2, team2_id,
        )

        # Create incomplete submissions (only repo_url filled)
        sub_id1 = uuid.uuid4()
        await conn.execute(
            "INSERT INTO submissions (id, team_id, repo_url, completeness_pct, created_at, updated_at) "
            "VALUES ($1, $2, $3, $4, NOW(), NOW())",
            sub_id1, team_id, "https://github.com/team1/project", 25.0,
        )

        sub_id2 = uuid.uuid4()
        await conn.execute(
            "INSERT INTO submissions (id, team_id, repo_url, description, completeness_pct, created_at, updated_at) "
            "VALUES ($1, $2, $3, $4, $5, NOW(), NOW())",
            sub_id2, team2_id, "https://github.com/team2/project", "Our project", 50.0,
        )

        # Create JWTs
        from app.auth import create_jwt
        jwt1 = create_jwt({"sub": str(participant_id), "role": "participant"})
        jwt2 = create_jwt({"sub": str(participant2_id), "role": "participant"})

        return (event_id, track_id, team_id, participant_id, jwt1,
                team2_id, participant2_id, jwt2, deadline)
    finally:
        await conn.close()


def run_tests():
    global passed, failed

    print("=" * 60)
    print("Phase 9: Proactive Reminders - Smoke Test")
    print("=" * 60)

    # Load DB URL
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
    (event_id, track_id, team_id, participant_id, jwt1,
     team2_id, participant2_id, jwt2, deadline) = asyncio.run(seed_data(db_url))
    print(f"  event_id={event_id}")
    print(f"  team_id={team_id} (incomplete, 25%)")
    print(f"  team2_id={team2_id} (incomplete, 50%)")
    print(f"  deadline={deadline.isoformat()}")

    # Organizer login
    print("\n[setup] Organizer login...")
    r = httpx.post(f"{BASE}/auth/organizer/login", json={
        "username": "organizer",
        "password": "pulse_admin_2026",
    }, timeout=TIMEOUT)
    check(r.status_code == 200, "Organizer login 200")
    org_token = r.json()["access_token"]
    org_h = {"Authorization": f"Bearer {org_token}"}

    part1_h = {"Authorization": f"Bearer {jwt1}"}
    part2_h = {"Authorization": f"Bearer {jwt2}"}

    # ─── Test 1: GET /notifications (participant - should be empty) ────
    print("\n[GET /notifications] Participant views notifications (before sweep)...")

    r = h("GET /notifications (participant 1)", httpx.get(
        f"{BASE}/notifications",
        headers=part1_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /notifications 200")
    check(len(r.json()) == 0, "No notifications before sweep")

    # ─── Test 2: POST /reminders/sweep (dry run) ──────────────
    print("\n[POST /reminders/sweep] Dry run sweep...")

    r = h("POST /reminders/sweep (dry_run=true)", httpx.post(
        f"{BASE}/reminders/sweep",
        headers=org_h,
        json={"dry_run": True, "threshold_hours": 24, "completeness_threshold": 100.0},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "Sweep dry run 200")
    sweep = r.json()
    check(sweep.get("sweep_id") is not None, f"sweep_id={sweep.get('sweep_id')}")
    check(sweep.get("teams_checked", 0) >= 2, f"teams_checked={sweep.get('teams_checked')} (expected >= 2)")
    check(sweep.get("teams_needing_reminders", 0) >= 2, f"teams_needing={sweep.get('teams_needing_reminders')} (expected >= 2)")
    check(sweep.get("total_notifications_sent") == 0, "Dry run sends 0 notifications")

    # Check team results
    teams = sweep.get("teams", [])
    check(len(teams) >= 2, f"Sweep found {len(teams)} teams needing reminders")

    # Check that missing fields are identified
    team_result = next((t for t in teams if t["team_id"] == str(team_id)), None)
    if team_result:
        check(len(team_result.get("missing_fields", [])) >= 3,
              f"Team 1 missing fields: {team_result.get('missing_fields')}")
        check(team_result.get("completeness_pct") == 25.0,
              f"Team 1 completeness: {team_result.get('completeness_pct')}")

    team2_result = next((t for t in teams if t["team_id"] == str(team2_id)), None)
    if team2_result:
        check(len(team2_result.get("missing_fields", [])) >= 2,
              f"Team 2 missing fields: {team2_result.get('missing_fields')}")
        check(team2_result.get("completeness_pct") == 50.0,
              f"Team 2 completeness: {team2_result.get('completeness_pct')}")

    # ─── Test 3: Verify no notifications sent (dry run) ────────
    print("\n[GET /notifications] Still empty after dry run...")

    r = h("GET /notifications (participant 1 - still empty)", httpx.get(
        f"{BASE}/notifications",
        headers=part1_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /notifications 200")
    check(len(r.json()) == 0, "Still 0 notifications after dry run")

    # ─── Test 4: POST /reminders/sweep (real) ─────────────────
    print("\n[POST /reminders/sweep] Real sweep...")

    r = h("POST /reminders/sweep (real)", httpx.post(
        f"{BASE}/reminders/sweep",
        headers=org_h,
        json={"dry_run": False, "threshold_hours": 24, "completeness_threshold": 100.0},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "Real sweep 200")
    sweep = r.json()
    check(sweep.get("total_notifications_sent", 0) >= 2,
          f"Real sweep sent {sweep.get('total_notifications_sent')} notifications (expected >= 2)")

    # ─── Test 5: GET /notifications (participant 1 - should have notifications) ────
    print("\n[GET /notifications] Participant 1 sees notifications...")

    r = h("GET /notifications (participant 1)", httpx.get(
        f"{BASE}/notifications",
        headers=part1_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /notifications 200")
    notifs = r.json()
    check(len(notifs) >= 1, f"Participant 1 has {len(notifs)} notifications (expected >= 1)")

    # Check notification structure
    if notifs:
        n = notifs[0]
        check(n.get("recipient_id") == str(participant_id), "Notification sent to correct participant")
        check(n.get("team_id") == str(team_id), "Notification has correct team_id")
        check(n.get("reminder_type") == "deadline_reminder", f"reminder_type={n.get('reminder_type')}")
        check(n.get("content") is not None and len(n["content"]) > 10, "Notification has content")
        check(n.get("read") == False, "Notification is unread by default")
        check(n.get("trigger_reason") is not None, "Notification has trigger_reason")

    # ─── Test 6: GET /notifications (participant 2) ───────────
    print("\n[GET /notifications] Participant 2 sees notifications...")

    r = h("GET /notifications (participant 2)", httpx.get(
        f"{BASE}/notifications",
        headers=part2_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /notifications 200")
    notifs2 = r.json()
    check(len(notifs2) >= 1, f"Participant 2 has {len(notifs2)} notifications (expected >= 1)")

    # ─── Test 7: PATCH /notifications/{id}/read ───────────────
    print("\n[PATCH /notifications/{id}/read] Mark as read...")

    if notifs:
        notif_id = notifs[0]["id"]
        r = h("PATCH mark read", httpx.patch(
            f"{BASE}/notifications/{notif_id}/read",
            headers=part1_h,
            timeout=TIMEOUT,
        ))
        check(r.status_code == 200, "Mark read 200")
        check(r.json().get("read") == True, "Notification marked as read")

    # ─── Test 8: GET /notifications?unread_only=true ──────────
    print("\n[GET /notifications?unread_only=true] Filter unread...")

    r = h("GET /notifications (unread only)", httpx.get(
        f"{BASE}/notifications",
        headers=part1_h,
        params={"unread_only": True},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /notifications?unread_only=true 200")
    unread = r.json()
    check(all(n["read"] == False for n in unread), "All returned notifications are unread")

    # ─── Test 9: GET /notifications?reminder_type=deadline_reminder ───
    print("\n[GET /notifications?reminder_type=deadline_reminder] Filter by type...")

    r = h("GET /notifications (by type)", httpx.get(
        f"{BASE}/notifications",
        headers=part1_h,
        params={"reminder_type": "deadline_reminder"},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /notifications?reminder_type=... 200")
    check(len(r.json()) >= 1, "Found deadline_reminder notifications")

    # ─── Test 10: GET /reminders (organizer sweep history) ────
    print("\n[GET /reminders] Organizer sweep history...")

    r = h("GET /reminders (sweep history)", httpx.get(
        f"{BASE}/reminders",
        headers=org_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /reminders 200")
    check(len(r.json()) >= 2, f"Found {len(r.json())} sweep entries (expected >= 2)")

    # ─── Test 11: GET /notifications/all (organizer) ──────────
    print("\n[GET /notifications/all] Organizer sees all notifications...")

    r = h("GET /notifications/all (organizer)", httpx.get(
        f"{BASE}/notifications/all",
        headers=org_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /notifications/all 200")
    all_notifs = r.json()
    check(len(all_notifs) >= 2, f"Organizer sees {len(all_notifs)} notifications (expected >= 2)")

    # ─── Test 12: GET /notifications/all?reminder_type=deadline_reminder ───
    print("\n[GET /notifications/all?reminder_type=...] Filter all by type...")

    r = h("GET /notifications/all (by type)", httpx.get(
        f"{BASE}/notifications/all",
        headers=org_h,
        params={"reminder_type": "deadline_reminder"},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /notifications/all?reminder_type=... 200")
    check(len(r.json()) >= 2, "Found deadline_reminder notifications in all")

    # ─── Test 13: Sweep with tight threshold (should not trigger) ───
    print("\n[POST /reminders/sweep] Tight threshold (should not trigger)...")

    r = h("POST /reminders/sweep (tight threshold)", httpx.post(
        f"{BASE}/reminders/sweep",
        headers=org_h,
        json={"dry_run": True, "threshold_hours": 0.5, "completeness_threshold": 100.0},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "Sweep with 0.5h threshold 200")
    # With 0.5h threshold and 12h remaining, no teams should need reminders
    check(r.json().get("teams_needing_reminders", 0) == 0,
          f"0.5h threshold: {r.json().get('teams_needing_reminders')} teams (expected 0)")

    # ─── Test 14: Authorization tests ─────────────────────────
    print("\n[auth] Authorization tests...")

    r = h("POST /reminders/sweep (no auth)", httpx.post(
        f"{BASE}/reminders/sweep",
        json={"dry_run": True},
        timeout=TIMEOUT,
    ))
    check(r.status_code in (401, 403), "POST /reminders/sweep without auth returns 401/403")

    r = h("GET /reminders (no auth)", httpx.get(
        f"{BASE}/reminders",
        timeout=TIMEOUT,
    ))
    check(r.status_code in (401, 403), "GET /reminders without auth returns 401/403")

    r = h("GET /notifications (no auth)", httpx.get(
        f"{BASE}/notifications",
        timeout=TIMEOUT,
    ))
    check(r.status_code in (401, 403), "GET /notifications without auth returns 401/403")

    # ─── Test 15: PATCH mark read by wrong participant ────────
    print("\n[PATCH /notifications/{id}/read] Wrong participant...")

    if notifs2:
        notif_id2 = notifs2[0]["id"]
        r = h("PATCH mark read (wrong participant)", httpx.patch(
            f"{BASE}/notifications/{notif_id2}/read",
            headers=part1_h,
            timeout=TIMEOUT,
        ))
        check(r.status_code == 403, "Wrong participant gets 403")

    # ─── Test 16: PATCH mark read non-existent ────────────────
    print("\n[PATCH /notifications/{id}/read] Non-existent...")

    fake_notif_id = str(uuid.uuid4())
    r = h("PATCH mark read (non-existent)", httpx.patch(
        f"{BASE}/notifications/{fake_notif_id}/read",
        headers=part1_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 404, "Non-existent notification gets 404")

    # ─── Test 17: Sweep with specific event_id ────────────────
    print("\n[POST /reminders/sweep] Specific event_id...")

    r = h("POST /reminders/sweep (event_id)", httpx.post(
        f"{BASE}/reminders/sweep",
        headers=org_h,
        json={"dry_run": True, "event_id": str(event_id), "threshold_hours": 24},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "Sweep with event_id 200")
    check(r.json().get("teams_checked", 0) >= 2,
          f"event_id sweep checked {r.json().get('teams_checked')} teams (expected >= 2)")

    # ─── Test 18: Sweep with completeness threshold (only very incomplete) ───
    print("\n[POST /reminders/sweep] Strict completeness threshold...")

    r = h("POST /reminders/sweep (strict)", httpx.post(
        f"{BASE}/reminders/sweep",
        headers=org_h,
        json={"dry_run": True, "threshold_hours": 24, "completeness_threshold": 30.0},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "Strict threshold sweep 200")
    # Only team1 (25%) should trigger, not team2 (50%)
    teams_strict = r.json().get("teams", [])
    check(len(teams_strict) >= 1, f"Strict threshold: {len(teams_strict)} teams (expected >= 1)")
    team_strict_ids = [t["team_id"] for t in teams_strict]
    check(str(team_id) in team_strict_ids, "Team 1 (25%) in strict results")
    check(str(team2_id) not in team_strict_ids, "Team 2 (50%) NOT in strict results")

    # ─── Summary ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
