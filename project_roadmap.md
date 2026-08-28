# Pulse — Phase-Wise Build Plan
*Autonomous Hackathon Concierge & Event Operations Agent*

---

## Stack Decisions

| Layer | Choice | Why |
|---|---|---|
| Frontend | React (Vite) | Given |
| Backend | FastAPI | Given |
| DB | Postgres | Given |
| Vector search | **pgvector extension on the same Postgres** | Avoids standing up a separate vector DB (Chroma/Pinecone) for a time-boxed build — one connection, one migration set, less to break live |
| LLM | Grok API (Messages API) | Used only for: drafting notification text, classifying query category, ranking mentor/teammate fit, troubleshooting-step suggestion. **Never** for deadline math, urgency score, or eligibility checks — those stay pure Python |
| Embeddings | Claude/OpenAI embedding endpoint (or `sentence-transformers` local model if you want zero extra API cost) | Feeds pgvector |
| Background sweeps | **APScheduler** (in-process, runs inside FastAPI) | No Redis/Celery needed at hackathon scale — one fewer service to deploy and demo |
| Real-time dashboard updates | **FastAPI WebSockets** | Organizer dashboard needs to visibly flip state live during demo — polling is fine as fallback but WS is the "wow" version |
| Auth | JWT, single organizer role; lightweight participant token (magic-link style or simple email+code) | Full RBAC explicitly out of scope (Version C) |
| Discord integration | `discord.py` bot as a small separate process, calls backend via internal HTTP | One channel live, per scoping decision |
| Deployment | Docker Compose (backend + Postgres + bot) locally; Vercel/Render for live demo if needed | Keep it boring and reliable |

**Tag legend used below:** `[MVP]` = must exist for the 24h core demo. `[STRETCH]` = 48h "strong version" additions. `[CUT]` = explicitly not built, mention only in vision.

---

## Phase 0 — Scaffolding & Environment (≈1–2h)

**Goal:** everything boots, empty but connected, before any feature logic.

- Monorepo structure: `/backend` (FastAPI), `/frontend` (React), `/bot` (discord.py), `/docs`.
- Postgres running via Docker Compose; enable `pgvector` extension.
- FastAPI app skeleton with health-check endpoint, CORS configured for the React dev server.
- React app skeleton (Vite + routing) with one placeholder page hitting the health-check endpoint.
- Environment/config management (`.env` for DB URL, LLM API key, JWT secret).
- Alembic (or simple SQL migration files) set up for schema versioning.

**Definition of done:** `docker compose up` brings up DB + backend; frontend fetches `/health` and renders "OK."

---

## Phase 1 — Data Model (≈2–3h) `[MVP]`

Build the full schema up front — every later phase just adds rows/logic, not new tables mid-build.

Tables (from the finalized entity list):
`Participant, Team, Event, Track, ScheduleEvent, Document, Rule (with vector column), Mentor, Issue, Notification, Submission, SubmissionRequirement, Escalation, AgentAction, ResourceItem, ResourceAllocation`

- Write SQLAlchemy models for all of the above.
- Foreign keys: Team 1—N Participant, Team 1—1 Submission, Submission N—N SubmissionRequirement via Track, Issue 1—0/1 Escalation, AgentAction references whichever entity it touched (polymorphic or nullable FK set).
- Seed script stub (fill with real data in Phase 12).

**Definition of done:** all tables migrate cleanly; can insert/query each one via a quick script.

---

## Phase 2 — Onboarding & Auth `[MVP]` (≈2h)

- `POST /participants/register` — captures name, skills[], domain preference, channel identity (Discord handle).
- `POST /teams` / `POST /teams/{id}/join` — team creation and joining, links to participants.
- Organizer login (`POST /auth/organizer/login`) → JWT.
- Participant auth: simple token issued at registration, used to scope all their later requests.
- **Row-level scoping middleware**: every participant-facing endpoint filters by `team_id` derived from their token — build this once, reuse everywhere.

**Definition of done:** can register a participant, form a team, and confirm a second participant's token cannot read the first team's data.

---

## Phase 3 — Organizer Event Setup (Admin Basics) `[MVP]` (≈2–3h)

- `POST /events`, set phase/timeline.
- `POST /tracks`, `POST /submission-requirements` (per track).
- `POST /documents` (upload rules/FAQ/rubric — store file, trigger ingestion in Phase 4).
- `POST /mentors` (roster intake: name, skills[], availability).
- `POST /resources` (bulk-create ResourceItems: hardware units, API key pool, quantities).
- Minimal admin screens in React for all of the above (plain forms/tables — no styling effort here).

**Definition of done:** organizer can fully configure one event through the UI without touching the DB directly.

---

## Phase 4 — Knowledge Engine (RAG) `[MVP]` (≈3–4h)

- Document ingestion pipeline: chunk uploaded docs → embed → store in `Rule` table with pgvector column.
- `POST /qa` endpoint: embed incoming question → similarity search top-k chunks → LLM call with retrieved context → return answer **with citation to source chunk**.
- **Confidence threshold**: if top similarity score < threshold, return "no confirmed rule found" and auto-create an `Issue` for escalation instead of guessing.
- Track/problem-statement browser: simple `GET /tracks` list surfaced in React (byproduct of ingested docs, not new pipeline).
- Sanitize ingested doc text — never let retrieved chunks be treated as instructions (strip anything that looks like a prompt injection before embedding).

**Definition of done:** ask a real question from an uploaded rules doc, get a grounded answer with a citation; ask an out-of-scope question, get "no confirmed rule" + an Issue created.

---

## Phase 5 — Submission Audit Module `[MVP]` (≈3h)

- `POST /submissions` / `PATCH /submissions/{id}` — team submits repo URL, demo link, description etc.
- Deterministic checker: compares filled fields against that track's `SubmissionRequirement` rows → computes `completeness_pct`.
- `GET /submissions/{id}/audit` — returns pass/fail per required field.
- This logic is **pure Python, no LLM** — keep it that way, it's a red-team talking point.

**Definition of done:** submitting an incomplete project correctly flags missing fields and a completeness percentage.

---

## Phase 6 — Escalation & Urgency Scoring `[MVP]` (≈2–3h)

- `Issue` creation endpoint (from Q&A low-confidence, participant-reported problem, or audit failure).
- **Urgency formula** (deterministic, pick concrete weights now, don't leave abstract):
  ```
  urgency = (severity_weight * severity)
          + (blocking_weight * is_blocking)
          + (time_weight * (1 / max(minutes_to_deadline, 1)))
  ```
  Pick starting weights (e.g. severity 0.3, blocking 0.3, time 0.4), test against 3–4 seeded scenarios, adjust until ranking feels right.
- `Escalation` table entry created when urgency crosses threshold or no deterministic fix found.
- Cooldown/max-retry: don't re-escalate the same `Issue` within N minutes or after M attempts — falls back to a standing queue item instead.
- `GET /escalations` — sorted by urgency, feeds the organizer queue view.

**Definition of done:** seeded issues produce a sensibly *ordered* escalation queue, not just a flat list.

---

## Phase 7 — Mentor Allocation `[MVP]` (≈3h)

- Query classification: LLM call labels an incoming issue's needed skill/domain (e.g. "deployment," "computer-vision").
- Match: filter `Mentor` table by skill overlap + `availability_status = available`.
- Rank candidates (simple scoring: skill overlap count, can add recency/load later).
- `POST /mentor-allocations` — creates a **proposed** (not committed) allocation, sends `Notification` to the mentor naming the requesting team + issue summary.
- One-tap accept endpoint (`PATCH /mentor-allocations/{id}/accept`).
- Timeout handling: if no response in window (e.g. 5 min, compressed for demo), re-offer to next-ranked mentor.
- No match found → creates a resourcing-gap `Escalation` to organizers (not a participant ticket).

**Definition of done:** a seeded query gets classified, matched to the right mentor, mentor gets a notification naming the team, and timeout correctly re-offers.

---

## Phase 8 — Resource Allocation & Tracking `[MVP]` (≈2h)

- `ResourceItem` pool per type (e.g. `api_key`, `hardware_kit`) with quantity/status.
- `POST /resource-requests` — checks live availability → auto-allocates next available unit → logs `ResourceAllocation` (which team holds what, when).
- Out-of-stock → flags organizer.
- Optional: overdue-return flag (allocated > N hours ago, hardware not marked returned).

**Definition of done:** requesting an API key when pool has stock succeeds and decrements; requesting when empty correctly flags organizers instead of failing silently.

---

## Phase 9 — Proactive Reminders `[MVP, keep to one sequence]` (≈2h)

- APScheduler job: periodic sweep checks each team's submission completeness vs. time-to-deadline.
- If incomplete AND under threshold time remaining → LLM drafts a **personalized** message naming the exact missing field → `Notification` sent via the live channel.
- This is the trigger for Phase 5's re-audit loop closing (see Phase 11).

**Definition of done:** one full adaptive reminder — not a generic broadcast — fires correctly on a seeded "almost deadline, missing field" team.

---

## Phase 10 — Team Formation & Matchmaking `[MVP, small]` (≈2h)

- Capability-gap logic: for an incomplete team, compare team's aggregate skills[] against track's commonly-needed skills (or against a simple required-roles list) → identify gap.
- Match against unassigned participants whose skills fill that gap.
- `GET /teams/{id}/match-suggestions` — returns ranked candidates with a one-line reasoning string.
- Keep to one working example — do not build a general optimizer.

**Definition of done:** one team with a stated skill gap gets a sensible ranked suggestion with reasoning.

---

## Phase 11 — Agent Orchestrator: The Closed Loop `[MVP — highest priority, highest risk]` (≈5–6h)

This is what ties Phases 5–9 together into the actual differentiator. Build it *after* the individual modules work standalone.

- Central orchestrator function (can be triggered by APScheduler sweep or by an incoming event/webhook):
  1. **OBSERVE** — read relevant state (submission status, issue, mentor/resource pool).
  2. **DECIDE** — run deterministic checks first (audit %, urgency formula, resource stock); call LLM only for classification/drafting/ranking sub-steps.
  3. **CHECK POLICY** — action against an explicit allow-list (notify: always allowed; escalate: always allowed; propose mentor/resource: always allowed; **roster change / disqualify / deadline edit: never autonomous, always routed to approval queue**).
  4. **ACT** — send notification / create escalation / propose allocation.
  5. **LOG** — write an `AgentAction` row: trigger snapshot, rule/policy applied, outcome.
  6. **VERIFY** — on next sweep, re-check whether the triggering condition resolved; if not, escalate further (respecting cooldown from Phase 6).
- Wire this to run for **three loop instances** using the same function: submission audit, mentor allocation, resource allocation. This reuse is your strongest "does it generalize" answer.

**Definition of done:** the Team-42 demo scenario (incomplete submission → notify → participant reports blocker → troubleshoot fails → escalate with urgency → resolved → re-audit unprompted → green) runs start to finish without manual triggering between steps.

---

## Phase 12 — Discord Integration `[MVP, one channel]` (≈3–4h)

- `discord.py` bot: listens for messages in a designated channel/DM, forwards to `POST /qa` or issue-creation endpoint, posts responses back.
- Personalized notifications (reminders, mentor proposals, escalation updates) delivered via DM to the relevant participant/mentor.
- Keep the other three channels (Slack/email/WhatsApp) as **unbuilt but architecturally trivial** — same internal notification service, different adapter. State this explicitly rather than building stubs that might break live.

**Definition of done:** a real message in Discord triggers a real RAG answer or real Issue creation; a real notification arrives as a Discord DM.

---

## Phase 13 — Organizer Dashboard (React) `[MVP]` (≈4–5h)

- Live event health view: team readiness %, open escalation count, mentor load, resource pool levels — via WebSocket for live updates.
- Escalation queue, sorted by urgency, with resolve/assign actions.
- **Approval queue** — anything the agent proposed that needs a human click (mentor allocation confirm, resource low-stock alert, any policy-gated action).
- **Explainability feed** — live-scrolling list of `AgentAction` entries in plain language, e.g. *"Allocated API key #14 to Team 42 — triggered because: request_type=api_key AND pool.available>0 AND team.eligible=true."*
- Manual override controls on any team/submission record.
- Manual "broadcast to everyone" fallback button.
- Export button (submission + audit status list as CSV).

**Definition of done:** watching the dashboard during the Phase 11 loop test, an organizer can see every step happen live without refreshing.

---

## Phase 14 — Participant-Facing UI `[MVP, minimal]` (≈2–3h)

- Simple chat widget (in-app, mirrors what Discord does) for participants without Discord.
- Team status page: own submission completeness, own escalations, resource allocations held.
- Team-matching suggestion view (Phase 10 output).

**Definition of done:** a participant can ask a question, see their own team's live status, and see a match suggestion — nothing else.

---

## Phase 15 — Seed Data & Demo Script `[MVP — do not skip]` (≈2h)

- Seed 15–20 fake teams across 2–3 tracks, varied completeness states.
- Seed 3–4 issues: one auto-resolvable, one needing escalation, one false-alarm control (proves no false positives), one mentor request.
- Seed mentor roster and resource pool with deliberately limited stock (to demo the out-of-stock path once).
- Compressed timeline option (1 real minute = 1 simulated hour) so urgency changes are visible live.
- Script out the exact Team-42 sequence from Phase 11 as a rehearsed, repeatable demo path.

**Definition of done:** the full demo sequence can be run twice in a row with consistent results.

---

## Phase 16 — Stretch (only if Phase 0–15 finish early) `[STRETCH]`

- Second real channel integration (Slack) to prove the channel-agnostic claim isn't just asserted.
- Load-test note/stub — even a simple "handled N concurrent seeded requests" number strengthens the honest "unproven at scale" answer.
- Basic RBAC beyond single organizer role.
- Schedule-change cache invalidation (flagged as a known weak spot in the original analysis — worth a real fix if time allows).

---

## Explicitly Cut `[CUT — mention in pitch only]`
- Full multi-channel (Slack/email/WhatsApp) bots.
- Deep team-matching optimization engine.
- Multi-tenant auth/role management.
- Cross-channel identity resolution.

---

## Suggested Build Order Summary (for the AI coding agent)

```
Phase 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15
```
Phases 0–3 are pure plumbing — fastest to hand to an agent with minimal ambiguity. Phases 4–10 are independent modules and can be built and tested in isolation before Phase 11 wires them into the closed loop — the loop is the highest-risk, highest-value phase, so don't attempt it until its dependencies (5, 6, 7, 8, 9) each work standalone.