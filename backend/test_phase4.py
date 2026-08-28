"""
Phase 4 smoke test — Knowledge Engine (RAG)
Run with:
    python test_phase4.py
Requires backend to be running on :8000.
"""
import httpx
import json
import sys

BASE = "http://localhost:8000"


def h(label, r):
    print(f"\n{'=' * 50}")
    print(f">> {label}")
    print(f"  Status : {r.status_code}")
    try:
        print(f"  Body   : {json.dumps(r.json(), indent=2)[:500]}")
    except Exception:
        print(f"  Body   : {r.text[:300]}")
    return r


def check(condition, msg):
    if not condition:
        print(f"\nFAIL: {msg}")
        sys.exit(1)
    print(f"  PASS: {msg}")


# --- Sample rules document ---
SAMPLE_RULES = """# Hackathon Rules & FAQ

## Submission Deadline
All submissions must be made by 11:59 PM IST on the final day of the hackathon.
Late submissions will not be accepted under any circumstances.

## Team Size
Each team must have between 2 and 5 members. Solo submissions are not allowed.

## Code of Conduct
All participants must adhere to the code of conduct. Harassment, cheating, or
plagiarism will result in immediate disqualification.

## Technology Stack
Teams are free to use any technology stack. However, all code must be written
during the hackathon period. Pre-existing code is not allowed unless it is
a publicly available open-source library.

## Judging Criteria
Projects will be judged on:
1. Innovation (30%)
2. Technical Complexity (25%)
3. Impact & Usefulness (25%)
4. Presentation & Demo (20%)

## Prizes
First place: $5,000
Second place: $3,000
Third place: $1,000
All participants receive certificates of participation.

## Mentors
Mentors are available throughout the event. Use the /mentor command to request help.

## Resources
GPU credits and API keys are available on a first-come, first-served basis.
Request through the resource allocation portal.
"""


print("=" * 50)
print("Phase 4 Smoke Test — Knowledge Engine (RAG)")
print("=" * 50)

with httpx.Client(base_url=BASE, timeout=120) as c:

    # 1. Health check
    r = h("GET /health", c.get("/health"))
    check(r.status_code == 200, "/health returns 200")
    check(r.json()["version"] == "0.4.0", "version = 0.4.0")

    # 2. Organizer login
    r = h("POST /auth/organizer/login", c.post("/auth/organizer/login",
        json={"username": "organizer", "password": "pulse_admin_2026"}))
    check(r.status_code == 200, "organizer login 200")
    org_token = r.json()["access_token"]
    OHD = {"Authorization": f"Bearer {org_token}"}

    # 3. Upload a rules document
    r = h("POST /documents/upload (rules.txt)", c.post(
        "/documents/upload",
        headers=OHD,
        params={"doc_type": "rules"},
        files={"file": ("hackathon_rules.txt", SAMPLE_RULES.encode(), "text/plain")},
    ))
    check(r.status_code == 201, "document upload: 201")
    doc = r.json()
    check(doc["ingested_at"] is not None, "document was ingested (ingested_at set)")
    check(doc["chunk_count"] > 0, f"produced {doc['chunk_count']} chunks")
    doc_id = doc["id"]

    # 4. List documents
    r = h("GET /documents", c.get("/documents", headers=OHD))
    check(r.status_code == 200, "list documents: 200")
    check(len(r.json()) >= 1, "at least 1 document listed")

    # 5. Get single document
    r = h(f"GET /documents/{doc_id}", c.get(f"/documents/{doc_id}", headers=OHD))
    check(r.status_code == 200, "get document: 200")
    check(r.json()["id"] == doc_id, "correct document returned")

    # 6. Q&A — question that MATCHES the rules
    r = h("POST /qa (matching question)", c.post("/qa", json={
        "question": "What is the submission deadline for the hackathon?"
    }))
    check(r.status_code == 200, "Q&A: 200")
    qa = r.json()
    check(qa["confident"] is True, "confident = true (rules match)")
    check(len(qa["citations"]) > 0, f"has {len(qa['citations'])} citation(s)")
    check("deadline" in qa["answer"].lower() or "11:59" in qa["answer"],
          "answer mentions deadline or time")
    print(f"  Answer: {qa['answer'][:200]}...")

    # 7. Q&A — completely unrelated question (should be low confidence)
    r = h("POST /qa (unrelated question)", c.post("/qa", json={
        "question": "What is the capital of Jupiter's third moon?"
    }))
    check(r.status_code == 200, "Q&A unrelated: 200")
    qa2 = r.json()
    check(qa2["confident"] is False, "confident = false (no matching rules)")
    check(qa2["issue_id"] is not None, "auto-created Issue for low-confidence query")
    print(f"  Issue ID: {qa2['issue_id']}")

    # 8. GET /tracks — simple track browser
    r = h("GET /tracks", c.get("/tracks"))
    check(r.status_code == 200, "GET /tracks: 200")
    check(isinstance(r.json(), list), "returns a list")

print("\n" + "=" * 50)
print("ALL PHASE 4 CHECKS PASSED")
print("=" * 50)
