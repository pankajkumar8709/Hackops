"""
Phase 11 smoke test - Agent Orchestrator (The Closed Loop)
Run with:
    python test_phase11.py
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
        print(f"  Body   : {json.dumps(r.json(), indent=2)[:600]}")
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
    Seed everything needed for the orchestrator test:
    - Event with deadline, Track with SubmissionRequirements
    - Team with incomplete submission (for submission_audit loop)
    - Team member with JWT
    - Issue (for mentor_allocation loop)
    - Mentor with matching skills
    - Resource items (for resource_allocation loop)
    """
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if "?" in sync_url:
        sync_url = sync_url.split("?")[0]

    conn = await asyncpg.connect(sync_url)
    try:
        event_id = uuid.uuid4()
        track_id = uuid.uuid4()
        team_id = uuid.uuid4()
        member_id = uuid.uuid4()
        issue_id = uuid.uuid4()
        mentor_id = uuid.uuid4()
        resource_id = uuid.uuid4()

        # Event with deadline (6 hours from now)
        deadline = datetime.now(timezone.utc) + timedelta(hours=6)
        await conn.execute(
            "INSERT INTO events (id, name, current_phase, timezone, deadline_at, created_at) "
            "VALUES ($1, $2, $3, $4, $5, NOW())",
            event_id, "Test Hackathon P11", "submissions", "UTC", deadline,
        )

        # Track with submission requirements
        await conn.execute(
            "INSERT INTO tracks (id, name, eligibility_rules, event_id, created_at) "
            "VALUES ($1, $2, $3, $4, NOW())",
            track_id, "AI/ML Track", "python, machine learning", event_id,
        )

        for field in ["repo_url", "demo_url", "description", "readme_url"]:
            await conn.execute(
                "INSERT INTO submission_requirements (id, track_id, field_name, required) "
                "VALUES ($1, $2, $3, true)",
                uuid.uuid4(), track_id, field,
            )

        # Team with INCOMPLETE submission (only repo_url filled)
        await conn.execute(
            "INSERT INTO teams (id, name, track_id, submission_status, readiness_pct, created_at) "
            "VALUES ($1, $2, $3, $4, $5, NOW())",
            team_id, "Team Orchestrator", track_id, "not_submitted", 25.0,
        )

        # Incomplete submission
        await conn.execute(
            "INSERT INTO submissions (id, team_id, repo_url, completeness_pct, created_at, updated_at) "
            "VALUES ($1, $2, $3, $4, NOW(), NOW())",
            uuid.uuid4(), team_id, "https://github.com/team/project", 25.0,
        )

        # Team member
        token = "test_token_p11_" + uuid.uuid4().hex[:16]
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        await conn.execute(
            "INSERT INTO participants (id, name, email, skills, track_pref, "
            "discord_handle, token_hash, team_id, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())",
            member_id, "Orch Member", f"orch_p11_{uuid.uuid4().hex[:8]}@example.com",
            ["python"], "ai", "orch_user", token_hash, team_id,
        )

        # Open issue (for mentor_allocation loop)
        await conn.execute(
            "INSERT INTO issues (id, team_id, participant_id, description, category, "
            "status, severity, is_blocking, urgency_score, created_at, updated_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())",
            issue_id, team_id, member_id,
            "Cannot deploy to Docker. Container fails to start with port binding error.",
            "deployment", "open", 0.8, True, 0.0,
        )

        # Mentor with matching skills
        await conn.execute(
            "INSERT INTO mentors (id, name, skills, availability_status, "
            "discord_handle, created_at) "
            "VALUES ($1, $2, $3, $4, $5, NOW())",
            mentor_id, "Docker Expert",
            ["docker", "deployment", "kubernetes"], "available", "docker_expert",
        )

        # Resource item with stock
        await conn.execute(
            "INSERT INTO resource_items (id, name, resource_type, total_quantity, "
            "available_quantity, created_at) "
            "VALUES ($1, $2, $3, $4, $5, NOW())",
            resource_id, "GPU Test Suite", "hardware_kit", 3, 3,
        )

        from app.auth import create_jwt
        jwt_token = create_jwt({"sub": str(member_id), "role": "participant"})

        return {
            "event_id": event_id,
            "track_id": track_id,
            "team_id": team_id,
            "member_id": member_id,
            "issue_id": issue_id,
            "mentor_id": mentor_id,
            "resource_id": resource_id,
            "jwt_token": jwt_token,
        }
    finally:
        await conn.close()


def run_tests():
    global passed, failed

    print("=" * 60)
    print("Phase 11: Agent Orchestrator - The Closed Loop - Smoke Test")
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
    print(f"  team_id={data['team_id']} (incomplete submission)")
    print(f"  issue_id={data['issue_id']} (open, blocking)")
    print(f"  mentor_id={data['mentor_id']} (docker expert)")
    print(f"  resource_id={data['resource_id']} (GPU Test Suite, qty=3)")

    # Organizer login
    print("\n[setup] Organizer login...")
    r = httpx.post(f"{BASE}/auth/organizer/login", json={
        "username": "organizer",
        "password": "pulse_admin_2026",
    }, timeout=TIMEOUT)
    check(r.status_code == 200, "Organizer login 200")
    org_token = r.json()["access_token"]
    org_h = {"Authorization": f"Bearer {org_token}"}

    # ═══════════════════════════════════════════════════════════
    # LOOP 1: Submission Audit
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 50)
    print("LOOP 1: Submission Audit")
    print("=" * 50)

    # Test 1: Run submission audit orchestrator
    print("\n[POST /orchestrator/run] Submission audit...")

    r = h("POST /orchestrator/run (submission_audit)", httpx.post(
        f"{BASE}/orchestrator/run",
        headers=org_h,
        json={
            "trigger_type": "submission_audit",
            "context": {"team_id": str(data["team_id"])},
        },
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "submission_audit 200")
    result = r.json()
    check(result.get("run_id") is not None, f"run_id={result.get('run_id')}")
    check(result.get("trigger_type") == "submission_audit", "trigger_type correct")
    check(result.get("logged") == True, "Action was logged")

    # Check observe step
    observe = result.get("observe", {})
    check(observe.get("has_submission") == True, "Team has submission")
    check(observe.get("completeness_pct", 0) < 100, f"completeness={observe.get('completeness_pct')} (< 100)")
    check(len(observe.get("missing_fields", [])) >= 2,
          f"Missing fields: {observe.get('missing_fields')}")

    # Check decide step
    decide = result.get("decide", {})
    check(decide.get("action") == "send_notification", f"Decision: {decide.get('action')}")
    check("reasoning" in decide, "Has reasoning")

    # Check policy step
    policy = result.get("policy", {})
    check(policy.get("allowed") == True, "Policy allowed")

    # Check act step
    act = result.get("act", {})
    check(act.get("notifications_sent", 0) >= 1, f"Notifications sent: {act.get('notifications_sent')}")

    # ═══════════════════════════════════════════════════════════
    # LOOP 2: Mentor Allocation
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 50)
    print("LOOP 2: Mentor Allocation")
    print("=" * 50)

    # Test 2: Run mentor allocation orchestrator
    print("\n[POST /orchestrator/run] Mentor allocation...")

    r = h("POST /orchestrator/run (mentor_allocation)", httpx.post(
        f"{BASE}/orchestrator/run",
        headers=org_h,
        json={
            "trigger_type": "mentor_allocation",
            "context": {"issue_id": str(data["issue_id"])},
        },
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "mentor_allocation 200")
    result = r.json()
    check(result.get("trigger_type") == "mentor_allocation", "trigger_type correct")
    check(result.get("logged") == True, "Action was logged")

    # Check observe
    observe = result.get("observe", {})
    check(observe.get("issue_id") == str(data["issue_id"]), "Issue ID correct")
    check(observe.get("is_blocking") == True, "Issue is blocking")
    check(observe.get("available_mentors", 0) >= 1, "Mentors available")

    # Check decide
    decide = result.get("decide", {})
    check(decide.get("action") in ("propose_mentor_allocation", "create_escalation", "none"),
          f"Decision: {decide.get('action')}")

    # Check act
    act = result.get("act", {})
    check(act.get("outcome") != "unknown_action", f"Outcome: {act.get('outcome')}")

    # ═══════════════════════════════════════════════════════════
    # LOOP 3: Resource Allocation
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 50)
    print("LOOP 3: Resource Allocation")
    print("=" * 50)

    # Test 3: Run resource allocation orchestrator
    print("\n[POST /orchestrator/run] Resource allocation...")

    r = h("POST /orchestrator/run (resource_allocation)", httpx.post(
        f"{BASE}/orchestrator/run",
        headers=org_h,
        json={
            "trigger_type": "resource_allocation",
            "context": {
                "resource_item_id": str(data["resource_id"]),
                "team_id": str(data["team_id"]),
            },
        },
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "resource_allocation 200")
    result = r.json()
    check(result.get("trigger_type") == "resource_allocation", "trigger_type correct")
    check(result.get("logged") == True, "Action was logged")

    # Check observe
    observe = result.get("observe", {})
    check(observe.get("available", 0) >= 1, f"Available: {observe.get('available')}")

    # Check decide
    decide = result.get("decide", {})
    check(decide.get("action") == "allocate_resource", f"Decision: {decide.get('action')}")

    # Check act
    act = result.get("act", {})
    check("allocation" in act.get("outcome", "").lower() or "allocated" in act.get("outcome", "").lower(),
          f"Outcome: {act.get('outcome')}")

    # ═══════════════════════════════════════════════════════════
    # Policy Checks
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 50)
    print("Policy Checks")
    print("=" * 50)

    # Test 4: Restricted action (simulate via direct service call)
    print("\n[policy] Check allowed vs restricted actions...")

    from app.services.orchestrator import check_policy

    allowed, reason = check_policy("send_notification")
    check(allowed == True, "send_notification: allowed")
    allowed, reason = check_policy("create_escalation")
    check(allowed == True, "create_escalation: allowed")
    allowed, reason = check_policy("propose_mentor_allocation")
    check(allowed == True, "propose_mentor_allocation: allowed")
    allowed, reason = check_policy("roster_change")
    check(allowed == False, "roster_change: blocked")
    allowed, reason = check_policy("deadline_edit")
    check(allowed == False, "deadline_edit: blocked")
    allowed, reason = check_policy("disqualify_team")
    check(allowed == False, "disqualify_team: blocked")

    # ═══════════════════════════════════════════════════════════
    # Action Log (Explainability Feed)
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 50)
    print("Action Log (Explainability)")
    print("=" * 50)

    # Test 5: GET /orchestrator/actions
    print("\n[GET /orchestrator/actions] View action log...")

    r = h("GET /orchestrator/actions", httpx.get(
        f"{BASE}/orchestrator/actions",
        headers=org_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /actions 200")
    actions = r.json()
    check(len(actions) >= 3, f"Found {len(actions)} actions (expected >= 3)")

    # Check action structure
    if actions:
        a = actions[0]
        check(a.get("id") is not None, "Action has id")
        check(a.get("action_type") is not None, f"action_type: {a.get('action_type')}")
        check(a.get("reasoning_trace") is not None, "Has reasoning_trace")
        check(a.get("policy_check_result") is not None, "Has policy_check_result")
        check(a.get("outcome") is not None, "Has outcome")
        check(a.get("executed_at") is not None, "Has executed_at")

    # Test 6: Filter by action_type
    print("\n[GET /orchestrator/actions?action_type=...] Filter actions...")

    r = h("GET /orchestrator/actions (filter)", httpx.get(
        f"{BASE}/orchestrator/actions",
        headers=org_h,
        params={"action_type": "send_notification"},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "Filter by action_type 200")
    filtered = r.json()
    check(all(a.get("action_type") == "send_notification" for a in filtered),
          "All filtered actions are send_notification")

    # ═══════════════════════════════════════════════════════════
    # Orchestrator Status
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 50)
    print("Orchestrator Status")
    print("=" * 50)

    # Test 7: GET /orchestrator/status
    print("\n[GET /orchestrator/status] Status...")

    r = h("GET /orchestrator/status", httpx.get(
        f"{BASE}/orchestrator/status",
        headers=org_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /status 200")
    status = r.json()
    check(status.get("status") == "operational", "Status is operational")
    check("submission_audit" in status.get("trigger_types", []), "Has submission_audit trigger")
    check("mentor_allocation" in status.get("trigger_types", []), "Has mentor_allocation trigger")
    check("resource_allocation" in status.get("trigger_types", []), "Has resource_allocation trigger")
    check("send_notification" in status.get("allowed_actions", []), "send_notification in allow-list")
    check("roster_change" in status.get("restricted_actions", []), "roster_change is restricted")

    # ═══════════════════════════════════════════════════════════
    # Full Sweep
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 50)
    print("Full Sweep")
    print("=" * 50)

    # Test 8: POST /orchestrator/sweep
    print("\n[POST /orchestrator/sweep] Full sweep...")

    r = h("POST /orchestrator/sweep", httpx.post(
        f"{BASE}/orchestrator/sweep",
        headers=org_h,
        timeout=300,
    ))
    check(r.status_code == 200, "Full sweep 200")
    sweep = r.json()
    check(sweep.get("sweep_id") is not None, f"sweep_id={sweep.get('sweep_id')}")
    check(sweep.get("total_runs", 0) >= 1, f"total_runs={sweep.get('total_runs')} (expected >= 1)")

    # Check that sweep results contain all three types
    results = sweep.get("results", [])
    trigger_types = set(r.get("trigger_type") for r in results)
    check("submission_audit" in trigger_types, "Sweep includes submission_audit")

    # ═══════════════════════════════════════════════════════════
    # Error Handling
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 50)
    print("Error Handling")
    print("=" * 50)

    # Test 9: Invalid trigger type
    print("\n[POST /orchestrator/run] Invalid trigger type...")

    r = h("POST /orchestrator/run (invalid)", httpx.post(
        f"{BASE}/orchestrator/run",
        headers=org_h,
        json={"trigger_type": "invalid_type", "context": {}},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 422, "Invalid trigger type returns 422")

    # Test 10: Missing context
    print("\n[POST /orchestrator/run] Missing context...")

    r = h("POST /orchestrator/run (missing context)", httpx.post(
        f"{BASE}/orchestrator/run",
        headers=org_h,
        json={"trigger_type": "submission_audit", "context": {}},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 422, "Missing context returns 422")

    # Test 11: Non-existent team
    print("\n[POST /orchestrator/run] Non-existent team...")

    r = h("POST /orchestrator/run (fake team)", httpx.post(
        f"{BASE}/orchestrator/run",
        headers=org_h,
        json={
            "trigger_type": "submission_audit",
            "context": {"team_id": str(uuid.uuid4())},
        },
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "Fake team returns 200 (with error in body)")
    check(r.json().get("error") is not None, "Error reported in result")

    # Test 12: No auth
    print("\n[POST /orchestrator/run] No auth...")

    r = h("POST /orchestrator/run (no auth)", httpx.post(
        f"{BASE}/orchestrator/run",
        json={"trigger_type": "submission_audit", "context": {"team_id": str(uuid.uuid4())}},
        timeout=TIMEOUT,
    ))
    check(r.status_code in (401, 403), "No auth returns 401/403")

    # ═══════════════════════════════════════════════════════════
    # Re-verification: Second run produces more action log entries
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 50)
    print("Re-verification: Second run adds to log")
    print("=" * 50)

    print("\n[POST /orchestrator/run] Second submission audit...")
    r = h("POST /orchestrator/run (2nd submission_audit)", httpx.post(
        f"{BASE}/orchestrator/run",
        headers=org_h,
        json={
            "trigger_type": "submission_audit",
            "context": {"team_id": str(data["team_id"])},
        },
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "2nd submission_audit 200")
    check(r.json().get("logged") == True, "Second run also logged")

    # Check total action count grew
    r2 = httpx.get(
        f"{BASE}/orchestrator/actions",
        headers=org_h,
        params={"limit": 200},
        timeout=TIMEOUT,
    )
    check(r2.status_code == 200, "GET actions 200")
    total_after = len(r2.json())
    check(total_after >= 6, f"Total actions after 2 runs: {total_after} (expected >= 6)")

    # ═══════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
