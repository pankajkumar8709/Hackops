"""
Phase 3 smoke test - Organizer Event Setup.
Requires backend running on :8000.
"""
import httpx, json, sys, time, os, tempfile

BASE = "http://localhost:8000"
passed = 0
failed = 0

def h(label, r):
    print(f"\n--- {label} ---")
    print(f"  Status : {r.status_code}")
    try:
        body = json.dumps(r.json(), indent=2, default=str)[:400]
        print(f"  Body   : {body}")
    except Exception:
        print(f"  Body   : {r.text[:200]}")
    return r

def check(condition, msg):
    global passed, failed
    if not condition:
        print(f"  FAIL: {msg}"); failed += 1; return False
    print(f"  PASS: {msg}"); passed += 1; return True


print("=" * 50)
print("Phase 3 Smoke Test - Organizer Event Setup")
print("=" * 50)

with httpx.Client(base_url=BASE, timeout=15) as c:

    # 0. Organizer login
    r = c.post("/auth/organizer/login", json={"username": "organizer", "password": "pulse_admin_2026"})
    assert r.status_code == 200, "Login failed"
    OHD = {"Authorization": f"Bearer {r.json()['access_token']}"}
    print("  Organizer logged in.")

    # ─── Events ────────────────────────────────
    r = h("POST /events", c.post("/events", json={"name": "Learnathon 5.0", "timezone": "Asia/Kolkata"}, headers=OHD))
    check(r.status_code == 201, "create event: 201")
    event_id = r.json()["id"]

    r = h("GET /events", c.get("/events", headers=OHD))
    check(r.status_code == 200, "list events: 200")
    check(len(r.json()) >= 1, "at least 1 event")

    r = h("PATCH /events/{id}", c.patch(f"/events/{event_id}", json={"current_phase": "hacking"}, headers=OHD))
    check(r.status_code == 200, "update event phase: 200")
    check(r.json()["current_phase"] == "hacking", "phase updated to hacking")

    # ─── Tracks ────────────────────────────────
    r = h("POST /tracks", c.post("/tracks", json={"name": "AI/ML", "event_id": event_id}, headers=OHD))
    check(r.status_code == 201, "create track: 201")
    track_id = r.json()["id"]

    r = h("POST /tracks (2nd)", c.post("/tracks", json={"name": "Web3", "event_id": event_id}, headers=OHD))
    check(r.status_code == 201, "create track 2: 201")

    r = h("GET /tracks", c.get("/tracks", headers=OHD))
    check(r.status_code == 200, "list tracks: 200")
    check(len(r.json()) >= 2, "at least 2 tracks")

    # ─── Submission Requirements ───────────────
    r = h("POST /submission-requirements", c.post("/submission-requirements",
        json={"track_id": track_id, "field_name": "repo_url", "required": True}, headers=OHD))
    check(r.status_code == 201, "create sub-req: 201")

    r = h("POST /submission-requirements (2)", c.post("/submission-requirements",
        json={"track_id": track_id, "field_name": "demo_url", "required": True}, headers=OHD))
    check(r.status_code == 201, "create sub-req 2: 201")

    r = h("GET /submission-requirements?track_id=", c.get(f"/submission-requirements?track_id={track_id}", headers=OHD))
    check(r.status_code == 200, "list sub-reqs: 200")
    check(len(r.json()) >= 2, "at least 2 requirements for track")

    # ─── Schedule Events ──────────────────────
    r = h("POST /schedule-events", c.post("/schedule-events", json={
        "title": "Opening Ceremony",
        "start_time": "2026-09-01T09:00:00+05:30",
        "end_time": "2026-09-01T10:00:00+05:30",
        "event_id": event_id},
        headers=OHD))
    check(r.status_code == 201, "create schedule event: 201")

    r = h("GET /schedule-events", c.get(f"/schedule-events?event_id={event_id}", headers=OHD))
    check(r.status_code == 200, "list schedule events: 200")
    check(len(r.json()) >= 1, "at least 1 schedule event")

    # ─── Documents ─────────────────────────────
    # Create a temp file to upload
    tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w")
    tmp.write("Rule 1: Have fun.\nRule 2: Ship it.\n")
    tmp.close()

    with open(tmp.name, "rb") as f:
        r = h("POST /documents (upload)", c.post("/documents",
            files={"file": ("rules.txt", f, "text/plain")},
            data={"doc_type": "rules"},
            headers=OHD))
    check(r.status_code == 201, "upload document: 201")
    doc_id = r.json()["id"]

    r = h("GET /documents", c.get("/documents", headers=OHD))
    check(r.status_code == 200, "list documents: 200")
    check(len(r.json()) >= 1, "at least 1 document")

    r = h("DELETE /documents/{id}", c.delete(f"/documents/{doc_id}", headers=OHD))
    check(r.status_code == 204, "delete document: 204")

    os.unlink(tmp.name)

    # ─── Mentors ───────────────────────────────
    r = h("POST /mentors", c.post("/mentors", json={
        "name": "Dr. Smith", "skills": ["Python", "ML"], "discord_handle": "drsmith#1234"},
        headers=OHD))
    check(r.status_code == 201, "create mentor: 201")
    mentor_id = r.json()["id"]

    r = h("POST /mentors (2)", c.post("/mentors", json={
        "name": "Jane Doe", "skills": ["Go", "Cloud"]},
        headers=OHD))
    check(r.status_code == 201, "create mentor 2: 201")

    r = h("GET /mentors", c.get("/mentors", headers=OHD))
    check(r.status_code == 200, "list mentors: 200")
    check(len(r.json()) >= 2, "at least 2 mentors")

    r = h("PATCH /mentors/{id}", c.patch(f"/mentors/{mentor_id}",
        json={"availability_status": "busy"}, headers=OHD))
    check(r.status_code == 200, "update mentor: 200")
    check(r.json()["availability_status"] == "busy", "mentor status = busy")

    # ─── Resources ─────────────────────────────
    r = h("POST /resources", c.post("/resources", json={
        "name": "Groq API Key", "resource_type": "api_key", "total_quantity": 10},
        headers=OHD))
    check(r.status_code == 201, "create resource: 201")
    check(r.json()["available_quantity"] == 10, "available defaults to total")

    r = h("POST /resources/bulk", c.post("/resources/bulk", json=[
        {"name": "Jetson Nano Kit", "resource_type": "hardware_kit", "total_quantity": 5},
        {"name": "AWS Credits", "resource_type": "cloud_credits", "total_quantity": 20},
    ], headers=OHD))
    check(r.status_code == 201, "bulk create resources: 201")
    check(len(r.json()) == 2, "2 resources created in bulk")

    r = h("GET /resources", c.get("/resources", headers=OHD))
    check(r.status_code == 200, "list resources: 200")
    check(len(r.json()) >= 3, "at least 3 resource items")

    # ─── Auth guard (no token) ─────────────────
    r = h("GET /events (no token)", c.get("/events"))
    check(r.status_code == 403, "events without token: 403")


print(f"\n{'=' * 50}")
print(f"Results: {passed} passed, {failed} failed out of {passed+failed} checks")
if failed == 0:
    print("ALL PHASE 3 CHECKS PASSED")
else:
    print("SOME CHECKS FAILED")
    sys.exit(1)
print("=" * 50)
