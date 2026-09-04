#!/usr/bin/env python3
"""Phase 15 — Seed Data Script.

Seeds the database with demo data for the hackathon demo:
- 1 Event with deadline (compressed timeline)
- 3 Tracks with submission requirements
- 18 Teams across tracks with varied completeness
- 35+ Participants across teams
- 5 Mentors
- 3 Resource Pools (one deliberately out of stock)
- 5+ Resource Allocations
- 4 Issues: auto-resolvable, escalation-needed, false-alarm, mentor-request
- Escalations, Notifications, Agent Actions

Usage:
    cd backend && python seed_data.py [--clean]
"""
from __future__ import annotations

import asyncio
import random
import sys
import os
import uuid
from datetime import datetime, timedelta, timezone

os.environ["PYTHONIOENCODING"] = "utf-8"

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEMO_PASSWORD = "demo1234"  # shared password for all seeded participants

# ─── Configuration ───────────────────────────────────────────

EVENT_DEADLINE_HOURS = 8  # compressed timeline: 8h from now
SEED_PREFIX = "DEMO"  # all seeded names start with this

# Track definitions
TRACKS = [
    {
        "name": "AI & Machine Learning",
        "eligibility_rules": (
            "Teams must build an AI/ML project using Python. "
            "Required skills: machine learning, data science, deep learning, "
            "natural language processing, computer vision, tensorflow, pytorch. "
            "Must include a working model and demo."
        ),
        "required_fields": ["repo_url", "demo_url", "description", "readme_url"],
    },
    {
        "name": "Web & Fullstack",
        "eligibility_rules": (
            "Teams must build a full-stack web application. "
            "Required skills: react, javascript, typescript, nodejs, "
            "css, html, database, api design, deployment, docker. "
            "Must include frontend, backend, and a live demo."
        ),
        "required_fields": ["repo_url", "demo_url", "description"],
    },
    {
        "name": "Hardware & IoT",
        "eligibility_rules": (
            "Teams must build a hardware/IoT project. "
            "Required skills: embedded systems, arduino, raspberry pi, "
            "iot, sensors, electronics, firmware, mqtt, networking. "
            "Must include hardware prototype and documentation."
        ),
        "required_fields": ["repo_url", "description", "readme_url"],
    },
]

# Team definitions — varied completeness
TEAMS = [
    # Track: AI & ML
    {"name": f"{SEED_PREFIX}-42-Alpha", "track": "AI & Machine Learning", "status": "in_progress", "readiness": 65.0},
    {"name": f"{SEED_PREFIX}-Beta-Neural", "track": "AI & Machine Learning", "status": "not_submitted", "readiness": 0.0},
    {"name": f"{SEED_PREFIX}-Gamma-Deep", "track": "AI & Machine Learning", "status": "submitted", "readiness": 100.0},
    {"name": f"{SEED_PREFIX}-Delta-LLM", "track": "AI & Machine Learning", "status": "in_progress", "readiness": 40.0},
    {"name": f"{SEED_PREFIX}-Epsilon-ML", "track": "AI & Machine Learning", "status": "not_submitted", "readiness": 0.0},
    {"name": f"{SEED_PREFIX}-Zeta-Vision", "track": "AI & Machine Learning", "status": "in_progress", "readiness": 85.0},
    # Track: Web & Fullstack
    {"name": f"{SEED_PREFIX}-Eta-React", "track": "Web & Fullstack", "status": "submitted", "readiness": 100.0},
    {"name": f"{SEED_PREFIX}-Theta-Stack", "track": "Web & Fullstack", "status": "in_progress", "readiness": 55.0},
    {"name": f"{SEED_PREFIX}-Iota-App", "track": "Web & Fullstack", "status": "not_submitted", "readiness": 0.0},
    {"name": f"{SEED_PREFIX}-Kappa-Web", "track": "Web & Fullstack", "status": "in_progress", "readiness": 70.0},
    {"name": f"{SEED_PREFIX}-Lambda-UI", "track": "Web & Fullstack", "status": "submitted", "readiness": 100.0},
    {"name": f"{SEED_PREFIX}-Mu-SPA", "track": "Web & Fullstack", "status": "in_progress", "readiness": 30.0},
    # Track: Hardware & IoT
    {"name": f"{SEED_PREFIX}-Nu-Sensor", "track": "Hardware & IoT", "status": "in_progress", "readiness": 50.0},
    {"name": f"{SEED_PREFIX}-Xi-IoT", "track": "Hardware & IoT", "status": "submitted", "readiness": 100.0},
    {"name": f"{SEED_PREFIX}-Omicron-Board", "track": "Hardware & IoT", "status": "not_submitted", "readiness": 0.0},
    {"name": f"{SEED_PREFIX}-Pi-Embedded", "track": "Hardware & IoT", "status": "in_progress", "readiness": 90.0},
    {"name": f"{SEED_PREFIX}-Rho-Firmware", "track": "Hardware & IoT", "status": "in_progress", "readiness": 25.0},
    {"name": f"{SEED_PREFIX}-Sigma-Robot", "track": "Hardware & IoT", "status": "in_progress", "readiness": 75.0},
]

# Participant pools
SKILL_POOLS = {
    "AI & Machine Learning": ["python", "machine learning", "data science", "deep learning", "pytorch", "tensorflow", "nlp", "computer vision", "scikit-learn", "pandas"],
    "Web & Fullstack": ["react", "javascript", "typescript", "nodejs", "css", "html", "postgresql", "docker", "fastapi", "nextjs"],
    "Hardware & IoT": ["embedded systems", "arduino", "raspberry pi", "iot", "sensors", "python", "c++", "mqtt", "electronics", "firmware"],
}

TEAM_SIZE_RANGE = (2, 3)

# Mentor roster
MENTORS = [
    {"name": "Dr. Sarah Chen", "skills": ["machine learning", "deep learning", "pytorch", "python", "data science"], "status": "available", "discord": "sarah_chen"},
    {"name": "Marcus Rodriguez", "skills": ["react", "typescript", "nodejs", "docker", "deployment"], "status": "available", "discord": "marcus_r"},
    {"name": "Priya Patel", "skills": ["embedded systems", "arduino", "raspberry pi", "iot", "sensors"], "status": "available", "discord": "priya_p"},
    {"name": "James Wilson", "skills": ["python", "fastapi", "postgresql", "machine learning", "nlp"], "status": "busy", "discord": "james_w"},
    {"name": "Aiko Tanaka", "skills": ["computer vision", "pytorch", "tensorflow", "deep learning", "python"], "status": "available", "discord": "aiko_t"},
]

# Resource pools
RESOURCE_POOLS = [
    {"name": "Groq API Keys", "type": "api_key", "total": 20, "available": 18},
    {"name": "GPU Cloud Credits", "type": "cloud_credit", "total": 10, "available": 3},
    {"name": "Raspberry Pi Kits", "type": "hardware_kit", "total": 5, "available": 0},  # deliberately out of stock
    {"name": "Arduino Starter Kits", "type": "hardware_kit", "total": 8, "available": 5},
    {"name": "Domain Names", "type": "api_key", "total": 15, "available": 12},
]


def _strip_sslmode(url: str) -> str:
    """Remove query params asyncpg can't parse (mirrors app/database.py)."""
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    for key in ("sslmode", "ssl", "channel_binding"):
        params.pop(key, None)
    clean_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=clean_query))


async def seed():
    """Seed the database with demo data."""
    import asyncpg

    # Connect
    sys.path.insert(0, os.path.dirname(__file__))
    from app.config import get_settings
    settings = get_settings()
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    db_url = _strip_sslmode(db_url)
    conn = await asyncpg.connect(db_url)

    print("[SEED] Connected to database.")

    # ─── Clean old demo data ──────────────────────
    print("[SEED] Cleaning old demo data...")
    await conn.execute("DELETE FROM agent_actions WHERE trigger_state_snapshot LIKE '%%DEMO%%'")
    await conn.execute("DELETE FROM notifications WHERE trigger_reason LIKE '%%demo%%'")
    await conn.execute("DELETE FROM mentor_allocations WHERE reasoning LIKE '%%DEMO%%'")
    await conn.execute("DELETE FROM escalations WHERE issue_id IN (SELECT id FROM issues WHERE description LIKE '%%DEMO%%')")
    await conn.execute("DELETE FROM resource_allocations WHERE team_id IN (SELECT id FROM teams WHERE name LIKE '%%DEMO%%')")
    await conn.execute("DELETE FROM issues WHERE description LIKE '%%DEMO%%'")
    await conn.execute("DELETE FROM submissions WHERE team_id IN (SELECT id FROM teams WHERE name LIKE '%%DEMO%%')")
    await conn.execute("DELETE FROM participants WHERE name LIKE '%%DEMO%%'")
    await conn.execute("DELETE FROM teams WHERE name LIKE '%%DEMO%%'")
    await conn.execute("DELETE FROM submission_requirements WHERE track_id IN (SELECT id FROM tracks WHERE name LIKE '%%AI%%' OR name LIKE '%%Web%%' OR name LIKE '%%Hardware%%')")
    await conn.execute("DELETE FROM tracks WHERE name LIKE '%%AI%%' OR name LIKE '%%Web%%' OR name LIKE '%%Hardware%%'")
    await conn.execute("DELETE FROM events WHERE name LIKE '%%DEMO%%'")
    await conn.execute("DELETE FROM mentors WHERE name LIKE '%%DEMO%%'")
    await conn.execute("DELETE FROM resource_items WHERE name LIKE '%%DEMO%%'")
    print("[SEED] Old data cleaned.")

    # ─── 1. Event ─────────────────────────────────
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(hours=EVENT_DEADLINE_HOURS)
    event_id = await conn.fetchval(
        "INSERT INTO events (name, current_phase, timezone, deadline_at) VALUES ($1, $2, $3, $4) RETURNING id",
        f"{SEED_PREFIX} HackOps 2026", "hacking", "UTC", deadline,
    )
    print(f"[SEED] Event created: {event_id}")

    # ─── 2. Tracks + Submission Requirements ───────
    track_ids = {}
    for t in TRACKS:
        tid = await conn.fetchval(
            "INSERT INTO tracks (name, eligibility_rules, event_id) VALUES ($1, $2, $3) RETURNING id",
            t["name"], t["eligibility_rules"], event_id,
        )
        track_ids[t["name"]] = tid
        for field in t["required_fields"]:
            await conn.execute(
                "INSERT INTO submission_requirements (track_id, field_name, required) VALUES ($1, $2, $3)",
                tid, field, True,
            )
    print(f"[SEED] {len(TRACKS)} tracks created with submission requirements.")

    # ─── 3. Mentors ────────────────────────────────
    mentor_ids = []
    for m in MENTORS:
        mid = await conn.fetchval(
            "INSERT INTO mentors (name, skills, availability_status, discord_handle) VALUES ($1, $2, $3, $4) RETURNING id",
            f"{SEED_PREFIX} {m['name']}", m["skills"], m["status"], m["discord"],
        )
        mentor_ids.append(mid)
    print(f"[SEED] {len(MENTORS)} mentors created.")

    # ─── 4. Resource Pools ─────────────────────────
    resource_ids = []
    for r in RESOURCE_POOLS:
        rid = await conn.fetchval(
            "INSERT INTO resource_items (name, resource_type, total_quantity, available_quantity) VALUES ($1, $2, $3, $4) RETURNING id",
            f"{SEED_PREFIX} {r['name']}", r["type"], r["total"], r["available"],
        )
        resource_ids.append(rid)
    print(f"[SEED] {len(RESOURCE_POOLS)} resource pools created (one deliberately at 0).")

    # ─── 5. Teams + Participants + Submissions ─────
    team_data = []  # (team_id, team_name, track_name, participants, submission_id)
    participant_counter = 0
    used_emails = set()
    demo_credentials = []  # (email, password) for summary

    for t in TRACKS:
        track_teams = [tm for tm in TEAMS if tm["track"] == t["name"]]
        for tm in track_teams:
            tid = await conn.fetchval(
                "INSERT INTO teams (name, track_id, submission_status, readiness_pct) VALUES ($1, $2, $3, $4) RETURNING id",
                tm["name"], track_ids[t["name"]], tm["status"], tm["readiness"],
            )

            # Create participants
            team_members = []
            size = random.choice(range(TEAM_SIZE_RANGE[0], TEAM_SIZE_RANGE[1] + 1))
            skills_pool = SKILL_POOLS[t["name"]]
            for i in range(size):
                participant_counter += 1
                email = f"{SEED_PREFIX.lower()}_p{participant_counter}@demo.com"
                while email in used_emails:
                    participant_counter += 1
                    email = f"{SEED_PREFIX.lower()}_p{participant_counter}@demo.com"
                used_emails.add(email)

                name = f"{SEED_PREFIX} P{participant_counter}"
                skills = random.sample(skills_pool, k=min(3, len(skills_pool)))
                password_hash = pwd_context.hash(DEMO_PASSWORD)

                pid = await conn.fetchval(
                    "INSERT INTO participants (name, email, password_hash, skills, track_pref, discord_handle, role, team_id) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id",
                    name, email, password_hash, skills, t["name"], f"demo_user_{participant_counter}", "participant", tid,
                )
                team_members.append(pid)
                demo_credentials.append((email, DEMO_PASSWORD))

            # Create submission (if team has one)
            sub_id = None
            if tm["status"] in ["submitted", "in_progress"]:
                # Fill fields based on completeness
                filled_fields = {}
                if tm["readiness"] >= 25:
                    filled_fields["repo_url"] = f"https://github.com/demo/{tm['name'].lower()}"
                if tm["readiness"] >= 50:
                    filled_fields["demo_url"] = f"https://demo.{tm['name'].lower()}.dev"
                if tm["readiness"] >= 30:
                    filled_fields["description"] = f"DEMO project: {tm['name']} - a {t['name']} project"
                if tm["readiness"] >= 60:
                    filled_fields["readme_url"] = f"https://github.com/demo/{tm['name'].lower()}/blob/main/README.md"

                completeness = tm["readiness"]
                sub_id = await conn.fetchval(
                    "INSERT INTO submissions (team_id, repo_url, demo_url, description, readme_url, completeness_pct) "
                    "VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
                    tid,
                    filled_fields.get("repo_url"),
                    filled_fields.get("demo_url"),
                    filled_fields.get("description"),
                    filled_fields.get("readme_url"),
                    completeness,
                )

            team_data.append({
                "team_id": tid,
                "team_name": tm["name"],
                "track_name": t["name"],
                "members": team_members,
                "submission_id": sub_id,
                "readiness": tm["readiness"],
                "status": tm["status"],
            })

    print(f"[SEED] {len(TEAMS)} teams created with {participant_counter} participants.")

    # ─── 6. Issues (4 scenarios) ───────────────────
    # Pick Team-42-Alpha for the demo scenario
    alpha_team = next(t for t in team_data if t["team_name"] == f"{SEED_PREFIX}-42-Alpha")
    alpha_member = alpha_team["members"][0]

    issues = []

    # Issue 1: Auto-resolvable (low severity, not blocking)
    issue1_id = await conn.fetchval(
        "INSERT INTO issues (participant_id, team_id, description, category, severity, is_blocking, status, urgency_score) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id",
        alpha_member, alpha_team["team_id"],
        "DEMO Issue: Minor CSS alignment issue on the landing page",
        "visual", 0.2, False, "open", 0.06,
    )
    issues.append({"id": issue1_id, "type": "auto-resolvable", "team": alpha_team["team_name"]})

    # Issue 2: Needs escalation (high severity, blocking)
    beta_team = next(t for t in team_data if t["team_name"] == f"{SEED_PREFIX}-Beta-Neural")
    beta_member = beta_team["members"][0]
    issue2_id = await conn.fetchval(
        "INSERT INTO issues (participant_id, team_id, description, category, severity, is_blocking, status, urgency_score) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id",
        beta_member, beta_team["team_id"],
        "DEMO Issue: Cannot deploy to cloud — all deployment attempts failing with 500 error",
        "technical", 0.9, True, "open", 0.87,
    )
    issues.append({"id": issue2_id, "type": "needs-escalation", "team": beta_team["team_name"]})

    # Issue 3: False alarm (very low severity, resolves easily)
    gamma_team = next(t for t in team_data if t["team_name"] == f"{SEED_PREFIX}-Gamma-Deep")
    gamma_member = gamma_team["members"][0]
    issue3_id = await conn.fetchval(
        "INSERT INTO issues (participant_id, team_id, description, category, severity, is_blocking, status, urgency_score) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id",
        gamma_member, gamma_team["team_id"],
        "DEMO Issue: Environment variable typo causing import warning (cosmetic only)",
        "configuration", 0.1, False, "open", 0.03,
    )
    issues.append({"id": issue3_id, "type": "false-alarm", "team": gamma_team["team_name"]})

    # Issue 4: Mentor request (medium severity, needs skill match)
    theta_team = next(t for t in team_data if t["team_name"] == f"{SEED_PREFIX}-Theta-Stack")
    theta_member = theta_team["members"][0]
    issue4_id = await conn.fetchval(
        "INSERT INTO issues (participant_id, team_id, description, category, severity, is_blocking, status, urgency_score) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id",
        theta_member, theta_team["team_id"],
        "DEMO Issue: Need help with database optimization — queries timing out under load",
        "technical", 0.6, False, "open", 0.42,
    )
    issues.append({"id": issue4_id, "type": "mentor-request", "team": theta_team["team_name"]})

    print(f"[SEED] {len(issues)} issues created.")

    # ─── 7. Escalations ────────────────────────────
    esc_id = await conn.fetchval(
        "INSERT INTO escalations (issue_id, urgency_score, status) VALUES ($1, $2, $3) RETURNING id",
        issue2_id, 0.87, "open",
    )
    print(f"[SEED] Escalation created for high-severity issue.")

    # ─── 8. Resource Allocations ───────────────────
    # Allocate from pools WITH stock (index 2 = Raspberry Pi is deliberately
    # out of stock), and decrement each pool's available_quantity so the
    # dashboard numbers reflect real allocations.
    allocatable_pool_indexes = [i for i, rid in enumerate(resource_ids) if i != 2]
    for i, td in enumerate(team_data[:4]):
        pool_idx = allocatable_pool_indexes[i % len(allocatable_pool_indexes)]
        rid = resource_ids[pool_idx]
        await conn.execute(
            "INSERT INTO resource_allocations (resource_item_id, team_id, status) VALUES ($1, $2, $3)",
            rid, td["team_id"], "allocated",
        )
        await conn.execute(
            "UPDATE resource_items SET available_quantity = available_quantity - 1 WHERE id = $1",
            rid,
        )
    print("[SEED] 4 resource allocations created (pool stock decremented).")

    # ─── 9. Agent Actions ──────────────────────────
    for td in team_data[:3]:
        await conn.execute(
            "INSERT INTO agent_actions (action_type, trigger_state_snapshot, reasoning_trace, policy_check_result, outcome) "
            "VALUES ($1, $2, $3, $4, $5)",
            "send_notification",
            f'DEMO: {{"team_id": "{td["team_id"]}", "team_name": "{td["team_name"]}"}}',
            f"DEMO: Submission audit for {td['team_name']} — completeness={td['readiness']}%",
            "allowed",
            f"Notification sent to {td['team_name']} members",
        )
    print("[SEED] Agent actions created.")

    await conn.close()

    # ─── Print summary ─────────────────────────────
    print("\n" + "=" * 60)
    print("  SEED DATA SUMMARY")
    print("=" * 60)
    print(f"  Event:          {SEED_PREFIX} HackOps 2026 (deadline: {EVENT_DEADLINE_HOURS}h from now)")
    print(f"  Tracks:         {len(TRACKS)} ({', '.join(t['name'] for t in TRACKS)})")
    print(f"  Teams:          {len(TEAMS)} ({sum(1 for t in TEAMS if t['status']=='submitted')} submitted, {sum(1 for t in TEAMS if t['status']=='in_progress')} in-progress, {sum(1 for t in TEAMS if t['status']=='not_submitted')} not-submitted)")
    print(f"  Participants:   {participant_counter}")
    print(f"  Mentors:        {len(MENTORS)} ({sum(1 for m in MENTORS if m['status']=='available')} available)")
    print(f"  Resources:      {len(RESOURCE_POOLS)} pools (one at 0 stock)")
    print(f"  Issues:         {len(issues)} (auto-resolvable, escalation, false-alarm, mentor-request)")
    print(f"  Escalations:    1 (high-severity)")
    print(f"  Agent Actions:  3")
    print("=" * 60)
    print(f"\n  Demo team: {SEED_PREFIX}-42-Alpha (readiness: 65%, in-progress)")
    print("  Issue scenarios:")
    for i in issues:
        print(f"    - {i['type']}: {i['team']}")
    print("=" * 60)
    org_user = settings.organizer_username or "organizer"
    org_pass = settings.organizer_password or "(not set in .env — see server log)"
    print("  LOGIN CREDENTIALS")
    print(f"    Organizer:   {org_user} / {org_pass}")
    print(f"    Participant: log in at /auth/participant/login with email + password")
    print(f"    Shared demo password: {DEMO_PASSWORD}")
    print("    Example participant logins (email / password):")
    for e, p in demo_credentials[:5]:
        print(f"      {e}  /  {p}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed())
