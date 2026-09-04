# ⚡ Pulse — Autonomous Hackathon Concierge & Event Operations Agent

> An AI-powered event operations agent that autonomously manages hackathon logistics: team formation, submission auditing, escalation triage, mentor allocation, resource tracking, and proactive reminders — all through a closed-loop orchestrator with full explainability.

---

## 🎯 What is Pulse?

Pulse is a **fully autonomous hackathon concierge** built for the [Learnathon 5.0 HackOps hackathon](https://github.com). It replaces the manual coordination burden that organizers face — answering repeated questions, tracking submission completeness, matching mentors to problems, managing limited resources, and sending deadline reminders — with an intelligent agent that observes, decides, acts, and explains itself.

### Key Differentiators

| Feature | How it works |
|---|---|
| **Deterministic-first** | Urgency scoring, submission auditing, resource allocation, and matchmaking are pure Python — no LLM needed. LLM is only used for classification, message drafting, and Q&A. |
| **Closed-loop orchestrator** | The same `OBSERVE → DECIDE → POLICY → ACT → LOG → VERIFY` function handles submission audits, mentor allocation, and resource allocation. |
| **Full explainability** | Every autonomous action logs trigger state, reasoning trace, policy check, and outcome to an `AgentAction` table — viewable live on the dashboard. |
| **Policy engine** | Explicit allow-list (notify, escalate, propose) vs. restricted actions (roster change, disqualify, deadline edit) — restricted actions always go to the approval queue. |
| **Channel-agnostic notifications** | Same notification service, different adapter — Discord bot is live; Slack/email/WhatsApp are architecturally trivial to add. |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        PULSE ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   Frontend   │    │   Backend    │    │   Discord    │       │
│  │  React/Vite  │───▶│   FastAPI    │◀───│  discord.py  │       │
│  │  Port 5173   │    │  Port 8000   │    │   Bot        │       │
│  └──────────────┘    └──────┬───────┘    └──────────────┘       │
│                             │                                    │
│                    ┌────────▼────────┐                           │
│                    │   PostgreSQL    │                           │
│                    │  + pgvector     │                           │
│                    │   (Neon DB)     │                           │
│                    └─────────────────┘                           │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  SERVICES (Python modules in backend/app/services/)             │
│                                                                  │
│  • orchestrator.py   — Closed-loop engine (Phases 5-11)        │
│  • urgency.py        — Deterministic urgency scoring (Phase 6) │
│  • audit.py          — Submission audit checker (Phase 5)       │
│  • mentor_allocation.py — Skill classification + matching (7)  │
│  • resource_allocation.py — Stock tracking + allocation (8)    │
│  • reminder.py       — Proactive reminder sweep (Phase 9)      │
│  • matchmaking.py    — Team formation suggestions (Phase 10)   │
│  • qa.py             — RAG question answering (Phase 4)        │
│  • notification_delivery.py — Channel-agnostic delivery (12)   │
│  • embeddings.py     — Sentence-transformer embeddings          │
│  • ingestion.py      — Document chunking + embedding storage   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **PostgreSQL** (or a free [Neon](https://neon.tech) / [Supabase](https://supabase.com) account)
- **Groq API key** (free tier — [console.groq.com](https://console.groq.com))

### 1. Database Setup

Create a free PostgreSQL database (e.g., on Neon), then run in the SQL editor:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2. Environment Configuration

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db?sslmode=require
DATABASE_SYNC_URL=postgresql+psycopg2://user:pass@host:5432/db?sslmode=require
GROQ_API_KEY=gsk_your_groq_api_key_here
JWT_SECRET=any_long_random_string_here
EMBEDDING_MODEL=all-MiniLM-L6-v2
FRONTEND_ORIGIN=http://localhost:5173

# Discord (optional — only needed for Phase 12 bot)
DISCORD_TOKEN=your_discord_bot_token
DISCORD_CHANNEL_ID=your_channel_id
BACKEND_URL=http://localhost:8000
```

### 3. Backend

```bash
cd backend
pip install -r requirements.txt

# Start the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend is now running at `http://localhost:8000`. Check with:

```bash
curl http://localhost:8000/health
# → {"status":"ok","service":"pulse-backend","version":"1.2.0"}
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

The React app is now running at `http://localhost:5173`.

### 5. Seed Demo Data (Phase 15)

```bash
cd backend
python seed_data.py
```

This creates:
- 1 event with compressed timeline (8h deadline)
- 3 tracks (AI/ML, Web/Fullstack, Hardware/IoT)
- 18 teams across tracks with varied completeness
- 46 participants (password: `demo1234`)
- 5 mentors (4 available, 1 busy)
- 5 resource pools (one deliberately out of stock)
- 4 issue scenarios (auto-resolvable, escalation, false-alarm, mentor-request)

### 6. Discord Bot (Optional)

```bash
cd backend
python -m bot.pulse_bot
```

Requires `DISCORD_TOKEN` in `.env`.

---

## 📋 Features by Phase

### Phase 0 — Scaffolding & Environment
- Monorepo: `/backend`, `/frontend`, `/bot`, `/docs`
- FastAPI skeleton with CORS, health check
- React Vite app with routing
- `.env` configuration management

### Phase 1 — Data Model
- 16 SQLAlchemy models: `Participant`, `Team`, `Event`, `Track`, `ScheduleEvent`, `Document`, `Rule` (pgvector), `Mentor`, `Issue`, `Notification`, `Submission`, `SubmissionRequirement`, `Escalation`, `AgentAction`, `ResourceItem`, `ResourceAllocation`
- `Participant` model: `email`, `password_hash` (bcrypt), `token_hash` (legacy), `team_id` FK
- Full foreign key relationships with row-level scoping

### Phase 2 — Onboarding & Auth
- `POST /participants/register` — captures name, email, password, skills[], domain preference, Discord handle
- `POST /auth/participant/login` — email + password → JWT
- `POST /teams` / `POST /teams/{id}/join` — team creation and joining
- `POST /auth/organizer/login` → JWT
- Participant JWT with `team_id` scoping
- **Row-level scoping middleware** — every participant endpoint filters by their team
- Passwords hashed with bcrypt (never stored in plaintext)
- Rate limiting on auth endpoints (5 attempts/min/IP)

### Phase 3 — Organizer Event Setup
- `POST /events`, `POST /tracks`, `POST /submission-requirements`
- `POST /documents` (upload + ingestion trigger)
- `POST /mentors` (roster intake)
- `POST /resources` (bulk-create with quantities)

### Phase 4 — Knowledge Engine (RAG)
- Document ingestion pipeline: chunk → embed → store in pgvector
- `POST /qa` — embed question → similarity search → LLM answer with citations
- **Confidence threshold** — low-confidence → auto-create Issue for escalation
- Prompt injection sanitization on ingested documents

### Phase 5 — Submission Audit Module
- `POST /submissions` / `PATCH /submissions/{id}`
- **Deterministic completeness checker** — compares fields against track requirements
- `GET /submissions/{id}/audit` — pass/fail per required field
- Pure Python, zero LLM calls

### Phase 6 — Escalation & Urgency Scoring
- `POST /issues` — participant-reported problems
- **Deterministic urgency formula**:
  ```
  urgency = (severity × 0.3) + (blocking × 0.3) + (time_weight × 0.4)
  ```
- Auto-escalation when urgency crosses threshold
- Cooldown/max-retry: no re-escalation within N minutes
- `GET /escalations` — sorted queue for organizer dashboard

### Phase 7 — Mentor Allocation
- **LLM skill classification** (Groq API) with 1s timeout + keyword fallback
- `POST /mentor-allocations` — creates proposed allocation
- `PATCH /mentor-allocations/{id}/accept` — one-tap accept
- Timeout handling: re-offers to next-ranked mentor
- No match → escalation to organizers

### Phase 8 — Resource Allocation & Tracking
- `POST /resource-requests` — checks live availability → auto-allocate
- Live stock tracking (decrement on allocate, increment on return)
- Out-of-stock → flags organizer dashboard
- Overdue detection (allocated > threshold hours)

### Phase 9 — Proactive Reminders
- `POST /reminders/sweep` — checks team submissions vs. deadlines
- LLM-drafted personalized messages naming exact missing fields
- Deadline-aware: only reminds within configurable hours
- Dry-run mode for testing
- `GET /notifications/mine` — participant notification inbox

### Phase 10 — Team Formation & Matchmaking
- `GET /teams/{id}/match-suggestions`
- Skill gap analysis (word-boundary regex matching)
- Candidate scoring (0.0–1.0) by gap-fill capability
- Ranked candidates with one-line reasoning

### Phase 11 — Agent Orchestrator (The Closed Loop)
- **Same function** for 3 loop instances: submission audit, mentor allocation, resource allocation
- `OBSERVE → DECIDE → POLICY → ACT → LOG → VERIFY`
- Policy engine: allow-list vs. restricted actions (→ approval queue)
- `AgentAction` table: trigger snapshot, reasoning, policy check, outcome
- `POST /orchestrator/run` — single instance
- `POST /orchestrator/sweep` — full sweep across all teams/issues

### Phase 12 — Discord Integration
- `discord.py` bot: message listener, 6 commands, DM sender
- Commands: `!ask`, `!issue`, `!status`, `!escalations`, `!mentor`, `!commands`
- Bot polling loop: checks pending notifications → delivers via DM
- Channel-agnostic adapter (same service, different channel)

### Phase 13 — Organizer Dashboard (React)
- **Live health view**: team readiness %, escalation count, mentor load, resource pools
- **Escalation queue**: sorted by urgency, one-click resolve
- **Approval queue**: agent-proposed actions needing human click
- **Explainability feed**: live agent action log with reasoning
- **Manual overrides**: team/submission record overrides
- **Broadcast**: send messages to all participants
- **CSV export**: submissions + audit status
- **WebSocket** for live updates (30s polling fallback)

### Phase 14 — Participant-Facing UI
- **Chat widget**: in-app chat mirroring Discord, calls RAG pipeline
- **Team status**: submission completeness, issues, resources, notifications
- **Match suggestions**: Phase 10 matchmaking with skill gap analysis
- Password-based auth (email + password)

### Phase 15 — Seed Data & Demo Script
- 18 teams, 46 participants, 5 mentors, 5 resource pools, 4 issues
- Demo password: `demo1234` (all seeded participants)
- Compressed timeline (1 real minute = 1 simulated hour)
- `demo_script.py` — rehearseable Team-42 closed-loop sequence
- Full reproducibility check (run twice, same results)

---

## 🔌 API Reference

### Authentication

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/auth/organizer/login` | POST | None | Login as organizer → JWT |
| `/auth/participant/login` | POST | None | Login participant (email + password) → JWT |
| `/participants/register` | POST | None | Register participant (email + password) |
| `/participants/me` | GET | Participant | Get own profile |

### Core Endpoints

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/health` | GET | None | Backend health check |
| `/events` | GET/POST | Organizer | Manage events |
| `/tracks` | GET/POST | Organizer | Manage tracks |
| `/submission-requirements` | GET/POST | Organizer | Track requirements |
| `/documents` | POST | Organizer | Upload documents (triggers ingestion) |
| `/mentors` | GET/POST | Organizer | Mentor roster |
| `/resources` | GET/POST | Organizer | Resource pool management |

### Team & Participant

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/teams` | GET/POST | Org/Part | List/create teams |
| `/teams/mine` | GET | Participant | Get own team |
| `/teams/{id}/join` | POST | Participant | Join team |
| `/teams/{id}/match-suggestions` | GET | Participant | Match suggestions |

### Submission & Audit

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/submissions` | GET/POST | Org/Part | Submit project |
| `/submissions/mine` | GET | Participant | Own submission |
| `/submissions/{id}` | GET/PATCH | Participant | View/update submission |
| `/submissions/{id}/audit` | GET | Participant | Run deterministic audit |

### Issues & Escalations

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/issues` | POST | Participant | Report an issue |
| `/issues/mine` | GET | Participant | Own issues |
| `/escalations` | GET | Organizer | Escalation queue |
| `/escalations/{id}/resolve` | PATCH | Organizer | Resolve escalation |

### Mentor Allocation

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/mentor-allocations` | POST | Participant | Request mentor |
| `/mentor-allocations/mine` | GET | Participant | Own allocations |
| `/mentor-allocations/{id}/accept` | PATCH | Participant | Accept allocation |
| `/mentor-allocations/{id}/decline` | PATCH | Participant | Decline allocation |
| `/mentor-allocations/check-timeouts` | POST | Organizer | Trigger timeout check |

### Resource Allocation

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/resource-requests` | POST | Participant | Request resource |
| `/resource-requests/mine` | GET | Participant | Own allocations |
| `/resource-requests/{id}/return` | PATCH | Participant | Return resource |
| `/resource-pools` | GET | Organizer | Pool summary |
| `/resource-requests/check-overdue` | POST | Organizer | Overdue check |

### Reminders & Notifications

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/reminders/sweep` | POST | Organizer | Trigger reminder sweep |
| `/reminders` | GET | Organizer | Sweep history |
| `/notifications/mine` | GET | Participant | Own notifications |
| `/notifications/{id}/read` | PATCH | Participant | Mark as read |
| `/notifications/all` | GET | Organizer | All notifications |

### Orchestrator

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/orchestrator/run` | POST | Organizer | Run single loop instance |
| `/orchestrator/sweep` | POST | Organizer | Full sweep |
| `/orchestrator/actions` | GET | Organizer | Action log (explainability) |
| `/orchestrator/status` | GET | Organizer | Orchestrator health |

### Dashboard

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/dashboard/health` | GET | Organizer | Aggregated health metrics |
| `/dashboard/approval-queue` | GET | Organizer | Agent-proposed actions |
| `/dashboard/broadcast` | POST | Organizer | Broadcast to all |
| `/dashboard/teams/{id}/override` | PATCH | Organizer | Manual team override |
| `/dashboard/submissions/{id}/override` | PATCH | Organizer | Manual submission override |
| `/dashboard/export` | GET | Organizer | CSV export |
| `/dashboard/ws` | WS | None | WebSocket live updates |

### Q&A

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/qa` | POST | None | Ask a question (RAG) |

---

## 🧪 Running Tests

Each phase has a dedicated test file. Run from `backend/`:

```bash
cd backend

# Phase 2 — Auth & Onboarding (29 checks)
python test_phase2.py

# Phase 5 — Submission Audit (32 checks)
python test_phase5.py

# Phase 7 — Mentor Allocation (19 checks)
python test_phase7.py

# Phase 8 — Resource Allocation (21 checks)
python test_phase8.py

# Remaining phases (6, 9, 10, 11, 13, 14, 15) — 31 checks
python test_remaining.py
```

**Total: 132 checks across all tests.**

---

## 🎬 Demo Script

The Team-42 closed-loop sequence demonstrates the full agent loop:

```bash
cd backend

# Seed the database first
python seed_data.py

# Run the demo
python demo_script.py
```

**Demo steps:**
1. Organizer triggers orchestrator sweep
2. Check escalation queue (sorted by urgency)
3. Check approval queue (agent-proposed actions)
4. Dashboard health overview
5. Agent action explainability feed
6. Resolve escalation
7. Verify out-of-stock resource alert
8. CSV export
9. Orchestrator status

---

## 📁 Project Structure

```
hackops/
├── .env                          # Environment config (gitignored)
├── .env.example                  # Template for .env
├── project_roadmap.md            # Phase-by-phase build plan
├── SETUP.md                      # Setup instructions
├── README.md                     # This file
│
├── backend/                      # FastAPI backend
│   ├── app/
│   │   ├── main.py               # App entry point, router registration
│   │   ├── config.py             # Settings from .env
│   │   ├── database.py           # SQLAlchemy async engine
│   │   ├── auth.py               # JWT + bcrypt password utilities
│   │   ├── models/               # SQLAlchemy ORM models (16 tables)
│   │   │   ├── team.py
│   │   │   ├── participant.py
│   │   │   ├── event.py
│   │   │   ├── submission.py
│   │   │   ├── issue.py
│   │   │   ├── escalation.py
│   │   │   ├── mentor.py
│   │   │   ├── mentor_allocation.py
│   │   │   ├── resource.py
│   │   │   ├── agent_action.py
│   │   │   └── document.py
│   │   ├── schemas/              # Pydantic request/response schemas
│   │   ├── routers/              # FastAPI route handlers (16 routers)
│   │   │   ├── auth.py
│   │   │   ├── participants.py
│   │   │   ├── teams.py
│   │   │   ├── events.py
│   │   │   ├── documents.py
│   │   │   ├── mentors.py
│   │   │   ├── resources.py
│   │   │   ├── qa.py
│   │   │   ├── submissions.py
│   │   │   ├── issues.py
│   │   │   ├── allocations.py
│   │   │   ├── resource_requests.py
│   │   │   ├── reminders.py
│   │   │   ├── orchestrator.py
│   │   │   ├── notifications.py
│   │   │   └── dashboard.py
│   │   └── services/             # Business logic (12 services)
│   │       ├── orchestrator.py   # Closed-loop engine
│   │       ├── urgency.py        # Urgency scoring
│   │       ├── audit.py          # Submission audit
│   │       ├── mentor_allocation.py
│   │       ├── resource_allocation.py
│   │       ├── reminder.py
│   │       ├── matchmaking.py
│   │       ├── qa.py             # RAG pipeline
│   │       ├── notification_delivery.py
│   │       ├── embeddings.py
│   │       └── ingestion.py
│   ├── test_phase2.py           # Auth & onboarding tests (29 checks)
│   ├── test_phase5.py           # Submission audit tests (32 checks)
│   ├── test_phase7.py           # Mentor allocation tests (19 checks)
│   ├── test_phase8.py           # Resource allocation tests (21 checks)
│   ├── test_remaining.py        # Remaining phases tests (31 checks)
│   ├── seed_data.py              # Demo data seeder
│   ├── demo_script.py            # Team-42 demo sequence
│   └── requirements.txt
│
├── frontend/                     # React (Vite) frontend
│   ├── src/
│   │   ├── App.jsx               # Route definitions
│   │   ├── api.js                # API client (auth, all endpoints)
│   │   ├── main.jsx              # React entry point
│   │   ├── index.css             # Global styles (dark theme)
│   │   └── pages/
│   │       ├── HealthPage.jsx         # Landing page
│   │       ├── LoginPage.jsx          # Organizer login
│   │       ├── DashboardPage.jsx      # Organizer dashboard (6 tabs)
│   │       ├── ParticipantLoginPage.jsx
│   │       ├── ParticipantLayout.jsx  # Participant sidebar
│   │       ├── ParticipantTeamPage.jsx
│   │       ├── ParticipantChatPage.jsx
│   │       └── ParticipantMatchesPage.jsx
│   └── package.json
│
├── bot/                          # Discord bot
│   ├── pulse_bot.py              # discord.py bot (6 commands)
│   ├── config.py                 # Bot config from env
│   └── __init__.py
│
└── docs/
    └── .gitkeep
```

---

## 🔑 Login Credentials

### Organizer
- **Username:** `organizer`
- **Password:** See `.env` → `ORGANIZER_PASSWORD`

### Participants
- Register via `POST /participants/register` (email + password)
- After seeding: all demo participants use password `demo1234`
- Example: `POST /auth/participant/login` with `{"email": "alice@team1.dev", "password": "demo1234"}`

### URLs
- **Backend API:** `http://localhost:8000`
- **API Docs (Swagger):** `http://localhost:8000/docs`
- **Frontend:** `http://localhost:5173`
- **Organizer Dashboard:** `http://localhost:5173/dashboard`
- **Participant Portal:** `http://localhost:5173/participant`

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Frontend** | React 18 + Vite | Fast dev, hot reload |
| **Backend** | FastAPI | Async, auto-docs, type-safe |
| **Database** | PostgreSQL + pgvector | One DB for data + vector search |
| **LLM** | Groq API (Llama 3) | Fast inference, free tier |
| **Embeddings** | sentence-transformers (local) | Zero API cost |
| **Auth** | JWT (organizer + participant, bcrypt passwords) | Simple, secure, hackathon-appropriate |
| **Bot** | discord.py | Single-channel Discord integration |
| **Background** | In-process async | No Redis/Celery needed |

---

## 📊 Database Schema

The system uses 16 tables:

| Table | Purpose |
|---|---|
| `events` | Hackathon events with deadlines |
| `tracks` | Competition tracks (AI, Web, Hardware) |
| `schedule_events` | Schedule items |
| `documents` | Uploaded rules/FAQ docs |
| `rules` | Chunked + embedded doc text (pgvector) |
| `teams` | Teams with readiness status |
| `participants` | Registered participants (email + bcrypt password) |
| `submissions` | Team project submissions |
| `submission_requirements` | Per-track required fields |
| `issues` | Participant-reported problems |
| `escalations` | Auto-escalated issues with urgency |
| `mentors` | Mentor roster with skills |
| `mentor_allocations` | Proposed mentor ↔ issue pairings |
| `resource_items` | Resource pools (API keys, hardware) |
| `resource_allocations` | Team ↔ resource tracking |
| `notifications` | In-app + Discord notifications |
| `agent_actions` | Orchestrator explainability log |

---

## 🎯 Demo Scenario (Team-42)

The full demo runs in `demo_script.py`:

```
1. Team "DEMO-42-Alpha" has incomplete submission (65% ready)
2. Organizer triggers orchestrator sweep → submission audit fires
3. Team reports blocker issue → urgency = 0.87 → auto-escalated
4. Mentor allocation requested → skills matched → mentor proposed
5. Dashboard shows live health, escalation queue, approval queue
6. Organizer resolves escalation
7. Dashboard shows out-of-stock resource alert
8. CSV export of all submissions
9. Agent action log shows full reasoning trail
```

---

## 📄 License

Built for [Learnathon 5.0 HackOps hackathon](https://github.com). Educational use.
