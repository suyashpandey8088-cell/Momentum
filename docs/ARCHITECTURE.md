# Architecture

## System

```text
Browser → Next.js (same-origin /api rewrite) → FastAPI → PostgreSQL/SQLite
                                             ├→ private disk / Supabase Storage
                                             ├→ AI provider adapters
                                             ├→ OAuth integration adapters
                                             └→ SMTP / notification outbox
Worker → processing jobs, reminders, summaries, retention, embeddings
```

The frontend never receives provider secrets, service-role keys, raw OAuth tokens, or private storage paths. Next.js proxies `/api/*` to `API_INTERNAL_URL`; the browser only talks to its own origin.

## Backend layers

- `api/`: HTTP contracts, authentication, RBAC, tenant scoping, validation.
- `agents/`: provider-independent pipeline stages.
  - **Transcription:** OpenAI transcription adapter; honest `needs_configuration` when unavailable.
  - **Meeting intelligence:** structured decisions/actions with evidence and confidence.
  - **Planning:** owner/deadline/priority/dependency normalization; never invents missing facts.
  - **Execution:** approval lifecycle and confirmed provider writes.
  - **Follow-up:** reminders, overdue detection, weekly summaries.
  - **Memory:** source-grounded chunks, embeddings, scoped retrieval.
- `services/`: storage validation/signing, provider clients, email/outbox, audit, serialization.
- `workers/runner.py`: atomic job claims, stale-job recovery, bounded retries/backoff, maintenance.
- `models/`: organization-scoped entities; memberships enforce roles.

## Data flow

1. A meeting is created with source material, participants, project, and consent.
2. A processing job is queued. The worker claims it atomically and updates progress.
3. Audio is transcribed only when a transcription provider is configured. Text/transcript sources proceed locally.
4. Intelligence produces candidate decisions/tasks with transcript segment references. Invalid evidence triggers a visible local fallback.
5. Planning validates owners against participants, parses only explicit dates, and caps confidence when facts are missing.
6. Outputs are reviewable. Users can edit transcripts, decisions, and tasks; reprocessing preserves approved/commented work.
7. Approved tasks may execute through a connected provider. The provider response ID and result are stored; failures are visible.
8. Memory chunks retain source meeting/segment references. Retrieval is organization/project scoped and labeled lexical vs semantic.

## Frontend

Next.js App Router + React + TypeScript + Tailwind CSS 4. Motion handles reveals/transitions; React Three Fiber/Drei/Three render the original hero network. Recharts powers reports. Local font packages avoid runtime font requests. Theme and motion preferences persist; the initial theme follows the OS to avoid a flash. Touch devices disable magnetic/custom cursor behavior. Reduced motion disables nonessential animation and uses a lightweight hero fallback.

The workspace is a separate application shell with Overview, Meetings, Tasks, Projects, AI Memory, Integrations, Reports, and Settings. Data hooks poll processing state and surface loading/empty/error states. Mutations include the `X-Momentum-Client: web` header required by the API's CSRF defense.

## Storage and retrieval

SQLite WAL is the zero-config development default. PostgreSQL uses pgvector cosine search with an HNSW index; other databases use an explicitly labeled lexical/cosine fallback. Recordings are private: local files live outside the web root; Supabase objects use a private bucket and short-lived signed URLs. Public execution cards contain only sanitized, explicitly shared fields.

## Extension points

Add an AI provider by implementing the provider interface in `services/providers.py`. Add an integration by registering OAuth metadata/scopes and an execution adapter, then updating the catalog status only after a confirmed end-to-end test. Keep all writes behind the approval/permission gate.
