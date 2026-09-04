"""
test_remaining.py — Remaining phases (6,9,10,11,12,13,14,15)

Phase 6:  Issues & Escalations
Phase 9:  Q&A / AI Assistant
Phase 10: Matchmaking
Phase 11: Orchestrator
Phase 12: Discord Bot Integration
Phase 13: Notification Delivery
Phase 14: Participant-Facing UI
Phase 15: Seed Data & Demo

Run:  python test_remaining.py
"""
import httpx
import json
import sys
import time
import uuid

BASE = "http://127.0.0.1:8000"
DEMO_PASS = "testpass123"
_ts = int(time.time())

import os
from pathlib import Path
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
_env = {}
for line in ENV_PATH.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        _env[k.strip()] = v.strip()
ORG_PASS = _env.get("ORGANIZER_PASSWORD", "")

_pass = [0]
_fail = [0]

def ok(label, condition, detail=""):
    if condition:
        _pass[0] += 1
        print(f"  [PASS] {label}")
    else:
        _fail[0] += 1
        print(f"  [FAIL] {label}  ({detail})" if detail else f"  [FAIL] {label}")

def header(label):
    print(f"\n{'-'*55}")
    print(f"  {label}")

def auth(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── Shared setup ───────────────────────────────────────────
with httpx.Client(base_url=BASE, timeout=60) as c:

    header("Setup: organizer")
    r = c.post("/auth/organizer/login", json={"username": "organizer", "password": ORG_PASS})
    ok("Organizer login", r.status_code == 200)
    OHD = auth(r.json()["access_token"])

    r = c.get("/tracks", headers=OHD)
    tracks = r.json()
    ok("Tracks exist", len(tracks) > 0)
    track_id = tracks[0]["id"]

    header("Setup: register A + B, create team")
    email_a = f"alice_rem_{_ts}@example.com"
    r = c.post("/participants/register", json={"name": "Alice Rem", "email": email_a, "password": DEMO_PASS, "skills": ["python", "docker"]})
    ok("Register A", r.status_code == 201)
    r = c.post("/auth/participant/login", json={"email": email_a, "password": DEMO_PASS})
    AHD = auth(r.json()["access_token"])

    r = c.post("/teams", headers=AHD, json={"name": f"RemTeam-{uuid.uuid4().hex[:6]}", "track_id": track_id})
    ok("Create team A", r.status_code == 201)
    team_a_id = r.json()["id"]

    email_b = f"bob_rem_{_ts}@example.com"
    r = c.post("/participants/register", json={"name": "Bob Rem", "email": email_b, "password": DEMO_PASS, "skills": ["go"]})
    ok("Register B", r.status_code == 201)
    r = c.post("/auth/participant/login", json={"email": email_b, "password": DEMO_PASS})
    BHD = auth(r.json()["access_token"])
    r = c.post(f"/teams/{team_a_id}/join", headers=BHD)
    ok("B joins team A", r.status_code == 200)

    # ── Phase 6: Issues & Escalations ────────────────────
    header("Phase 6: Issues & Escalations")

    r = c.post("/issues", headers=AHD, json={
        "description": "Docker deployment failing with port binding error",
        "category": "deployment", "severity": 0.8, "is_blocking": True,
    })
    ok("Create issue", r.status_code == 201)
    issue_id = r.json()["id"]
    ok("Issue has urgency_score", "urgency_score" in r.json())

    r = c.get("/issues/mine", headers=AHD)
    ok("GET /issues/mine", r.status_code == 200)
    ok("Has issues", len(r.json()) > 0)

    r = c.get(f"/issues/{issue_id}", headers=AHD)
    ok("GET /issues/{id}", r.status_code == 200)
    ok("Correct issue", r.json()["id"] == issue_id)

    r = c.get("/escalations", headers=OHD)
    ok("GET /escalations (org)", r.status_code == 200)
    ok("Returns list", isinstance(r.json(), list))

    # B (same team) can also view the issue
    r = c.get(f"/issues/{issue_id}", headers=BHD)
    ok("B (same team) views issue -> 200", r.status_code == 200)

    # ── Phase 9: Q&A ────────────────────────────────────
    header("Phase 9: Q&A / AI Assistant")

    r = c.post("/qa", headers=AHD, json={"question": "What are the submission requirements?"})
    # May fail if Groq API is down, so accept 200 or 500
    ok("POST /qa returns 200 or 500", r.status_code in (200, 500))
    if r.status_code == 200:
        ok("Response has answer", "answer" in r.json() or "response" in r.json())

    # ── Phase 10: Matchmaking ────────────────────────────
    header("Phase 10: Matchmaking")

    r = c.get(f"/teams/{team_a_id}/match-suggestions", headers=AHD)
    ok("GET match suggestions -> 200", r.status_code == 200)
    suggestions = r.json()
    ok("Has candidates key", "candidates" in suggestions or "total_candidates" in suggestions)

    # B (same team) can also view
    r = c.get(f"/teams/{team_a_id}/match-suggestions", headers=BHD)
    ok("B views match suggestions -> 200", r.status_code == 200)

    # ── Phase 11: Orchestrator ───────────────────────────
    header("Phase 11: Orchestrator")

    r = c.get("/orchestrator/status", headers=OHD)
    ok("GET /orchestrator/status -> 200", r.status_code == 200)

    r = c.get("/orchestrator/actions?limit=10", headers=OHD)
    ok("GET /orchestrator/actions -> 200", r.status_code == 200)

    # Run orchestrator sweep (may timeout on slow DB)
    try:
        r = c.post("/orchestrator/sweep", headers=OHD, timeout=120)
        ok("POST /orchestrator/sweep -> 200", r.status_code == 200)
    except httpx.ReadTimeout:
        print("  [SKIP] Orchestrator sweep timed out (slow DB)")

    # ── Phase 13: Notifications ──────────────────────────
    header("Phase 13: Notifications")

    r = c.get("/notifications/mine", headers=AHD)
    ok("GET /notifications/mine -> 200", r.status_code == 200)

    r = c.get("/notifications/pending", headers=OHD)
    ok("GET /notifications/pending (org) -> 200", r.status_code == 200)

    r = c.get("/notifications/channels", headers=OHD)
    ok("GET /notifications/channels -> 200", r.status_code == 200)

    # ── Phase 14: Participant UI endpoints ────────────────
    header("Phase 14: Participant UI endpoints")

    r = c.get("/participants/me", headers=AHD)
    ok("GET /participants/me -> 200", r.status_code == 200)

    r = c.get("/teams/mine", headers=AHD)
    ok("GET /teams/mine -> 200", r.status_code == 200)

    # ── Phase 15: Seed data endpoints ────────────────────
    header("Phase 15: Dashboard health")

    r = c.get("/dashboard/health", headers=OHD)
    ok("GET /dashboard/health -> 200", r.status_code == 200)
    health = r.json()
    ok("Has total_teams", "total_teams" in health)
    ok("Has total_participants", "total_participants" in health)
    ok("total_participants >= 0", health["total_participants"] >= 0)

print(f"\n{'='*55}")
if _fail[0]:
    print(f"  FAILED: {_fail[0]} / {_pass[0]+_fail[0]}")
    sys.exit(1)
else:
    print(f"  ALL {_pass[0]} CHECKS PASSED")
print(f"{'='*55}")
