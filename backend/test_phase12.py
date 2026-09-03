"""
Phase 12 smoke test - Discord Integration & Notification Delivery
Run with:
    python test_phase12.py
Requires backend to be running on :8000.
"""
import httpx
import json
import sys
import uuid
import asyncio
import hashlib

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
    Seed Event, Track, Team, Participants, and Mentors.
    Returns dict with IDs and JWTs.
    """
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if "?" in sync_url:
        sync_url = sync_url.split("?")[0]

    conn = await asyncpg.connect(sync_url)
    try:
        event_id = uuid.uuid4()
        track_id = uuid.uuid4()
        team_id = uuid.uuid4()
        member1_id = uuid.uuid4()
        member2_id = uuid.uuid4()
        mentor_id = uuid.uuid4()

        # Event
        await conn.execute(
            "INSERT INTO events (id, name, current_phase, timezone, created_at) "
            "VALUES ($1, $2, $3, $4, NOW())",
            event_id, "Test Hackathon P12", "submissions", "UTC",
        )

        # Track
        await conn.execute(
            "INSERT INTO tracks (id, name, eligibility_rules, event_id, created_at) "
            "VALUES ($1, $2, $3, $4, NOW())",
            track_id, "AI/ML Track", "python, machine learning", event_id,
        )

        # Submission requirements
        for field in ["repo_url", "demo_url", "description", "readme_url"]:
            await conn.execute(
                "INSERT INTO submission_requirements (id, track_id, field_name, required) "
                "VALUES ($1, $2, $3, true)",
                uuid.uuid4(), track_id, field,
            )

        # Team
        await conn.execute(
            "INSERT INTO teams (id, name, track_id, submission_status, readiness_pct, created_at) "
            "VALUES ($1, $2, $3, $4, $5, NOW())",
            team_id, "Team Discord", track_id, "not_submitted", 50.0,
        )

        # Member 1 (has discord_handle)
        token1 = "test_token_p12a_" + uuid.uuid4().hex[:16]
        hash1 = hashlib.sha256(token1.encode()).hexdigest()
        await conn.execute(
            "INSERT INTO participants (id, name, email, skills, track_pref, "
            "discord_handle, token_hash, team_id, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())",
            member1_id, "Discord User A", f"discord_a_{uuid.uuid4().hex[:8]}@example.com",
            ["python"], "ai", "discord_user_a", hash1, team_id,
        )

        # Member 2 (no discord_handle)
        token2 = "test_token_p12b_" + uuid.uuid4().hex[:16]
        hash2 = hashlib.sha256(token2.encode()).hexdigest()
        await conn.execute(
            "INSERT INTO participants (id, name, email, skills, track_pref, "
            "discord_handle, token_hash, team_id, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())",
            member2_id, "Discord User B", f"discord_b_{uuid.uuid4().hex[:8]}@example.com",
            ["ml"], "ai", None, hash2, team_id,
        )

        # Mentor
        await conn.execute(
            "INSERT INTO mentors (id, name, skills, availability_status, "
            "discord_handle, created_at) "
            "VALUES ($1, $2, $3, $4, $5, NOW())",
            mentor_id, "Discord Mentor", ["python", "deployment"],
            "available", "discord_mentor",
        )

        from app.auth import create_jwt
        jwt1 = create_jwt({"sub": str(member1_id), "role": "participant"})
        jwt2 = create_jwt({"sub": str(member2_id), "role": "participant"})

        return {
            "event_id": event_id,
            "track_id": track_id,
            "team_id": team_id,
            "member1_id": member1_id,
            "member2_id": member2_id,
            "mentor_id": mentor_id,
            "jwt1": jwt1,
            "jwt2": jwt2,
        }
    finally:
        await conn.close()


def run_tests():
    global passed, failed

    print("=" * 60)
    print("Phase 12: Discord Integration & Notification Delivery - Smoke Test")
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
    data = asyncio.run(seed_data(db_url))
    print(f"  team_id={data['team_id']}")
    print(f"  member1 (has discord): {data['member1_id']}")
    print(f"  member2 (no discord): {data['member2_id']}")

    # Organizer login
    print("\n[setup] Organizer login...")
    r = httpx.post(f"{BASE}/auth/organizer/login", json={
        "username": "organizer",
        "password": "pulse_admin_2026",
    }, timeout=TIMEOUT)
    check(r.status_code == 200, "Organizer login 200")
    org_token = r.json()["access_token"]
    org_h = {"Authorization": f"Bearer {org_token}"}

    part1_h = {"Authorization": f"Bearer {data['jwt1']}"}

    # ═══════════════════════════════════════════════════════════
    # Channel Configuration
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 50)
    print("Channel Configuration")
    print("=" * 50)

    # Test 1: GET /notifications/channels
    print("\n[GET /notifications/channels] Channel config...")

    r = h("GET /notifications/channels", httpx.get(
        f"{BASE}/notifications/channels",
        headers=org_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /channels 200")
    channels = r.json()
    check("in_app" in channels.get("active_channels", []), "in_app channel active")
    check(channels.get("default_channel") == "in_app", "Default channel is in_app")
    # Discord may or may not be enabled (depends on DISCORD_TOKEN in .env)
    check(isinstance(channels.get("discord_enabled"), bool), "discord_enabled is boolean")

    # ═══════════════════════════════════════════════════════════
    # Send Notification (auto channel)
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 50)
    print("Send Notification (auto channel)")
    print("=" * 50)

    # Test 2: POST /notifications/send (auto channel, has discord_handle)
    print("\n[POST /notifications/send] Auto channel (has discord)...")

    r = h("POST /notifications/send (auto, discord user)", httpx.post(
        f"{BASE}/notifications/send",
        headers=org_h,
        json={
            "recipient_id": str(data["member1_id"]),
            "content": "Your submission is at 50% completeness. Missing: demo_url, description.",
            "channel": "auto",
            "trigger_reason": "test:phase12",
            "reminder_type": "submission_reminder",
        },
        timeout=TIMEOUT,
    ))
    check(r.status_code == 201, "Send notification 201")
    check(r.json().get("delivered") == True, "Notification delivered")
    notif1_channel = r.json().get("channel")
    check(notif1_channel in ("discord", "in_app"), f"Channel: {notif1_channel}")
    notif1_id = r.json().get("notification_id")

    # Test 3: POST /notifications/send (auto channel, no discord_handle)
    print("\n[POST /notifications/send] Auto channel (no discord)...")

    r = h("POST /notifications/send (auto, no discord)", httpx.post(
        f"{BASE}/notifications/send",
        headers=org_h,
        json={
            "recipient_id": str(data["member2_id"]),
            "content": "Your team has a new mentor allocation proposal.",
            "channel": "auto",
            "trigger_reason": "test:phase12",
            "reminder_type": "mentor_proposal",
        },
        timeout=TIMEOUT,
    ))
    check(r.status_code == 201, "Send notification 201")
    check(r.json().get("delivered") == True, "Notification delivered")
    check(r.json().get("channel") == "in_app", "No discord -> in_app channel")

    # Test 4: POST /notifications/send (explicit discord channel)
    print("\n[POST /notifications/send] Explicit discord channel...")

    r = h("POST /notifications/send (explicit discord)", httpx.post(
        f"{BASE}/notifications/send",
        headers=org_h,
        json={
            "recipient_id": str(data["member1_id"]),
            "content": "Test explicit discord channel routing.",
            "channel": "discord",
            "trigger_reason": "test:phase12:explicit",
        },
        timeout=TIMEOUT,
    ))
    check(r.status_code == 201, "Send explicit discord 201")
    check(r.json().get("channel") == "discord", "Explicit discord channel")

    # Test 5: POST /notifications/send (explicit in_app)
    print("\n[POST /notifications/send] Explicit in_app channel...")

    r = h("POST /notifications/send (explicit in_app)", httpx.post(
        f"{BASE}/notifications/send",
        headers=org_h,
        json={
            "recipient_id": str(data["member1_id"]),
            "content": "Test explicit in_app channel routing.",
            "channel": "in_app",
            "trigger_reason": "test:phase12:explicit",
        },
        timeout=TIMEOUT,
    ))
    check(r.status_code == 201, "Send explicit in_app 201")
    check(r.json().get("channel") == "in_app", "Explicit in_app channel")

    # ═══════════════════════════════════════════════════════════
    # Pending Notifications (bot polling)
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 50)
    print("Pending Notifications (bot polling)")
    print("=" * 50)

    # Test 6: GET /notifications/pending
    print("\n[GET /notifications/pending] All pending...")

    r = h("GET /notifications/pending", httpx.get(
        f"{BASE}/notifications/pending",
        headers=org_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /pending 200")
    pending = r.json()
    check(len(pending) >= 3, f"Found {len(pending)} pending (expected >= 3)")

    # Check structure
    if pending:
        p = pending[0]
        check(p.get("id") is not None, "Pending has id")
        check(p.get("recipient_id") is not None, "Pending has recipient_id")
        check(p.get("content") is not None, "Pending has content")
        check(p.get("channel") is not None, "Pending has channel")
        check(p.get("recipient_name") is not None, "Pending has recipient_name")
        check(p.get("read") == False, "Pending is unread")

    # Test 7: GET /notifications/pending?channel=discord
    print("\n[GET /notifications/pending?channel=discord] Discord only...")

    r = h("GET /notifications/pending (discord)", httpx.get(
        f"{BASE}/notifications/pending",
        headers=org_h,
        params={"channel": "discord"},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /pending?channel=discord 200")
    discord_pending = r.json()
    check(all(p.get("channel") == "discord" for p in discord_pending),
          f"All filtered are discord: {[p.get('channel') for p in discord_pending]}")

    # Test 8: GET /notifications/pending?channel=in_app
    print("\n[GET /notifications/pending?channel=in_app] In-app only...")

    r = h("GET /notifications/pending (in_app)", httpx.get(
        f"{BASE}/notifications/pending",
        headers=org_h,
        params={"channel": "in_app"},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /pending?channel=in_app 200")
    inapp_pending = r.json()
    check(all(p.get("channel") == "in_app" for p in inapp_pending),
          "All filtered are in_app")

    # ═══════════════════════════════════════════════════════════
    # Mark as read (simulates bot delivery)
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 50)
    print("Mark as Read (simulates bot delivery)")
    print("=" * 50)

    # Test 9: PATCH /notifications/{id}/read
    if notif1_id:
        print("\n[PATCH /notifications/{id}/read] Mark delivered...")

        # Use participant 1's JWT to mark their own notification as read
        r = h("PATCH mark read", httpx.patch(
            f"{BASE}/notifications/{notif1_id}/read",
            headers=part1_h,
            timeout=TIMEOUT,
        ))
        check(r.status_code == 200, "Mark read 200")
        check(r.json().get("read") == True, "Marked as read")

    # ═══════════════════════════════════════════════════════════
    # Integration with Orchestrator
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 50)
    print("Integration: Orchestrator creates notifications")
    print("=" * 50)

    # Test 10: Run submission audit orchestrator (creates notifications)
    print("\n[POST /orchestrator/run] Submission audit (creates notifs)...")

    r = h("POST /orchestrator/run (submission_audit)", httpx.post(
        f"{BASE}/orchestrator/run",
        headers=org_h,
        json={
            "trigger_type": "submission_audit",
            "context": {"team_id": str(data["team_id"])},
        },
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "Orchestrator run 200")
    check(r.json().get("logged") == True, "Action logged")
    notifs_sent = r.json().get("act", {}).get("notifications_sent", 0)
    check(notifs_sent >= 1, f"Notifications sent by orchestrator: {notifs_sent}")

    # Test 11: Check pending count grew
    print("\n[GET /notifications/pending] After orchestrator...")

    r = h("GET /notifications/pending (after orchestrator)", httpx.get(
        f"{BASE}/notifications/pending",
        headers=org_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /pending 200")
    new_pending = r.json()
    check(len(new_pending) >= len(pending),
          f"Pending grew: {len(pending)} -> {len(new_pending)}")

    # ═══════════════════════════════════════════════════════════
    # Error Handling
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 50)
    print("Error Handling")
    print("=" * 50)

    # Test 12: Send to non-existent recipient
    print("\n[POST /notifications/send] Non-existent recipient...")

    r = h("POST /notifications/send (fake recipient)", httpx.post(
        f"{BASE}/notifications/send",
        headers=org_h,
        json={
            "recipient_id": str(uuid.uuid4()),
            "content": "Test",
            "channel": "in_app",
        },
        timeout=TIMEOUT,
    ))
    check(r.status_code == 404, "Fake recipient returns 404")

    # Test 13: No auth
    print("\n[POST /notifications/send] No auth...")

    r = h("POST /notifications/send (no auth)", httpx.post(
        f"{BASE}/notifications/send",
        json={
            "recipient_id": str(data["member1_id"]),
            "content": "Test",
        },
        timeout=TIMEOUT,
    ))
    check(r.status_code in (401, 403), "No auth returns 401/403")

    # Test 14: GET /notifications/pending no auth
    print("\n[GET /notifications/pending] No auth...")

    r = h("GET /notifications/pending (no auth)", httpx.get(
        f"{BASE}/notifications/pending",
        timeout=TIMEOUT,
    ))
    check(r.status_code in (401, 403), "No auth returns 401/403")

    # ═══════════════════════════════════════════════════════════
    # Bot Module Verification
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 50)
    print("Bot Module Verification")
    print("=" * 50)

    # Test 15: Bot config loads
    print("\n[bot] Bot config loads...")

    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from bot.config import config as bot_config
    check(bot_config.BACKEND_URL == "http://localhost:8000", "Backend URL correct")
    check(bot_config.BOT_NAME == "Pulse", "Bot name correct")
    check(bot_config.COMMAND_PREFIX == "!", "Command prefix correct")

    # Test 16: Bot module imports
    print("\n[bot] Bot module imports...")

    from bot.pulse_bot import bot as discord_bot
    check(discord_bot is not None, "Discord bot object created")
    check(len(discord_bot.commands) >= 5, f"Bot has {len(discord_bot.commands)} commands (expected >= 5)")

    # List commands
    cmd_names = [c.name for c in discord_bot.commands]
    check("help" in cmd_names, "Has !help command")
    check("ask" in cmd_names, "Has !ask command")
    check("issue" in cmd_names, "Has !issue command")
    check("status" in cmd_names, "Has !status command")
    check("escalations" in cmd_names, "Has !escalations command")

    # ═══════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
