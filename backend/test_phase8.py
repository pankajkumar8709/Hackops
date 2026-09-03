"""
Phase 8 smoke test - Resource Allocation & Tracking
Run with:
    python test_phase8.py
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
TIMEOUT = 30  # increased for remote Neon DB
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
    Seed Event, Track, Team, Participant, and ResourceItems directly in the DB.
    Returns (event_id, track_id, team_id, participant_id, resource_item_api, resource_item_hw, jwt_token).
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
        resource_api = uuid.uuid4()
        resource_hw = uuid.uuid4()

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
        participant_token = "test_token_p8_" + uuid.uuid4().hex[:16]
        token_hash = hashlib.sha256(participant_token.encode()).hexdigest()

        await conn.execute(
            "INSERT INTO participants (id, name, email, skills, track_pref, "
            "discord_handle, token_hash, team_id, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())",
            participant_id, "Test User P8", f"test_p8_{uuid.uuid4().hex[:8]}@example.com",
            ["python", "ml"], "ai", "test_user", token_hash, team_id,
        )

        # Create resource items
        await conn.execute(
            "INSERT INTO resource_items (id, name, resource_type, total_quantity, available_quantity, created_at) "
            "VALUES ($1, $2, $3, $4, $5, NOW())",
            resource_api, "Groq API Key Pool", "api_key", 5, 5,
        )
        await conn.execute(
            "INSERT INTO resource_items (id, name, resource_type, total_quantity, available_quantity, created_at) "
            "VALUES ($1, $2, $3, $4, $5, NOW())",
            resource_hw, "GPU Hardware Kit", "hardware_kit", 2, 2,
        )

        # Create a JWT for the participant
        from app.auth import create_jwt
        jwt_token = create_jwt({"sub": str(participant_id), "role": "participant"})

        return (event_id, track_id, team_id, participant_id,
                resource_api, resource_hw, jwt_token)
    finally:
        await conn.close()


def run_tests():
    global passed, failed

    print("=" * 60)
    print("Phase 8: Resource Allocation & Tracking - Smoke Test")
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
    (event_id, track_id, team_id, participant_id,
     resource_api, resource_hw, participant_token) = asyncio.run(seed_data(db_url))
    print(f"  team_id={team_id}")
    print(f"  resource_api={resource_api} (Groq API Key Pool, qty=5)")
    print(f"  resource_hw={resource_hw} (GPU Hardware Kit, qty=2)")

    # Organizer login
    print("\n[setup] Organizer login...")
    r = httpx.post(f"{BASE}/auth/organizer/login", json={
        "username": "organizer",
        "password": "pulse_admin_2026",
    }, timeout=TIMEOUT)
    check(r.status_code == 200, "Organizer login 200")
    org_token = r.json()["access_token"]
    org_h = {"Authorization": f"Bearer {org_token}"}
    part_h = {"Authorization": f"Bearer {participant_token}"}

    # --- Test 1: Organizer creates resource items ---
    print("\n[POST /resources] Organizer creates resources...")

    r = h("POST /resources (extra API keys)", httpx.post(
        f"{BASE}/resources",
        headers=org_h,
        json={"name": "Extra API Keys", "resource_type": "api_key", "total_quantity": 10},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 201, "Create extra resource: 201")
    extra_resource_id = r.json().get("id")

    # --- Test 2: GET /resource-pools (organizer view) ---
    print("\n[GET /resource-pools] Organizer views pool summary...")

    r = h("GET /resource-pools", httpx.get(
        f"{BASE}/resource-pools",
        headers=org_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /resource-pools 200")
    pools = r.json()
    check(len(pools) >= 2, f"Found {len(pools)} resource pools (expected >= 2)")

    # Check structure
    pool_names = [p["name"] for p in pools]
    check("Groq API Key Pool" in pool_names, "Groq API Key Pool exists in pools")
    check("GPU Hardware Kit" in pool_names, "GPU Hardware Kit exists in pools")

    # Check stock
    api_pool = next(p for p in pools if p["id"] == str(resource_api))
    check(api_pool is not None, "Seeded API key pool found by ID")
    check(api_pool["available_quantity"] == 5, "API key pool has 5 available")
    check(api_pool["total_quantity"] == 5, "API key pool has 5 total")
    check(api_pool["allocated_count"] == 0, "API key pool has 0 allocated")
    check(api_pool["overdue_count"] == 0, "API key pool has 0 overdue")

    # --- Test 3: POST /resource-requests (allocate API key) ---
    print("\n[POST /resource-requests] Requesting API key...")

    r = h("POST /resource-requests (API key)", httpx.post(
        f"{BASE}/resource-requests",
        headers=part_h,
        json={"resource_item_id": str(resource_api)},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 201, "Allocate API key: 201")
    alloc1 = r.json()
    alloc1_id = alloc1.get("id")
    check(alloc1_id is not None, f"alloc1_id={alloc1_id}")
    check(alloc1.get("status") == "allocated", "Status is 'allocated'")
    check(alloc1.get("resource_item") is not None, "Resource item info included")
    check(alloc1.get("team") is not None, "Team info included")
    check(alloc1.get("overdue") is False, "Not overdue")

    # --- Test 4: Verify stock decremented ---
    print("\n[GET /resource-pools] Stock check after allocation...")

    r = h("GET /resource-pools (after alloc)", httpx.get(
        f"{BASE}/resource-pools",
        headers=org_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /resource-pools 200")
    api_pool = next(p for p in r.json() if p["id"] == str(resource_api))
    check(api_pool is not None, "Seeded API key pool found after alloc")
    check(api_pool["available_quantity"] == 4, f"API key available = {api_pool['available_quantity']} (expected 4)")
    check(api_pool["allocated_count"] == 1, f"API key allocated = {api_pool['allocated_count']} (expected 1)")

    # --- Test 5: Allocate second resource (hardware) ---
    print("\n[POST /resource-requests] Requesting hardware...")

    r = h("POST /resource-requests (hardware)", httpx.post(
        f"{BASE}/resource-requests",
        headers=part_h,
        json={"resource_item_id": str(resource_hw)},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 201, "Allocate hardware: 201")
    alloc2_id = r.json().get("id")
    check(r.json().get("status") == "allocated", "Hardware allocated")

    # --- Test 6: GET /resource-requests/mine ---
    print("\n[GET /resource-requests/mine] Participant views allocations...")

    r = h("GET /resource-requests/mine", httpx.get(
        f"{BASE}/resource-requests/mine",
        headers=part_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /mine 200")
    mine = r.json()
    check(len(mine) >= 2, f"Found {len(mine)} allocations (expected >= 2)")
    check(
        all(a["status"] in ("allocated", "returned", "overdue") for a in mine),
        "All allocations have valid status",
    )

    # Filter by status
    r = h("GET /resource-requests/mine?status=allocated", httpx.get(
        f"{BASE}/resource-requests/mine",
        headers=part_h,
        params={"status": "allocated"},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /mine?status=allocated 200")
    check(len(r.json()) >= 2, "At least 2 allocated")

    # --- Test 7: GET /resource-requests/{id} ---
    print("\n[GET /resource-requests/{id}] View specific allocation...")

    r = h("GET /resource-requests/{id}", httpx.get(
        f"{BASE}/resource-requests/{alloc1_id}",
        headers=part_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET specific allocation 200")
    check(r.json().get("id") == alloc1_id, "Returned correct allocation")

    # --- Test 8: PATCH /resource-requests/{id}/return ---
    print("\n[PATCH /resource-requests/{id}/return] Returning resource...")

    r = h("PATCH /resource-requests/{id}/return (API key)", httpx.patch(
        f"{BASE}/resource-requests/{alloc1_id}/return",
        headers=part_h,
        json={},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "Return API key: 200")
    check(r.json().get("status") == "returned", "Status changed to 'returned'")
    check(r.json().get("returned_at") is not None, "returned_at set")

    # --- Test 9: Verify stock incremented after return ---
    print("\n[GET /resource-pools] Stock check after return...")

    r = h("GET /resource-pools (after return)", httpx.get(
        f"{BASE}/resource-pools",
        headers=org_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET /resource-pools 200")
    api_pool = next(p for p in r.json() if p["id"] == str(resource_api))
    check(api_pool is not None, "Seeded API key pool found after return")
    check(api_pool["available_quantity"] == 5, f"API key available = {api_pool['available_quantity']} (expected 5)")
    check(api_pool["allocated_count"] == 0, f"API key allocated = {api_pool['allocated_count']} (expected 0)")

    # --- Test 10: Cannot return again ---
    print("\n[PATCH /resource-requests/{id}/return] Already returned...")

    r = h("PATCH /resource-requests/{id}/return (already returned)", httpx.patch(
        f"{BASE}/resource-requests/{alloc1_id}/return",
        headers=part_h,
        json={},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 409, "Cannot return again -> 409")

    # --- Test 11: Out of stock ---
    print("\n[POST /resource-requests] Out of stock...")

    # Allocate all remaining hardware (only 1 left)
    r = h("POST /resource-requests (last hardware)", httpx.post(
        f"{BASE}/resource-requests",
        headers=part_h,
        json={"resource_item_id": str(resource_hw)},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 201, "Last hardware allocated: 201")

    # Now try to allocate when empty
    r = h("POST /resource-requests (out of stock)", httpx.post(
        f"{BASE}/resource-requests",
        headers=part_h,
        json={"resource_item_id": str(resource_hw)},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 409, "Out of stock returns 409")
    check("out of stock" in r.json().get("detail", "").lower() or
          "out of stock" in r.json().get("detail", "").replace("Resource ", "").lower(),
          "Error mentions out of stock")

    # --- Test 12: Invalid resource item ---
    print("\n[POST /resource-requests] Invalid resource...")

    fake_id = str(uuid.uuid4())
    r = h("POST /resource-requests (invalid)", httpx.post(
        f"{BASE}/resource-requests",
        headers=part_h,
        json={"resource_item_id": fake_id},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 404, "Invalid resource returns 404")

    # --- Test 13: No team participant ---
    print("\n[POST /resource-requests] No team participant...")

    async def create_orphan():
        sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        if "?" in sync_url:
            sync_url = sync_url.split("?")[0]
        conn = await asyncpg.connect(sync_url)
        try:
            orphan_id = uuid.uuid4()
            import hashlib
            orphan_token = "orphan_p8_" + uuid.uuid4().hex[:16]
            token_hash = hashlib.sha256(orphan_token.encode()).hexdigest()
            await conn.execute(
                "INSERT INTO participants (id, name, email, skills, track_pref, "
                "discord_handle, token_hash, team_id, created_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, NULL, NOW())",
                orphan_id, "Orphan P8", f"orphan_p8_{uuid.uuid4().hex[:8]}@example.com",
                ["python"], "ai", "orphan", token_hash,
            )
            from app.auth import create_jwt
            return create_jwt({"sub": str(orphan_id), "role": "participant"})
        finally:
            await conn.close()

    orphan_jwt = asyncio.run(create_orphan())
    orphan_h = {"Authorization": f"Bearer {orphan_jwt}"}

    r = h("POST /resource-requests (no team)", httpx.post(
        f"{BASE}/resource-requests",
        headers=orphan_h,
        json={"resource_item_id": str(resource_api)},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 409, "No team returns 409")

    # --- Test 14: Authorization tests ---
    print("\n[auth] Authorization tests...")

    r = h("GET /resource-pools (no auth)", httpx.get(
        f"{BASE}/resource-pools",
        timeout=TIMEOUT,
    ))
    check(r.status_code in (401, 403), "No auth returns 401/403")

    r = h("POST /resource-requests (no auth)", httpx.post(
        f"{BASE}/resource-requests",
        json={"resource_item_id": str(uuid.uuid4())},
        timeout=TIMEOUT,
    ))
    check(r.status_code in (401, 403), "POST without auth returns 401/403")

    # --- Test 15: Organizer list all allocations ---
    print("\n[GET /resource-requests] Organizer list...")

    r = h("GET /resource-requests (organizer)", httpx.get(
        f"{BASE}/resource-requests",
        headers=org_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "Organizer list 200")
    check(len(r.json()) >= 2, "Organizer sees >= 2 allocations")

    # --- Test 16: Overdue check endpoint ---
    print("\n[POST /resource-requests/check-overdue] Overdue check...")

    r = h("POST /resource-requests/check-overdue", httpx.post(
        f"{BASE}/resource-requests/check-overdue",
        headers=org_h,
        params={"threshold_hours": 24},
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "Overdue check 200")
    check(isinstance(r.json(), list), "Returns a list")

    # --- Test 17: Final pool state ---
    print("\n[final] Final resource pool state...")

    r = h("GET /resource-pools (final)", httpx.get(
        f"{BASE}/resource-pools",
        headers=org_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "Final pool state 200")
    for pool in r.json():
        check(
            pool["available_quantity"] >= 0,
            f"{pool['name']}: available={pool['available_quantity']} >= 0",
        )
        check(
            pool["available_quantity"] <= pool["total_quantity"],
            f"{pool['name']}: available <= total",
        )

    # --- Summary ---
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
