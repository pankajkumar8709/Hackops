"""
test_phase8.py — Resource Allocation

Tests:
  1. Setup: register A, create team
  2. Organizer creates resource pool
  3. Participant GET /resources/available
  4. POST /resource-requests (request resource)
  5. GET /resource-requests/mine (team sees own allocations)
  6. Stock decremented after allocation
  7. PATCH /resource-requests/{id}/return (return resource)
  8. Stock restored after return
  9. Out-of-stock resource -> cannot allocate
 10. Organizer GET /resource-requests
 11. Row-level: other team cannot view A's allocations

Run:  python test_phase8.py
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

    header("Setup: organizer")
    r = c.post("/auth/organizer/login", json={"username": "organizer", "password": ORG_PASS})
    ok("Organizer login", r.status_code == 200)
    OHD = auth(r.json()["access_token"])

    header("Setup: register A, create team")
    email_a = f"alice_res_{_ts}@example.com"
    r = c.post("/participants/register", json={"name": "Alice Res", "email": email_a, "password": DEMO_PASS, "skills": ["Python"]})
    ok("Register A", r.status_code == 201)
    r = c.post("/auth/participant/login", json={"email": email_a, "password": DEMO_PASS})
    AHD = auth(r.json()["access_token"])

    team_name = f"ResTeam-{uuid.uuid4().hex[:6]}"
    r = c.post("/teams", headers=AHD, json={"name": team_name})
    ok("Create team", r.status_code == 201)
    team_id = r.json()["id"]

    header("1. Organizer creates resource pool")
    pool_name = f"Test Pool {uuid.uuid4().hex[:6]}"
    r = c.post("/resources", headers=OHD, json={
        "name": pool_name, "resource_type": "api_key",
        "total_quantity": 3, "available_quantity": 3,
    })
    ok("Create pool -> 201", r.status_code == 201)
    pool_id = r.json()["id"]
    ok("available_quantity = 3", r.json()["available_quantity"] == 3)

    header("2. Participant GET /resources/available")
    r = c.get("/resources/available", headers=AHD)
    ok("Returns 200", r.status_code == 200)
    pools = r.json()
    ok("Pool exists in list", any(p["id"] == pool_id for p in pools))

    header("3. POST /resource-requests (request resource)")
    r = c.post("/resource-requests", headers=AHD, json={"resource_item_id": pool_id})
    ok("Request resource -> 201", r.status_code == 201)
    alloc = r.json()
    alloc_id = alloc["id"]
    ok("Status is allocated", alloc["status"] == "allocated")

    header("4. Stock decremented")
    r = c.get("/resources/available", headers=AHD)
    pool = next(p for p in r.json() if p["id"] == pool_id)
    ok("available_quantity = 2", pool["available_quantity"] == 2, f"got {pool['available_quantity']}")

    header("5. GET /resource-requests/mine")
    r = c.get("/resource-requests/mine", headers=AHD)
    ok("Returns 200", r.status_code == 200)
    ok("Has allocations", len(r.json()) > 0)

    header("6. PATCH /resource-requests/{id}/return")
    r = c.patch(f"/resource-requests/{alloc_id}/return", headers=AHD)
    ok("Return -> 200", r.status_code == 200)
    ok("Status is returned", r.json()["status"] == "returned")

    header("7. Stock restored after return")
    r = c.get("/resources/available", headers=AHD)
    pool = next(p for p in r.json() if p["id"] == pool_id)
    ok("available_quantity = 3", pool["available_quantity"] == 3, f"got {pool['available_quantity']}")

    header("8. Out-of-stock resource -> cannot allocate")
    out_pool = c.post("/resources", headers=OHD, json={
        "name": f"Empty Pool {uuid.uuid4().hex[:6]}", "resource_type": "hardware_kit",
        "total_quantity": 1, "available_quantity": 0,
    }).json()
    r = c.post("/resource-requests", headers=AHD, json={"resource_item_id": out_pool["id"]})
    ok("Out-of-stock -> 409", r.status_code == 409)

    header("9. Organizer GET /resource-requests")
    r = c.get("/resource-requests", headers=OHD)
    ok("Returns 200", r.status_code == 200)
    ok("Returns list", isinstance(r.json(), list))

    header("10. Row-level: other team cannot view A's allocations")
    email_b = f"bob_res_{_ts}@example.com"
    r = c.post("/participants/register", json={"name": "Bob Res", "email": email_b, "password": DEMO_PASS, "skills": []})
    ok("Register B", r.status_code == 201)
    r = c.post("/auth/participant/login", json={"email": email_b, "password": DEMO_PASS})
    BHD = auth(r.json()["access_token"])
    r = c.post("/teams", headers=BHD, json={"name": f"Other-{uuid.uuid4().hex[:6]}"})
    ok("B creates team", r.status_code == 201)
    r = c.get("/resource-requests/mine", headers=BHD)
    ok("B's mine is empty (no allocations)", len(r.json()) == 0)

print(f"\n{'='*55}")
if _fail[0]:
    print(f"  FAILED: {_fail[0]} / {_pass[0]+_fail[0]}")
    sys.exit(1)
else:
    print(f"  ALL {_pass[0]} CHECKS PASSED")
print(f"{'='*55}")
