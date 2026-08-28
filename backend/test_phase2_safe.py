"""
Phase 2 smoke test (Windows-safe, no Unicode issues).
Requires backend to be running on :8000.
"""
import httpx, json, sys, time, os

os.environ["PYTHONIOENCODING"] = "utf-8"
BASE = "http://localhost:8000"
passed = 0
failed = 0

def h(label, r):
    print(f"\n--- {label} ---")
    print(f"  Status : {r.status_code}")
    try:
        print(f"  Body   : {json.dumps(r.json(), indent=2)[:400]}")
    except Exception:
        print(f"  Body   : {r.text[:200]}")
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


print("=" * 50)
print("Phase 2 Smoke Test - Onboarding & Auth")
print("=" * 50)

ts = int(time.time())

with httpx.Client(base_url=BASE, timeout=15) as c:

    # 1. Health
    r = h("GET /health", c.get("/health"))
    check(r.status_code == 200, "/health returns 200")
    check(r.json()["version"] == "0.2.0", "version = 0.2.0")

    # 2. Organizer login (correct)
    r = h("POST /auth/organizer/login", c.post("/auth/organizer/login",
        json={"username": "organizer", "password": "pulse_admin_2026"}))
    check(r.status_code == 200, "organizer login 200")
    org_token = r.json()["access_token"]
    OHD = {"Authorization": f"Bearer {org_token}"}

    # 3. Wrong organizer password
    r = h("Wrong organizer password", c.post("/auth/organizer/login",
        json={"username": "organizer", "password": "wrong"}))
    check(r.status_code == 401, "wrong password -> 401")

    # 4. Register participant A
    r = h("Register Participant A", c.post("/participants/register",
        json={"name": "Alice", "email": f"alice_{ts}@example.com",
              "skills": ["Python", "ML"], "discord_handle": "alice#0001"}))
    check(r.status_code == 201, "register A: 201")
    token_a = r.json()["token"]
    AHD = {"Authorization": f"Bearer {token_a}"}

    # 5. Duplicate email
    r = h("Duplicate email", c.post("/participants/register",
        json={"name": "Alice2", "email": f"alice_{ts}@example.com", "skills": []}))
    check(r.status_code == 409, "duplicate email -> 409")

    # 6. Register participant B
    r = h("Register Participant B", c.post("/participants/register",
        json={"name": "Bob", "email": f"bob_{ts}@example.com", "skills": ["Go"]}))
    check(r.status_code == 201, "register B: 201")
    token_b = r.json()["token"]
    BHD = {"Authorization": f"Bearer {token_b}"}

    # 7. GET /participants/me
    r = h("GET /participants/me (A)", c.get("/participants/me", headers=AHD))
    check(r.status_code == 200, "/participants/me returns 200")
    check("Alice" in r.json()["name"], "/me returns correct participant")

    # 8. Create team as A
    r = h("POST /teams (A creates Team Alpha)", c.post("/teams",
        json={"name": f"Team Alpha {ts}"}, headers=AHD))
    check(r.status_code == 201, "create team: 201")
    team_id = r.json()["id"]

    # 9. A tries to create another team (should 409)
    r = h("A tries second team", c.post("/teams",
        json={"name": "Second"}, headers=AHD))
    check(r.status_code == 409, "already in team -> 409")

    # 10. B joins Team Alpha
    r = h(f"POST /teams/{team_id}/join (B joins)", c.post(f"/teams/{team_id}/join", headers=BHD))
    check(r.status_code == 200, "B joins team: 200")

    # 11. GET /teams/mine (A)
    r = h("GET /teams/mine (A)", c.get("/teams/mine", headers=AHD))
    check(r.status_code == 200, "/teams/mine returns 200")
    check(r.json()["id"] == team_id, "A's team ID matches")

    # 12. Organizer can list all teams
    r = h("GET /teams (organizer)", c.get("/teams", headers=OHD))
    check(r.status_code == 200, "organizer GET /teams: 200")
    check(isinstance(r.json(), list), "returns list")

    # 13. Participant CANNOT list all teams (forbidden)
    r = h("GET /teams (participant A - should 403)", c.get("/teams", headers=AHD))
    check(r.status_code == 403, "participant cannot list all teams -> 403")

    # 14. Organizer can list all participants
    r = h("GET /participants (organizer)", c.get("/participants", headers=OHD))
    check(r.status_code == 200, "organizer GET /participants: 200")

    # 15. No token -> 403
    r = h("GET /participants/me (no token)", c.get("/participants/me"))
    check(r.status_code == 403, "no token -> 403")


print(f"\n{'=' * 50}")
print(f"Results: {passed} passed, {failed} failed out of {passed+failed} checks")
if failed == 0:
    print("ALL PHASE 2 CHECKS PASSED")
else:
    print(f"SOME CHECKS FAILED")
    sys.exit(1)
print("=" * 50)
