# Glupper Backend

Glupper is an invite-and-vouch trust graph for verifying that online accounts are controlled by real people.

## Product Scope (Current)

### Purpose

- Establish social proof of real humans through in-person vouches.
- Let users keep pseudonyms while still building public trust signals.
- Show trust age (`trust_days`) publicly.

### Trust Model

- Bootstrap: platform admin creates initial trusted users.
- Growth: active users create invite codes and sponsor new users.
- Trust timer: starts at account creation or successful revouch and accumulates in days.
- Public profile: exposes account status, sponsor relationship, trust timer, and verified linked social accounts.

### Moderation Model

- Reports are handled externally through GitHub issues (not handled by backend workflows).
- Conviction is binary.
- If an account is convicted as bot:
  - Convicted account is permanently `banned`.
  - Direct sponsor receives one demerit.
  - All downstream descendants become `revouch_required` (not immediately permanently banned) and lose trust timer.
  - Descendants cannot issue invites while in `revouch_required` state.

### Recovery Model (Downstream of a Convicted Upstream)

Downstream accounts can recover by revouching from a different active sponsor. To reduce fraud/ring recovery:

- Recovery requires a different sponsor than the previous sponsor.
- Recovery can be blocked by a cooldown (`RECOVERY_COOLDOWN_HOURS`, default 72h).
- Recovery sponsor must meet minimum trust age (`RECOVERY_SPONSOR_MIN_TRUST_DAYS`, default 30).
- Recovery sponsor must be low risk by demerits (`RECOVERY_SPONSOR_MAX_DEMERITS`, default 0).
- Successful recovery resets trust timer and sets account back to `active`.

### Sponsor Inactivity Model

- Admin can run sponsor inactivity expiration.
- Descendants of inactive sponsors become `revouch_required` and must get a fresh vouch.

### Social Identity Verification

- Linked social handles require OAuth proof of ownership.
- MVP implementation currently supports GitHub linkage verification.
- Google OAuth is supported for account sign-in/registration.

## Explicit Decisions in Scope

- Pseudonyms are allowed.
- One-person-one-account enforcement is deferred (not in MVP).
- No appeals process in MVP.
- Historical moderation/event data is retained.
- Redis maintains a banned-account dataset for fast lookups.

## Out of Scope (Current)

- Automated bot scoring/classification.
- In-app reporting/review workflow (GitHub issues used instead).
- Legal/privacy policy workflows.
- Strong Sybil resistance beyond invite graph + recovery gates.

## Architecture

- FastAPI API server
- PostgreSQL via asyncpg
- Redis for ban cache
- JWT auth

## Key Data Concepts

- `accounts`: identity, sponsor link, status, trust and recovery timestamps, demerits.
- `invite_codes`: sponsor-issued vouch tokens.
- `social_identities`: verified external handles.
- `account_events`: immutable event log for moderation and lifecycle actions.

## Main API Surface

### Auth

- `POST /api/v1/auth/register/password`
- `POST /api/v1/auth/register/google`
- `POST /api/v1/auth/login/password`
- `GET /api/v1/auth/me`

### Accounts

- `GET /api/v1/accounts/{username}`
- `GET /api/v1/accounts/me`
- `POST /api/v1/accounts/me/revouch`
- `POST /api/v1/accounts/me/heartbeat`

### Invites

- `POST /api/v1/invites`
- `GET /api/v1/invites/mine`

### Social Accounts

- `POST /api/v1/social-accounts/link`
- `GET /api/v1/social-accounts/mine`

### Moderation/Admin

- `POST /api/v1/moderation/bootstrap-user` (admin key)
- `POST /api/v1/moderation/convict` (admin key)
- `POST /api/v1/moderation/expire-inactive-sponsors` (admin key)
- `GET /api/v1/moderation/banned/{account_id}` (admin key)

## Configuration (Important)

Defined in `src/config_secrets.py`:

- `ADMIN_BOOTSTRAP_KEY`
- `RECOVERY_COOLDOWN_HOURS`
- `RECOVERY_SPONSOR_MIN_TRUST_DAYS`
- `RECOVERY_SPONSOR_MAX_DEMERITS`
- JWT, DB, and Redis settings

## Local Run

1. Install dependencies:

```bash
uv sync
```

2. Update config values in `src/config_secrets.py`.

3. Start server:

```bash
python run.py --host 127.0.0.1 --port 8000
```

4. Open docs:

- `http://127.0.0.1:8000/docs`
