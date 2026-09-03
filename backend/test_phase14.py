#!/usr/bin/env python3
"""Phase 14 smoke test -- Participant-Facing UI.

Tests all participant-facing endpoints used by the React frontend:
registration, team status, chat (Q&A), issues, notifications, match suggestions.
"""
import httpx
import sys
import os
os.environ["PYTHONIOENCODING"] = "utf-8"

BASE = "http://localhost:8000"
PARTICIPANT_TOKEN = None
TEAM_ID = None
passed = 0
failed = 0


def ok(label, condition=True):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {label}")
    else:
        failed += 1
        print(f"  FAIL: {label}")


def headers():
    return {"Authorization": f"Bearer {PARTICIPANT_TOKEN}", "Content-Type": "application/json"}


def run_tests():
    global PARTICIPANT_TOKEN, TEAM_ID

    print("\n" + "=" * 60)
    print("  Phase 14 -- Participant-Facing UI")
    print("=" * 60)

    # ─── 1. Register participant ────────────────────
    print("\n[REGISTER] Participant Registration")
    import time
    suffix = str(int(time.time() * 1000))[-6:]
    r = httpx.post(f"{BASE}/participants/register", json={
        "name": f"Phase14 Participant {suffix}",
        "email": f"p14_{suffix}@test.com",
        "skills": ["python", "react", "fastapi"],
        "track_pref": "ai",
        "discord_handle": f"p14tester_{suffix}",
    }, timeout=30)
    ok("POST /participants/register returns 201", r.status_code == 201)
    data = r.json()
    ok("Response has token", "token" in data)
    ok("Response has id", "id" in data)
    ok("Response has name", data.get("name", "").startswith("Phase14"))
    PARTICIPANT_TOKEN = data["token"]
    participant_id = data["id"]
    ok("Token is a string", isinstance(PARTICIPANT_TOKEN, str) and len(PARTICIPANT_TOKEN) > 10)

    # ─── 2. Get profile ─────────────────────────────
    print("\n[PROFILE] Participant Profile")
    r = httpx.get(f"{BASE}/participants/me", headers=headers(), timeout=30)
    ok("GET /participants/me returns 200", r.status_code == 200)
    me = r.json()
    ok("Profile has name", me.get("name", "").startswith("Phase14"))
    ok("Profile has skills", isinstance(me.get("skills"), list))
    ok("Profile has team_id (null initially)", me.get("team_id") is None)

    # ─── 3. Create team ─────────────────────────────
    print("\n[TEAM] Team Creation")
    r = httpx.post(f"{BASE}/teams", headers=headers(), json={
        "name": f"Phase14 Team {suffix}",
    }, timeout=30)
    ok("POST /teams returns 201", r.status_code == 201)
    team = r.json()
    TEAM_ID = team["id"]
    ok("Team has id", "id" in team)
    ok("Team has name", team.get("name", "").startswith("Phase14"))
    ok("Team submission_status is not_submitted", team.get("submission_status") == "not_submitted")
    ok("Team readiness_pct is 0.0", team.get("readiness_pct") == 0.0)

    # ─── 4. Get my team ─────────────────────────────
    print("\n[TEAM MINE] Get My Team")
    r = httpx.get(f"{BASE}/teams/mine", headers=headers(), timeout=30)
    ok("GET /teams/mine returns 200", r.status_code == 200)
    mine = r.json()
    ok("My team has correct name", mine.get("name", "").startswith("Phase14"))
    ok("My team id matches created team", mine.get("id") == TEAM_ID)

    # ─── 5. Submit project ──────────────────────────
    print("\n[SUBMISSION] Create Submission")
    r = httpx.post(f"{BASE}/submissions", headers=headers(), json={
        "repo_url": "https://github.com/test/phase14-project",
        "demo_url": "https://demo.phase14.test.com",
        "description": "Phase14 test project - AI hackathon submission",
    }, timeout=30)
    ok("POST /submissions returns 201", r.status_code == 201)
    sub = r.json()
    ok("Submission has id", "id" in data)
    ok("Submission has repo_url", "repo_url" in sub)
    ok("Submission has completeness_pct", "completeness_pct" in sub)
    sub_id = sub.get("id")

    # ─── 6. Get my submission ───────────────────────
    print("\n[SUBMISSION MINE] Get My Submission")
    r = httpx.get(f"{BASE}/submissions/mine", headers=headers(), timeout=30)
    ok("GET /submissions/mine returns 200", r.status_code == 200)
    my_sub = r.json()
    ok("My submission has repo_url", "github.com" in (my_sub.get("repo_url") or ""))

    # ─── 7. Report issue ────────────────────────────
    print("\n[ISSUE] Report Issue")
    r = httpx.post(f"{BASE}/issues", headers=headers(), json={
        "description": "Phase14 test issue - can't deploy to cloud",
        "category": "technical",
        "severity": 0.7,
        "is_blocking": True,
    }, timeout=30)
    ok("POST /issues returns 201", r.status_code == 201)
    issue = r.json()
    ok("Issue has id", "id" in issue)
    ok("Issue has urgency_score", "urgency_score" in issue)
    ok("Issue has status", issue.get("status") in ["open", "escalated"])

    # ─── 8. Get my issues ───────────────────────────
    print("\n[ISSUES MINE] Get My Issues")
    r = httpx.get(f"{BASE}/issues/mine", headers=headers(), timeout=30)
    ok("GET /issues/mine returns 200", r.status_code == 200)
    my_issues = r.json()
    ok("Issues list is a list", isinstance(my_issues, list))
    ok("Issues count >= 1", len(my_issues) >= 1)
    ok("Our issue is in the list", any("Phase14" in (i.get("description") or "") for i in my_issues))

    # ─── 9. Get notifications ───────────────────────
    print("\n[NOTIFICATIONS] Get My Notifications")
    r = httpx.get(f"{BASE}/notifications/mine", headers=headers(), timeout=30)
    ok("GET /notifications/mine returns 200", r.status_code == 200)
    notifs = r.json()
    ok("Notifications is a list", isinstance(notifs, list))

    # ─── 10. Get resource allocations ───────────────
    print("\n[RESOURCES] Get My Resource Allocations")
    r = httpx.get(f"{BASE}/resource-requests/mine", headers=headers(), timeout=30)
    ok("GET /resource-requests/mine returns 200", r.status_code == 200)
    resources = r.json()
    ok("Resource allocations is a list", isinstance(resources, list))

    # ─── 11. Match suggestions ──────────────────────
    print("\n[MATCHES] Match Suggestions")
    r = httpx.get(f"{BASE}/teams/{TEAM_ID}/match-suggestions", headers=headers(), timeout=30)
    ok("GET /teams/{id}/match-suggestions returns 200", r.status_code == 200)
    matches = r.json()
    ok("Has gap_analysis field", "gap_analysis" in matches or "skill_gaps" in matches)
    ok("Has candidates field", "candidates" in matches)
    ok("Candidates is a list", isinstance(matches.get("candidates"), list))

    # ─── 12. Mark notification read ─────────────────
    if notifs:
        notif_id = notifs[0]["id"]
        print("\n[NOTIFICATION READ] Mark as Read")
        r = httpx.patch(f"{BASE}/notifications/{notif_id}/read", headers=headers(), timeout=30)
        ok("PATCH /notifications/{id}/read returns 200", r.status_code == 200)
        marked = r.json()
        ok("Notification read field is True", marked.get("read") is True)

    # ─── 13. Q&A (chat) ────────────────────────────
    print("\n[CHAT] Q&A Endpoint")
    r = httpx.post(f"{BASE}/qa", headers={"Content-Type": "application/json"}, json={
        "question": "What is this hackathon about?",
        "participant_id": participant_id,
        "team_id": TEAM_ID,
    }, timeout=60)
    ok("POST /qa returns 200", r.status_code == 200)
    qa = r.json()
    ok("QA has answer field", "answer" in qa)
    ok("QA has confident field", "confident" in qa)
    ok("QA has citations field", "citations" in qa)
    ok("Answer is a string", isinstance(qa.get("answer"), str) and len(qa.get("answer", "")) > 0)

    # ─── 14. Auth protection ────────────────────────
    print("\n[AUTH] Participant Auth Protection")
    r = httpx.get(f"{BASE}/teams/mine")
    ok("Unauthenticated request returns 403", r.status_code == 403)

    r = httpx.get(f"{BASE}/teams/mine", headers={"Authorization": "Bearer fake_token"})
    ok("Invalid token returns 401", r.status_code == 401)

    # ─── 15. Cross-team scoping ─────────────────────
    print("\n[SCOPING] Row-Level Scoping")
    # Register another participant
    suffix2 = str(int(time.time() * 1000))[-6:]
    r2 = httpx.post(f"{BASE}/participants/register", json={
        "name": f"Phase14 Other {suffix2}",
        "email": f"p14_other_{suffix2}@test.com",
        "skills": ["javascript"],
    }, timeout=30)
    other_token = r2.json()["token"]
    other_headers = {"Authorization": f"Bearer {other_token}", "Content-Type": "application/json"}

    r = httpx.get(f"{BASE}/teams/{TEAM_ID}/match-suggestions", headers=other_headers, timeout=30)
    ok("Other participant can't view our match suggestions (403)", r.status_code == 403)

    r = httpx.get(f"{BASE}/submissions/mine", headers=other_headers, timeout=30)
    ok("Other participant has no submission (404)", r.status_code == 404)

    return passed, failed


if __name__ == "__main__":
    p, f = run_tests()
    print("\n" + "=" * 60)
    print(f"  Phase 14 Results: {p} passed, {f} failed")
    print("=" * 60)
    sys.exit(1 if f > 0 else 0)
