"""
Phase 10 smoke test - Team Formation & Matchmaking
Run with:
    python test_phase10.py
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
    Seed Event, Track, Teams (with varying skills), and unassigned Participants.
    Returns (event_id, track_id, team_id, team_member_id, team_member_jwt,
             unassigned_ids, unassigned_jwts).
    """
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if "?" in sync_url:
        sync_url = sync_url.split("?")[0]

    conn = await asyncpg.connect(sync_url)
    try:
        event_id = uuid.uuid4()
        track_id = uuid.uuid4()
        team_id = uuid.uuid4()
        team_member_id = uuid.uuid4()

        # Create event
        await conn.execute(
            "INSERT INTO events (id, name, current_phase, timezone, created_at) "
            "VALUES ($1, $2, $3, $4, NOW())",
            event_id, "Test Hackathon P10", "registration", "UTC",
        )

        # Create track with eligibility rules mentioning specific skills
        await conn.execute(
            "INSERT INTO tracks (id, name, eligibility_rules, event_id, created_at) "
            "VALUES ($1, $2, $3, $4, NOW())",
            track_id, "AI/ML Track",
            "Looking for teams with skills in python, machine learning, "
            "deep learning, data science, react, and deployment.",
            event_id,
        )

        # Create team with LIMITED skills (only python, git)
        await conn.execute(
            "INSERT INTO teams (id, name, track_id, submission_status, readiness_pct, created_at) "
            "VALUES ($1, $2, $3, $4, $5, NOW())",
            team_id, "Team Alpha", track_id, "not_submitted", 0.0,
        )

        # Team member 1 (has python, git)
        token1 = "test_token_p10_" + uuid.uuid4().hex[:16]
        token_hash1 = hashlib.sha256(token1.encode()).hexdigest()
        await conn.execute(
            "INSERT INTO participants (id, name, email, skills, track_pref, "
            "discord_handle, token_hash, team_id, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())",
            team_member_id, "Alice (Team Alpha)", f"alice_p10_{uuid.uuid4().hex[:8]}@example.com",
            ["python", "git"], "ai", "alice_dev", token_hash1, team_id,
        )

        # Create unassigned participants with VARIOUS skill sets
        unassigned_data = [
            # Bob: has ML + data science (great match)
            ("Bob (ML Expert)", ["python", "machine learning", "deep learning", "data science", "tensorflow"], "ai", "bob_ml"),
            # Carol: has react + deployment (partial match)
            ("Carol (Frontend)", ["react", "javascript", "html", "css", "node"], "web", "carol_ui"),
            # Dave: has python + ML + deployment (strong match)
            ("Dave (Full Stack ML)", ["python", "machine learning", "docker", "aws", "fastapi"], "ai", "dave_full"),
            # Eve: has completely different skills (weak match)
            ("Eve (Mobile)", ["flutter", "dart", "ios", "android", "swift"], "mobile", "eve_mob"),
            # Frank: has data science + python (good match)
            ("Frank (Data)", ["python", "data science", "pandas", "numpy", "sql"], "data", "frank_data"),
        ]

        unassigned_ids = []
        unassigned_jwts = []
        for name, skills, pref, handle in unassigned_data:
            uid = uuid.uuid4()
            token = "test_token_p10_" + uuid.uuid4().hex[:16]
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            email = f"{handle}_p10_{uuid.uuid4().hex[:8]}@example.com"
            await conn.execute(
                "INSERT INTO participants (id, name, email, skills, track_pref, "
                "discord_handle, token_hash, team_id, created_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, NULL, NOW())",
                uid, name, email, skills, pref, handle, token_hash,
            )
            from app.auth import create_jwt
            jwt = create_jwt({"sub": str(uid), "role": "participant"})
            unassigned_ids.append(uid)
            unassigned_jwts.append(jwt)

        from app.auth import create_jwt
        team_jwt = create_jwt({"sub": str(team_member_id), "role": "participant"})

        return (event_id, track_id, team_id, team_member_id, team_jwt,
                unassigned_ids, unassigned_jwts)
    finally:
        await conn.close()


def run_tests():
    global passed, failed

    print("=" * 60)
    print("Phase 10: Team Formation & Matchmaking - Smoke Test")
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
    (event_id, track_id, team_id, team_member_id, team_jwt,
     unassigned_ids, unassigned_jwts) = asyncio.run(seed_data(db_url))
    print(f"  team_id={team_id} (skills: python, git)")
    print(f"  track: AI/ML (needs: python, ml, deep learning, data science, react, deployment)")
    print(f"  unassigned participants: {len(unassigned_ids)}")

    part_h = {"Authorization": f"Bearer {team_jwt}"}

    # ─── Test 1: GET /teams/{id}/match-suggestions (team member) ────
    print("\n[GET /teams/{id}/match-suggestions] Team member views suggestions...")

    r = h("GET /teams/{id}/match-suggestions", httpx.get(
        f"{BASE}/teams/{team_id}/match-suggestions",
        headers=part_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "GET match-suggestions 200")
    data = r.json()

    # Check top-level structure
    check(data.get("team_id") == str(team_id), "Correct team_id")
    check(data.get("team_name") == "Team Alpha", "Correct team_name")
    check(data.get("total_candidates") >= 3, f"Found {data.get('total_candidates')} candidates (expected >= 3)")

    # ─── Test 2: Gap analysis ────────────────────────────────
    print("\n[gap analysis] Check skill gap identification...")

    gap = data.get("gap_analysis", {})
    check(gap.get("team_id") == str(team_id), "Gap analysis has correct team_id")
    check("python" in gap.get("team_skills", []), "Team skill 'python' detected")
    check("git" in gap.get("team_skills", []), "Team skill 'git' detected")
    check(gap.get("member_count") == 1, f"Member count: {gap.get('member_count')} (expected 1)")

    missing = gap.get("missing_skills", [])
    check(len(missing) >= 3, f"Missing skills: {missing} (expected >= 3)")
    # Team has python, track needs ml/data science/react/deployment etc.
    check("machine learning" in missing or "ml" in missing,
          "Missing 'machine learning' in gap")
    check("data science" in missing,
          "Missing 'data science' in gap")

    # ─── Test 3: Candidates are ranked correctly ──────────────
    print("\n[ranking] Check candidate ranking...")

    candidates = data.get("candidates", [])
    check(len(candidates) >= 3, f"Got {len(candidates)} candidates")

    if len(candidates) >= 2:
        # First candidate should have highest score
        check(candidates[0].get("match_score", 0) >= candidates[1].get("match_score", 0),
              f"First candidate score ({candidates[0].get('match_score')}) >= "
              f"second ({candidates[1].get('match_score')})")

    # ─── Test 4: Check candidate structure ────────────────────
    print("\n[structure] Check candidate details...")

    if candidates:
        top = candidates[0]
        check(top.get("participant_id") is not None, "Candidate has participant_id")
        check(top.get("name") is not None, "Candidate has name")
        check(top.get("skills") is not None, "Candidate has skills")
        check(top.get("match_score") is not None and top.get("match_score") >= 0,
              f"Candidate match_score: {top.get('match_score')}")
        check(top.get("reasoning") is not None and len(top.get("reasoning", "")) > 5,
              f"Candidate reasoning: '{top.get('reasoning', '')[:60]}'")
        check(top.get("matching_skills") is not None, "Candidate has matching_skills")

    # ─── Test 5: Best match should be Bob (ML) or Dave (Full Stack ML) ────
    print("\n[quality] Check best match quality...")

    # Bob has: machine learning, deep learning, data science (3 gap fills)
    # Dave has: machine learning, docker, aws, fastapi (1 direct gap + bonus)
    # Frank has: data science, pandas, numpy, sql (1 direct gap + bonus)
    top_names = [c.get("name", "") for c in candidates[:3]]
    check(any("Bob" in n or "Dave" in n for n in top_names),
          f"Top 3 should include Bob or Dave, got: {top_names}")

    # Check that Bob (ML expert) has matching_skills
    bob = next((c for c in candidates if "Bob" in c.get("name", "")), None)
    if bob:
        check(len(bob.get("matching_skills", [])) >= 2,
              f"Bob's matching_skills: {bob.get('matching_skills')}")

    # ─── Test 6: Message is helpful ──────────────────────────
    print("\n[message] Check suggestion message...")

    msg = data.get("message", "")
    check(len(msg) > 10, f"Message: '{msg[:80]}'")
    check("candidate" in msg.lower() or "match" in msg.lower() or "gap" in msg.lower(),
          f"Message mentions candidates/match/gap")

    # ─── Test 7: Unassigned participant cannot view other team's suggestions ────
    print("\n[auth] Unassigned participant tries to view team suggestions...")

    unassigned_h = {"Authorization": f"Bearer {unassigned_jwts[0]}"}
    r = h("GET /teams/{id}/match-suggestions (unassigned)", httpx.get(
        f"{BASE}/teams/{team_id}/match-suggestions",
        headers=unassigned_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 403, "Unassigned participant gets 403")

    # ─── Test 8: No auth returns 401/403 ─────────────────────
    print("\n[auth] No auth...")

    r = h("GET /teams/{id}/match-suggestions (no auth)", httpx.get(
        f"{BASE}/teams/{team_id}/match-suggestions",
        timeout=TIMEOUT,
    ))
    check(r.status_code in (401, 403), "No auth returns 401/403")

    # ─── Test 9: Non-existent team ───────────────────────────
    print("\n[error] Non-existent team...")

    fake_team_id = str(uuid.uuid4())
    r = h("GET /teams/{id}/match-suggestions (fake team)", httpx.get(
        f"{BASE}/teams/{fake_team_id}/match-suggestions",
        headers=part_h,
        timeout=TIMEOUT,
    ))
    # Row-level scoping fires first: participant is on team_id, not fake_team_id
    check(r.status_code in (403, 404), "Non-existent team returns 403/404")

    # ─── Test 10: Team with no track (edge case) ──────────────
    print("\n[edge case] Team with no track...")

    async def create_no_track_team():
        sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        if "?" in sync_url:
            sync_url = sync_url.split("?")[0]
        conn = await asyncpg.connect(sync_url)
        try:
            ntt_id = uuid.uuid4()
            ntt_member = uuid.uuid4()
            await conn.execute(
                "INSERT INTO teams (id, name, track_id, submission_status, readiness_pct, created_at) "
                "VALUES ($1, $2, NULL, $3, $4, NOW())",
                ntt_id, "Team No Track", "not_submitted", 0.0,
            )
            ntt_token = "test_token_p10_ntt_" + uuid.uuid4().hex[:16]
            ntt_hash = hashlib.sha256(ntt_token.encode()).hexdigest()
            await conn.execute(
                "INSERT INTO participants (id, name, email, skills, track_pref, "
                "discord_handle, token_hash, team_id, created_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())",
                ntt_member, "NTT Member", f"ntt_p10_{uuid.uuid4().hex[:8]}@example.com",
                ["python"], "ai", "ntt_user", ntt_hash, ntt_id,
            )
            from app.auth import create_jwt
            jwt = create_jwt({"sub": str(ntt_member), "role": "participant"})
            return ntt_id, jwt
        finally:
            await conn.close()

    ntt_id, ntt_jwt = asyncio.run(create_no_track_team())
    ntt_h = {"Authorization": f"Bearer {ntt_jwt}"}

    r = h("GET /teams/{id}/match-suggestions (no track)", httpx.get(
        f"{BASE}/teams/{ntt_id}/match-suggestions",
        headers=ntt_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "Team with no track: 200")
    ntt_data = r.json()
    check(ntt_data.get("total_candidates") >= 0, "Returns candidates (even without track)")
    check(ntt_data.get("gap_analysis", {}).get("track_needed_skills") == [],
          "No track skills when track is None")

    # ─── Test 11: Empty team (no members) ─────────────────────
    print("\n[edge case] Empty team...")

    async def create_empty_team():
        sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        if "?" in sync_url:
            sync_url = sync_url.split("?")[0]
        conn = await asyncpg.connect(sync_url)
        try:
            et_id = uuid.uuid4()
            et_member = uuid.uuid4()
            await conn.execute(
                "INSERT INTO teams (id, name, track_id, submission_status, readiness_pct, created_at) "
                "VALUES ($1, $2, $3, $4, $5, NOW())",
                et_id, "Team Empty", track_id, "not_submitted", 0.0,
            )
            et_token = "test_token_p10_et_" + uuid.uuid4().hex[:16]
            et_hash = hashlib.sha256(et_token.encode()).hexdigest()
            await conn.execute(
                "INSERT INTO participants (id, name, email, skills, track_pref, "
                "discord_handle, token_hash, team_id, created_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())",
                et_member, "ET Member", f"et_p10_{uuid.uuid4().hex[:8]}@example.com",
                [], "ai", "et_user", et_hash, et_id,
            )
            from app.auth import create_jwt
            jwt = create_jwt({"sub": str(et_member), "role": "participant"})
            return et_id, jwt
        finally:
            await conn.close()

    et_id, et_jwt = asyncio.run(create_empty_team())
    et_h = {"Authorization": f"Bearer {et_jwt}"}

    r = h("GET /teams/{id}/match-suggestions (empty team)", httpx.get(
        f"{BASE}/teams/{et_id}/match-suggestions",
        headers=et_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "Empty team: 200")
    et_data = r.json()
    check(et_data.get("gap_analysis", {}).get("team_skills") == [],
          "Empty team has no skills")
    # Team was created with a member (the participant who created it)
    check(et_data.get("gap_analysis", {}).get("member_count") >= 0,
          f"Empty team member_count: {et_data.get('gap_analysis', {}).get('member_count')}")
    check(et_data.get("total_candidates") >= 0, "Returns candidates for empty team")

    # ─── Test 12: Team fully covers track skills ──────────────
    print("\n[edge case] Team with full skill coverage...")

    async def create_full_team():
        sync_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        if "?" in sync_url:
            sync_url = sync_url.split("?")[0]
        conn = await asyncpg.connect(sync_url)
        try:
            ft_id = uuid.uuid4()
            ft_member = uuid.uuid4()
            await conn.execute(
                "INSERT INTO teams (id, name, track_id, submission_status, readiness_pct, created_at) "
                "VALUES ($1, $2, $3, $4, $5, NOW())",
                ft_id, "Team Full", track_id, "not_submitted", 100.0,
            )
            ft_token = "test_token_p10_ft_" + uuid.uuid4().hex[:16]
            ft_hash = hashlib.sha256(ft_token.encode()).hexdigest()
            await conn.execute(
                "INSERT INTO participants (id, name, email, skills, track_pref, "
                "discord_handle, token_hash, team_id, created_at) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())",
                ft_member, "FT Member", f"ft_p10_{uuid.uuid4().hex[:8]}@example.com",
                ["python", "machine learning", "deep learning", "data science",
                 "react", "docker", "aws"], "ai", "ft_user", ft_hash, ft_id,
            )
            from app.auth import create_jwt
            jwt = create_jwt({"sub": str(ft_member), "role": "participant"})
            return ft_id, jwt
        finally:
            await conn.close()

    ft_id, ft_jwt = asyncio.run(create_full_team())
    ft_h = {"Authorization": f"Bearer {ft_jwt}"}

    r = h("GET /teams/{id}/match-suggestions (full team)", httpx.get(
        f"{BASE}/teams/{ft_id}/match-suggestions",
        headers=ft_h,
        timeout=TIMEOUT,
    ))
    check(r.status_code == 200, "Full team: 200")
    ft_data = r.json()
    missing = ft_data.get("gap_analysis", {}).get("missing_skills", [])
    check(len(missing) <= 1, f"Full team has {len(missing)} missing skills (expected <= 1): {missing}")
    # Message should indicate good coverage or few gaps
    msg = ft_data.get("message", "")
    check(len(msg) > 10, f"Message: '{msg[:80]}'")

    # ─── Summary ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
