"""
test_phase2.py — Auth & Onboarding (email + password)

Tests:
  1. Health check
  2. Organizer login (env credentials)
  3. Wrong organizer password -> 401
  4. Participant registration with password
  5. Duplicate email -> 409
  6. Participant login with correct password
  7. Wrong password -> 401
  8. GET /participants/me
  9. Create team
  10. Join team
  11. Row-level scoping (teams/mine)
  12. RBAC: participant cannot list all teams -> 403
  13. Organizer can list all teams -> 200

Run:  python test_phase2.py
      (requires backend on :8000)
"""
import httpx
import json
import sys
import time
import uuid

BASE = "http://127.0.0.1:8000"

# ── Load organizer credentials from .env ───────────────────
import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
_env: dict[str, str] = {}
for line in ENV_PATH.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        _env[k.strip()] = v.strip()

ORG_USER = _env.get("ORGANIZER_USERNAME", "organizer")
ORG_PASS = _env.get("ORGANIZER_PASSWORD", "")
DEMO_PASS = "testpass123"
_ts = int(time.time())


# ── Helpers ────────────────────────────────────────────────
_pass = [0]
_fail = [0]

def ok(label, condition, detail=""):
    if condition:
        _pass[0] += 1
        print(f"  [PASS] {label}")
    else:
        _fail[0] += 1
        msg = f"  [FAIL] {label}"
        if detail:
            msg += f"  ({detail})"
        print(msg)

def header(label):
    print(f"\n{'-'*55}")
    print(f"  {label}")

def auth(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── Tests ──────────────────────────────────────────────────
with httpx.Client(base_url=BASE, timeout=30) as c:

    header("1. Health check")
    r = c.get("/health")
    ok("GET /health returns 200", r.status_code == 200)
    ok("version field present", bool(r.json().get("version")))

    header("2. Organizer login")
    r = c.post("/auth/organizer/login", json={"username": ORG_USER, "password": ORG_PASS})
    ok("POST /auth/organizer/login returns 200", r.status_code == 200)
    org_token = r.json().get("access_token", "")
    ok("access_token returned", bool(org_token))
    OHD = auth(org_token)

    header("3. Wrong organizer password")
    r = c.post("/auth/organizer/login", json={"username": ORG_USER, "password": "wrong"})
    ok("Wrong password returns 401", r.status_code == 401)

    header("4. Register participant A")
    email_a = f"alice_{_ts}@example.com"
    r = c.post("/participants/register", json={
        "name": "Alice", "email": email_a, "password": DEMO_PASS,
        "skills": ["Python", "ML"], "discord_handle": "alice#0001",
    })
    ok("Register returns 201", r.status_code == 201)
    data = r.json()
    ok("Response has id", "id" in data)
    ok("Response has name=Alice", data.get("name") == "Alice")
    ok("No token in response", "token" not in data)
    alice_id = data["id"]

    header("5. Duplicate email -> 409")
    r = c.post("/participants/register", json={
        "name": "Alice2", "email": email_a, "password": DEMO_PASS, "skills": [],
    })
    ok("Duplicate email returns 409", r.status_code == 409)

    header("6. Participant A login")
    r = c.post("/auth/participant/login", json={"email": email_a, "password": DEMO_PASS})
    ok("Login returns 200", r.status_code == 200)
    token_a = r.json().get("access_token", "")
    ok("JWT returned", bool(token_a))
    ok("participant_id returned", "participant_id" in r.json())
    AHD = auth(token_a)

    header("7. Wrong password -> 401")
    r = c.post("/auth/participant/login", json={"email": email_a, "password": "wrong"})
    ok("Wrong password returns 401", r.status_code == 401)

    header("8. Register + login participant B")
    email_b = f"bob_{_ts}@example.com"
    r = c.post("/participants/register", json={
        "name": "Bob", "email": email_b, "password": DEMO_PASS, "skills": ["Go"],
    })
    ok("Register B returns 201", r.status_code == 201)
    r = c.post("/auth/participant/login", json={"email": email_b, "password": DEMO_PASS})
    ok("Login B returns 200", r.status_code == 200)
    BHD = auth(r.json()["access_token"])

    header("9. GET /participants/me")
    r = c.get("/participants/me", headers=AHD)
    ok("Returns 200", r.status_code == 200)
    ok("Name is Alice", "Alice" in r.json().get("name", ""))
    ok("No password_hash in response", "password_hash" not in r.json())
    ok("No token_hash in response", "token_hash" not in r.json())

    header("10. Create team as A")
    team_name = f"Team-{uuid.uuid4().hex[:6]}"
    r = c.post("/teams", headers=AHD, json={"name": team_name})
    ok("Create team returns 201", r.status_code == 201)
    team_id = r.json()["id"]

    header("11. B joins team")
    r = c.post(f"/teams/{team_id}/join", headers=BHD)
    ok("B joins returns 200", r.status_code == 200)

    header("12. Row-level scoping: /teams/mine")
    r = c.get("/teams/mine", headers=AHD)
    ok("A's /teams/mine returns 200", r.status_code == 200)
    ok("Returns correct team", r.json()["id"] == team_id)

    r = c.get("/teams/mine", headers=BHD)
    ok("B's /teams/mine returns same team", r.json()["id"] == team_id)

    header("13. RBAC: participant cannot list all teams")
    r = c.get("/teams", headers=AHD)
    ok("Participant GET /teams -> 403", r.status_code == 403)

    header("14. Organizer can list all teams")
    r = c.get("/teams", headers=OHD)
    ok("Organizer GET /teams -> 200", r.status_code == 200)
    ok("Returns list", isinstance(r.json(), list))

    header("15. Password not returned in any response")
    r = c.get("/participants/me", headers=AHD)
    ok("password_hash not in /me", "password_hash" not in r.json())

# ── Summary ────────────────────────────────────────────────
print(f"\n{'='*55}")
if _fail[0]:
    print(f"  FAILED: {_fail[0]} / {_pass[0]+_fail[0]}")
    sys.exit(1)
else:
    print(f"  ALL {_pass[0]} CHECKS PASSED")
print(f"{'='*55}")
