# Deployment

## Recommended production topology

- **Frontend:** Vercel (Next.js) or the included Docker image.
- **API + worker:** container host (Fly.io, Render, Railway, ECS, etc.). FastAPI is a long-running Python service; do not deploy it as a Vercel serverless function.
- **Database:** Supabase Postgres or managed PostgreSQL with `vector` enabled.
- **Queue/locks:** managed Redis.
- **Recordings:** private Supabase Storage bucket (or encrypted persistent disk with backups).
- **Email:** transactional SMTP provider.

## Environment

Use `.env.example` as the contract. Production requirements:

```env
APP_ENV=production
APP_URL=https://app.example.com
API_URL=https://api.example.com
API_INTERNAL_URL=https://api.example.com
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DB?sslmode=require
REDIS_URL=rediss://USER:PASSWORD@HOST:6379/0
COOKIE_SECURE=true
ENCRYPTION_KEY=<base64-urlsafe 32-byte key>
EMBEDDED_WORKER=false
ENABLE_DEMO=false
SUPABASE_URL=https://PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<server-only>
SUPABASE_STORAGE_BUCKET=momentum-recordings
```

Generate an encryption key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

The API refuses production startup with SQLite, insecure cookies, or a missing encryption key. Never expose `SUPABASE_SERVICE_ROLE_KEY`, OAuth client secrets, SMTP passwords, or AI keys to the browser. Next.js only needs `API_INTERNAL_URL` (server-side rewrite target).

## Database

```bash
PYTHONPATH=backend:. .venv/bin/python database/migrate.py
```

The migration runner records applied versions in `schema_migrations` and applies each SQL file transactionally. The initial migration enables `pgvector` and creates all tables/indexes. Back up before migrating. Supabase users can also run the SQL in the SQL editor, but the runner is preferred for repeatability.

## Frontend on Vercel

1. Import the repository and set **Root Directory** to `frontend`.
2. Build command: `npm run build`; output: Next.js default.
3. Set `API_INTERNAL_URL` to the public HTTPS API origin (or a private network target if your platform supports it).
4. Deploy. The same-origin `/api/*` rewrite keeps cookies first-party and avoids browser CORS/localhost issues.
5. Set `APP_URL`/`API_URL` on the API to the deployed origins and configure OAuth redirect URIs.

For the Docker frontend, `API_INTERNAL_URL` is read when the Next.js rewrite manifest is built. Pass it as a build argument if your API origin differs from the compose default.

## API and worker containers

```bash
docker build -f backend/Dockerfile -t momentum-api .
docker run --env-file .env -p 8000:8000 momentum-api
# Separate worker process:
docker run --env-file .env momentum-api python -m workers.runner
```

Run at least one worker. The worker uses Redis for a distributed lock when configured; job claims are also atomic in the database. Scale API replicas independently. Put the API behind TLS and a reverse proxy that preserves `Host`/`X-Forwarded-Proto`.

## OAuth redirect URIs

- Google sign-in: `{APP_URL}/api/auth/google/callback`
- Integrations: `{API_URL}/api/integrations/{provider}/callback`

If the frontend proxies the API on the same domain, use the public frontend origin for both patterns. Register the exact URIs with each provider. Integration scopes are least-privilege; Gmail creates drafts and never sends email.

## Health and operations

- Liveness: `GET /api/health`
- Readiness/database: `GET /api/health/ready`
- Logs: structured application logs; audit events are stored per organization.
- Monitor: processing failure rate, stale jobs, SMTP outbox failures, OAuth refresh failures, storage errors, and API 5xx.
- Retention: worker enforces organization retention settings; deletion removes meetings, recordings, tasks, memory, and shares.
- Backups: database + private object storage. Test restore procedures.

## Pre-launch checklist

- [ ] HTTPS everywhere; secure cookies; strict `APP_URL`/`API_URL`.
- [ ] Strong encryption key stored in a secret manager; rotation plan documented.
- [ ] PostgreSQL migration applied; pgvector enabled; backups tested.
- [ ] Redis configured; at least one worker healthy.
- [ ] Private storage bucket verified; signed URLs expire; no public bucket policy.
- [ ] SMTP verified; verification/reset emails deliver.
- [ ] OAuth apps configured and consent screens reviewed.
- [ ] Each enabled integration tested with a real account and confirmed response.
- [ ] Demo disabled or clearly isolated in production.
- [ ] Rate limits reviewed for expected traffic (in-process by default; use edge/proxy limits for multi-replica deployments).
- [ ] Privacy policy, retention defaults, and data-processing agreements reviewed.
