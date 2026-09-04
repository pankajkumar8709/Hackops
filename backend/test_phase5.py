"""
test_phase5.py — Submission Audit Module

Tests:
  1. Setup: register A+B, create team with track, join
  2. POST /submissions (incomplete - 1/4 fields) -> 25%
  3. GET /submissions/mine
  4. GET /submissions/{id}/audit -> field-level detail
  5. PATCH /submissions/{id} -> add 2 more fields -> 75%
  6. PATCH -> add description -> 100%
  7. Row-level: B (same team) can view audit
  8. Row-level: C (different team) -> 403
  9. Organizer GET /submissions -> 200
 10. Organizer GET /submissions/{id}/audit-organizer -> 200

Run:  python test_phase5.py
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

with httpx.Client(base_url=BASE, timeout=30) as c:

    header("Setup: organizer + track")
    r = c.post("/auth/organizer/login", json={"username": "organizer", "password": ORG_PASS})
    ok("Organizer login", r.status_code == 200)
    OHD = auth(r.json()["access_token"])

    r = c.get("/tracks", headers=OHD)
    tracks = r.json()
    ok("Tracks exist", len(tracks) > 0, f"count={len(tracks)}")
    track_id = tracks[0]["id"]

    header("Setup: register A, create team with track")
    email_a = f"alice_sub_{_ts}@example.com"
    r = c.post("/participants/register", json={"name": "Alice Sub", "email": email_a, "password": DEMO_PASS, "skills": ["Python"]})
    ok("Register A", r.status_code == 201)
    r = c.post("/auth/participant/login", json={"email": email_a, "password": DEMO_PASS})
    AHD = auth(r.json()["access_token"])

    team_name = f"SubTeam-{uuid.uuid4().hex[:6]}"
    r = c.post("/teams", headers=AHD, json={"name": team_name, "track_id": track_id})
    ok("Create team", r.status_code == 201)
    team_id = r.json()["id"]

    header("Setup: register B, join team")
    email_b = f"bob_sub_{_ts}@example.com"
    r = c.post("/participants/register", json={"name": "Bob Sub", "email": email_b, "password": DEMO_PASS, "skills": ["Go"]})
    ok("Register B", r.status_code == 201)
    r = c.post("/auth/participant/login", json={"email": email_b, "password": DEMO_PASS})
    BHD = auth(r.json()["access_token"])
    r = c.post(f"/teams/{team_id}/join", headers=BHD)
    ok("B joins team", r.status_code == 200)

    header("1. POST /submissions (incomplete - only repo_url)")
    r = c.post("/submissions", headers=AHD, json={"repo_url": "https://github.com/team/project"})
    ok("Create submission -> 201", r.status_code == 201)
    sub = r.json()
    sub_id = sub["id"]
    ok("completeness_pct = 25%", sub["completeness_pct"] == 25.0, f"got {sub['completeness_pct']}")
    ok("last_audited_at set", sub["last_audited_at"] is not None)

    header("2. GET /submissions/mine")
    r = c.get("/submissions/mine", headers=AHD)
    ok("Returns 200", r.status_code == 200)
    ok("Correct submission", r.json()["id"] == sub_id)

    header("3. GET /submissions/{id}/audit")
    r = c.get(f"/submissions/{sub_id}/audit", headers=AHD)
    ok("Audit returns 200", r.status_code == 200)
    audit = r.json()
    ok("total_required = 4", audit["total_required"] == 4)
    ok("total_present = 1", audit["total_present"] == 1)
    ok("completeness = 25%", audit["completeness_pct"] == 25.0)
    fields = {f["field_name"]: f for f in audit["fields"]}
    ok("repo_url passed", fields["repo_url"]["passed"] is True)
    ok("readme_url failed", fields["readme_url"]["passed"] is False)
    ok("demo_url failed", fields["demo_url"]["passed"] is False)
    ok("description failed", fields["description"]["passed"] is False)

    header("4. PATCH - add readme_url + demo_url -> 75%")
    r = c.patch(f"/submissions/{sub_id}", headers=AHD, json={
        "readme_url": "https://github.com/team/project/blob/main/README.md",
        "demo_url": "https://youtu.be/demo123",
    })
    ok("Patch returns 200", r.status_code == 200)
    ok("completeness = 75%", r.json()["completeness_pct"] == 75.0, f"got {r.json()['completeness_pct']}")

    header("5. PATCH - add description -> 100%")
    r = c.patch(f"/submissions/{sub_id}", headers=AHD, json={
        "description": "An AI-powered hackathon concierge that helps teams succeed.",
    })
    ok("Patch returns 200", r.status_code == 200)
    ok("completeness = 100%", r.json()["completeness_pct"] == 100.0, f"got {r.json()['completeness_pct']}")

    header("6. Row-level: B (same team) can view audit")
    r = c.get(f"/submissions/{sub_id}/audit", headers=BHD)
    ok("B can view -> 200", r.status_code == 200)

    header("7. Row-level: C (different team) -> 403")
    email_c = f"carol_sub_{_ts}@example.com"
    r = c.post("/participants/register", json={"name": "Carol Sub", "email": email_c, "password": DEMO_PASS, "skills": ["JS"]})
    ok("Register C", r.status_code == 201)
    r = c.post("/auth/participant/login", json={"email": email_c, "password": DEMO_PASS})
    CHD = auth(r.json()["access_token"])
    r = c.post("/teams", headers=CHD, json={"name": f"Other-{uuid.uuid4().hex[:6]}"})
    ok("C creates team", r.status_code == 201)
    r = c.get(f"/submissions/{sub_id}/audit", headers=CHD)
    ok("C cannot view -> 403", r.status_code == 403)

    header("8. Organizer endpoints")
    r = c.get("/submissions", headers=OHD)
    ok("GET /submissions (org) -> 200", r.status_code == 200)
    ok("Returns list", isinstance(r.json(), list))
    r = c.get(f"/submissions/{sub_id}/audit-organizer", headers=OHD)
    ok("Org audit -> 200", r.status_code == 200)

    header("9. No team -> cannot submit")
    email_d = f"dave_sub_{_ts}@example.com"
    r = c.post("/participants/register", json={"name": "Dave Sub", "email": email_d, "password": DEMO_PASS, "skills": []})
    ok("Register D (no team)", r.status_code == 201)
    r = c.post("/auth/participant/login", json={"email": email_d, "password": DEMO_PASS})
    DHD = auth(r.json()["access_token"])
    r = c.post("/submissions", headers=DHD, json={"repo_url": "https://x.com"})
    ok("No team submit -> 409", r.status_code == 409)

print(f"\n{'='*55}")
if _fail[0]:
    print(f"  FAILED: {_fail[0]} / {_pass[0]+_fail[0]}")
    sys.exit(1)
else:
    print(f"  ALL {_pass[0]} CHECKS PASSED")
print(f"{'='*55}")
