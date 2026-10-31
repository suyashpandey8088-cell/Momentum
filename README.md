# MOMENTUM

**From conversation to completion.**

MOMENTUM turns meetings into source-grounded decisions, owned work, approved execution, and organizational memory. It is a working full-stack product: a motion-led marketing experience, a private demo sandbox, and a persistent execution workspace.

## What works now

- **Marketing:** original interactive Three.js/R3F network, eight-part product story, live-style product previews, theme/motion controls, responsive layouts, reduced-motion and lightweight fallbacks.
- **Accounts:** email/password, Google OIDC, verification, password reset, secure opaque sessions, individual/team onboarding, account export and workspace deletion.
- **Meetings:** manual notes, transcript import, validated MP3/WAV/M4A/MP4/WebM uploads, browser recording, participants, consent, processing jobs, editable transcripts/decisions/actions, audio playback, source links.
- **Intelligence:** six modular agents (transcription, meeting intelligence, planning, execution, follow-up, memory). With provider keys, OpenAI/Anthropic adapters and OpenAI transcription/embeddings are available. Without keys, clearly labeled grounded local extraction and lexical retrieval work.
- **Execution:** task CRUD, comments, dependencies, search/filter/sort, Kanban/list, approvals, reminders, reports, project progress, and persistent memory search.
- **Integrations:** Google sign-in; OAuth connection flows and confirmed execution adapters for Gmail drafts, Google Calendar, Slack, Linear, and Notion. Microsoft Teams, Trello, and Asana are explicitly marked planned.
- **Sharing:** private-by-default, revocable execution cards with PNG export, QR code, copy/native share, and sanitized public data.
- **Operations:** background worker, retries, audit log, notifications/outbox, PostgreSQL + pgvector migration, optional Supabase private object storage, Docker deployment.

External actions are never simulated. A task only becomes `EXECUTED` after the provider confirms success. Demo workspaces cannot connect integrations or execute external actions.

## Quick start (local, no API keys)

Requires Node.js 22+ and Python 3.11+.

```bash
python -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
npm --prefix frontend install
cp .env.example .env
npm run dev
```

Open **http://localhost:3000**. Click **Explore the platform** for an isolated sample workspace, or create an account. SQLite, private local uploads, local extraction, and the embedded worker are configured automatically.

- Frontend: `http://localhost:3000`
- API: `http://localhost:8000/api/health`
- Interactive API docs: `http://localhost:8000/docs`
- Browser-facing API calls use same-origin `/api/*`, proxied by Next.js.

### Optional AI

Set `OPENAI_API_KEY` for audio transcription, richer extraction, and semantic embeddings. Set `ANTHROPIC_API_KEY` to use Anthropic for meeting intelligence. The UI reports the actual provider/mode and surfaces configuration failures instead of inventing results. See `.env.example`.

### Sample data

The anonymous demo creates a fresh private user/organization and seeds fictional Orbit Studio conversations. To re-seed an existing **demo** organization from the CLI (real workspaces are intentionally rejected):

```bash
PYTHONPATH=backend:. .venv/bin/python database/seed.py --organization ORG_ID --user USER_ID
```

## PostgreSQL / Supabase

1. Create a PostgreSQL database and enable `vector` (Supabase: Database → Extensions).
2. Set `DATABASE_URL=postgresql+psycopg://...` in `.env`.
3. Apply the versioned migration: `npm run db:migrate`.
4. Set a strong `ENCRYPTION_KEY`, provider secrets, SMTP, and `COOKIE_SECURE=true` behind HTTPS.
5. Run the API and worker separately with `EMBEDDED_WORKER=false`.

For private Supabase object storage, create a **private** bucket and set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_STORAGE_BUCKET`. The service-role key stays on the API server. Local disk remains the default when unset.

## Docker (PostgreSQL + Redis + API + worker + web)

```bash
cp .env.example .env
docker compose up --build
```

The compose stack is for local evaluation (`APP_ENV=development`, HTTP cookies). For production, use the hardened settings in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). The frontend container uses Next.js standalone output.

## Validation

```bash
npm run typecheck
npm run build
.venv/bin/pytest tests -q
```

The backend suite covers authentication/session security, tenant isolation, consent/CSRF, grounded extraction, processing, approval gating/idempotency, task dependencies, private recordings, share revocation/sanitization, export, and deletion.

Browser smoke audit (with the app running):

```bash
cd frontend
npm run test:ui
```

The audit uses Playwright with `@sparticuz/chromium`, checks the landing page, demo workspace, task creation, transcript processing, and mobile layout, and writes screenshots to `frontend/artifacts/` (gitignored). On Debian hosts missing Chromium shared libraries, install the distro Chromium dependencies or use a standard Playwright browser installation.

## Project map

```text
frontend/                 Next.js App Router, design system, marketing, workspace
backend/api/              Auth, workspace, meetings, actions, integrations, insights
backend/agents/           Transcription, intelligence, planning, execution, follow-up, memory
backend/workers/          Atomic jobs, retries, reminders, summaries, retention, embeddings
backend/integrations/     OAuth and confirmed external execution adapters
backend/services/         Providers, storage, email, audit, serialization
backend/models/           SQLAlchemy entities and tenant boundaries
database/migrations/      PostgreSQL + pgvector schema
database/seeds/           Fictional demo workspace
docs/                     Architecture, API, deployment, security
tests/                    Isolated workflow/security tests
```

## Design and behavior

Dark-first, editorial, restrained. Inter/Manrope/local monospace fonts, consistent spacing and state colors, purposeful motion, accessible dialogs, keyboard command menu, touch-safe interactions, and OS-aware theme/motion preferences. Sample data is always labeled. Missing owners/deadlines remain unassigned/undated and are flagged for confirmation.

## Honest boundaries

- Live OAuth, email delivery, AI transcription, and external writes require your own credentials and have not been executed against live third-party accounts in this environment.
- Local extraction is deliberately conservative; it is not a replacement for a configured LLM on ambiguous language.
- Team workspaces support member roles and shared data; a full invitation/billing administration suite is not included.
- This is a strong application security baseline, not an independent penetration test or compliance certification.

See [architecture](docs/ARCHITECTURE.md), [API](docs/API.md), [deployment](docs/DEPLOYMENT.md), and [security](docs/SECURITY.md).
