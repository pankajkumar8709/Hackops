"""
Phase 2 smoke test — run with:
    python test_phase2.py
Requires backend to be running on :8000.
"""
import httpx, json, sys

BASE = "http://localhost:8000"

def h(label, r):
    print(f"\n{'─'*50}")
    print(f"▶ {label}")
    print(f"  Status : {r.status_code}")
    try:
        print(f"  Body   : {json.dumps(r.json(), indent=2)[:400]}")
    except Exception:
        print(f"  Body   : {r.text[:200]}")
    return r

def check(condition, msg):
    if not condition:
        print(f"\n❌ FAIL: {msg}"); sys.exit(1)
    print(f"  ✅ {msg}")


print("=" * 50)
print("Phase 2 Smoke Test — Onboarding & Auth")
print("=" * 50)

with httpx.Client(base_url=BASE, timeout=15) as c:

    # 1. Health
    r = h("GET /health", c.get("/health"))
    check(r.status_code == 200, "/health returns 200")
    check(r.json()["version"] == "0.2.0", "version = 0.2.0")

    # 2. Organizer login
    r = h("POST /auth/organizer/login", c.post("/auth/organizer/login",
        json={"username": "organizer", "password": "pulse_admin_2026"}))
    check(r.status_code == 200, "organizer login 200")
    org_token = r.json()["access_token"]
    OHD = {"Authorization": f"Bearer {org_token}"}

    # 3. Wrong organizer password
    r = h("Wrong organizer password", c.post("/auth/organizer/login",
        json={"username": "organizer", "password": "wrong"}))
    check(r.status_code == 401, "wrong password → 401")

    # 4. Register participant A
    import time; ts = int(time.time())
    r = h("Register Participant A", c.post("/participants/register",
        json={"name": "Alice", "email": f"alice_{ts}@example.com",
              "skills": ["Python", "ML"], "discord_handle": "alice#0001"}))
    check(r.status_code == 201, "register A: 201")
    token_a = r.json()["token"]
    AHD = {"Authorization": f"Bearer {token_a}"}

    # 5. Register participant B
    r = h("Register Participant B", c.post("/participants/register",
        json={"name": "Bob", "email": f"bob_{ts}@example.com", "skills": ["Go"]}))
    check(r.status_code == 201, "register B: 201")
    token_b = r.json()["token"]
    BHD = {"Authorization": f"Bearer {token_b}"}

    # 6. GET /participants/me
    r = h("GET /participants/me (A)", c.get("/participants/me", headers=AHD))
    check(r.status_code == 200, "/participants/me returns participant A")

    # 7. Create team as A
    r = h("POST /teams (A creates Team Alpha)", c.post("/teams",
        json={"name": "Team Alpha"}, headers=AHD))
    check(r.status_code in (201, 409), "create team: 201 or 409")
    if r.status_code == 201:
        team_id = r.json()["id"]
    else:
        # A is already in a team — get it
        r2 = c.get("/teams/mine", headers=AHD)
        team_id = r2.json()["id"]

    # 8. B joins Team Alpha
    r = h(f"POST /teams/{team_id}/join (B joins)", c.post(f"/teams/{team_id}/join", headers=BHD))
    check(r.status_code in (200, 409), "B joins team: 200 or 409")

    # 9. Row-level isolation: A's /teams/mine only returns A's team
    r = h("GET /teams/mine (A)", c.get("/teams/mine", headers=AHD))
    check(r.status_code == 200, "/teams/mine returns A's team")
    check(r.json()["id"] == team_id, "A's team ID matches")

    # 10. Organizer can list all teams
    r = h("GET /teams (organizer)", c.get("/teams", headers=OHD))
    check(r.status_code == 200, "organizer GET /teams: 200")
    check(isinstance(r.json(), list), "returns list")

    # 11. Participant CANNOT list all teams (forbidden)
    r = h("GET /teams (participant A — should 403)", c.get("/teams", headers=AHD))
    check(r.status_code == 403, "participant cannot list all teams → 403")

print("\n" + "=" * 50)
print("✅  ALL PHASE 2 CHECKS PASSED")
print("=" * 50)
