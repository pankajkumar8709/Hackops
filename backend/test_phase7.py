"""
test_phase7.py — Mentor Allocation

Tests:
  1. Setup: register A, create team with track, create issue
  2. POST /mentor-allocations (request mentor for issue)
  3. GET /mentor-allocations/mine (team sees own allocations)
  4. GET /mentor-allocations (organizer sees all)
  5. PATCH /mentor-allocations/{id}/accept
  6. Duplicate allocation -> 409
  7. Row-level: other team's issue -> 403

Run:  python test_phase7.py
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

with httpx.Client(base_url=BASE, timeout=60) as c:

    header("Setup: organizer + track + mentor")
    r = c.post("/auth/organizer/login", json={"username": "organizer", "password": ORG_PASS})
    ok("Organizer login", r.status_code == 200)
    OHD = auth(r.json()["access_token"])

    r = c.get("/tracks", headers=OHD)
    tracks = r.json()
    ok("Tracks exist", len(tracks) > 0)
    track_id = tracks[0]["id"]

    header("Setup: register A, create team")
    email_a = f"alice_ment_{_ts}@example.com"
    r = c.post("/participants/register", json={"name": "Alice Ment", "email": email_a, "password": DEMO_PASS, "skills": ["Python"]})
    ok("Register A", r.status_code == 201)
    r = c.post("/auth/participant/login", json={"email": email_a, "password": DEMO_PASS})
    AHD = auth(r.json()["access_token"])

    team_name = f"MentTeam-{uuid.uuid4().hex[:6]}"
    r = c.post("/teams", headers=AHD, json={"name": team_name, "track_id": track_id})
    ok("Create team", r.status_code == 201)
    team_id = r.json()["id"]

    header("Setup: create issue for team A")
    r = c.post("/issues", headers=AHD, json={
        "description": "Need help with Docker container deployment - port binding error keeps failing",
        "category": "deployment",
        "severity": 0.8,
        "is_blocking": True,
    })
    ok("Create issue", r.status_code == 201)
    issue_id = r.json()["id"]

    header("1. POST /mentor-allocations (request mentor)")
    r = c.post("/mentor-allocations", headers=AHD, json={"issue_id": issue_id})
    # This calls LLM for skill classification -- may be slow
    ok("Request mentor returns 201 or 404 (no match)", r.status_code in (201, 404))
    if r.status_code == 201:
        alloc = r.json()
        alloc_id = alloc["id"]
        ok("Allocation has id", "id" in alloc)
        ok("Status is proposed", alloc["status"] == "proposed")
        ok("mentor field present", "mentor" in alloc)

        header("2. GET /mentor-allocations/mine")
        r = c.get("/mentor-allocations/mine", headers=AHD)
        ok("Returns 200", r.status_code == 200)
        ok("List has allocations", len(r.json()) > 0)

        header("3. GET /mentor-allocations (organizer)")
        r = c.get("/mentor-allocations", headers=OHD)
        ok("Returns 200", r.status_code == 200)
        ok("Returns list", isinstance(r.json(), list))

        header("4. PATCH /mentor-allocations/{id}/accept")
        r = c.patch(f"/mentor-allocations/{alloc_id}/accept", headers=AHD, json={"notes": "I can help with that"})
        ok("Accept returns 200", r.status_code == 200)
        ok("Status is accepted", r.json()["status"] == "accepted")

        header("5. Duplicate allocation -> 409")
        r = c.post("/mentor-allocations", headers=AHD, json={"issue_id": issue_id})
        ok("Duplicate -> 409", r.status_code == 409)
    else:
        print("  [SKIP] No mentor match found (404) - skipping allocation flow tests")

    header("6. Row-level: other team cannot request mentor for A's issue")
    email_c = f"carol_ment_{_ts}@example.com"
    r = c.post("/participants/register", json={"name": "Carol Ment", "email": email_c, "password": DEMO_PASS, "skills": []})
    ok("Register C", r.status_code == 201)
    r = c.post("/auth/participant/login", json={"email": email_c, "password": DEMO_PASS})
    CHD = auth(r.json()["access_token"])
    r = c.post("/teams", headers=CHD, json={"name": f"Other-{uuid.uuid4().hex[:6]}"})
    ok("C creates team", r.status_code == 201)
    r = c.post("/mentor-allocations", headers=CHD, json={"issue_id": issue_id})
    ok("C requests mentor for A's issue -> 403", r.status_code == 403)

print(f"\n{'='*55}")
if _fail[0]:
    print(f"  FAILED: {_fail[0]} / {_pass[0]+_fail[0]}")
    sys.exit(1)
else:
    print(f"  ALL {_pass[0]} CHECKS PASSED")
print(f"{'='*55}")
