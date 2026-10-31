# Security model

## Identity and sessions

Passwords use PBKDF2-SHA256 (600,000 iterations) with per-user salts. Sessions are opaque random tokens stored hashed, delivered as HttpOnly/SameSite cookies, and revoked on password reset and account deletion. Reset and verification tokens are single-use and expire. Google sign-in uses OIDC with database-backed state, a state cookie, PKCE, nonce validation, and verified-email checks.

## Authorization and isolation

Every workspace query is scoped by organization membership. Roles: owner, admin, member, viewer. Viewers cannot mutate work; destructive workspace operations require owner/admin. Demo organizations are isolated per anonymous session, labeled, and blocked from external connections/approvals/execution.

## Request protections

- Mutations require `X-Momentum-Client: web`; cross-site fetch metadata is rejected.
- Same-origin browser API access through Next.js rewrites keeps session cookies first-party.
- Security headers: nosniff, referrer policy, permissions policy; API responses are not cached.
- In-process rate limits protect auth and sensitive endpoints. For multi-replica production, enforce equivalent limits at the edge/reverse proxy or add a shared limiter.
- Pydantic contracts reject unknown fields and invalid types; uploads are size-limited and magic-byte validated.

## Secrets and integrations

OAuth access/refresh tokens are encrypted at rest with `ENCRYPTION_KEY`. Provider secrets and Supabase service-role keys are server-only. Integration execution requires a connected provider, an approved task, appropriate role, and verified email where required. Success is recorded only from a confirmed provider response, with the external ID stored for traceability. Gmail execution creates drafts; it does not send email.

## Meeting privacy

Recordings require explicit consent. Private uploads are stored outside the web root or in a private Supabase bucket and served through short-lived HMAC/signed URLs. Public execution cards are opt-in, revocable, sanitized, `no-store`, and `noindex`; they never include transcripts, recordings, participant emails, or private meeting content beyond the approved card fields.

## AI and memory

Customer recordings are sent to a configured transcription provider only when the user supplies that provider's credentials and initiates processing. The application does not train models on customer data. Generated decisions/tasks retain transcript segment references. Missing owners/deadlines are not invented; uncertainty lowers confidence and requires review. Retrieval is organization/project scoped.

## Data lifecycle

Users can export their workspace data and delete their account/workspace. Retention settings are enforced by the worker. Audit events record consequential actions. Backups and provider-side token revocation are operational responsibilities; deleting data in the application does not retroactively erase backups or third-party audit logs.

## Known limitations

This baseline has not undergone an independent penetration test or compliance audit. Before handling sensitive enterprise data, review: shared rate limiting, centralized secret rotation, backup encryption/restore, provider data-processing terms, incident response, and organization-level SSO/SCIM requirements.
