# Star Wars Catalog & Voting API

A RESTful API that syncs the [SWAPI](https://swapi.dev) dataset (characters, films, starships) into a PostgreSQL database, exposes it with search, filtering, and pagination, and lets authenticated users vote for their favourites.

**Stack:** Django 4.2 · Django REST Framework · PostgreSQL 16 · Celery + Redis · JWT auth · Docker Compose

---

## Table of contents

- [Architecture](#architecture)
- [Quick start (Docker)](#quick-start-docker)
- [Local development](#local-development)
- [Running tests](#running-tests)
- [API reference](#api-reference)
- [Design decisions](#design-decisions)
- [Project structure](#project-structure)

---

## Architecture

Five focused Django apps, each with a single responsibility:

| App | Responsibility |
|---|---|
| `accounts` | Custom `User` model, JWT registration / login |
| `catalog` | Read-only `Character`, `Film`, `Starship` models and API |
| `swapi_sync` | SWAPI HTTP client (retries, backoff), sync service, Celery task |
| `voting` | `Vote` model via `GenericForeignKey`, toggle vote/un-vote |
| `common` | `TimeStampedModel`, centralised exception handler |

Views are thin — they handle HTTP concerns and delegate to plain-Python service functions. This keeps business logic independently testable without the full request/response cycle.

```
Client
  │
  ▼
DRF Views/ViewSets ──► Service layer (services.py) ──► Models
  │                            │
  │                            ▼
  └── serializers.py     SwapiClient (HTTP, retries)
                                │
                                ▼
                             SWAPI
```

---

## Quick start (Docker)

**Prerequisites:** Docker and Docker Compose.

```bash
git clone <repository-url>
cd swapi_platform
cp .env.example .env
```

Then start everything:

```bash
docker compose up --build
```

The entrypoint automatically waits for the database, runs migrations, and collects static files. The API is available at `http://localhost:8000` once gunicorn reports workers booted.

**Populate the catalog:**

```bash
docker compose exec web python manage.py sync_swapi
# Syncs ~124 records (6 films, 36 starships, 82 characters) from SWAPI.
```

**Create an admin user** (required to trigger sync via the API):

```bash
docker compose exec web python manage.py createsuperuser
```

**Run the test suite:**

```bash
docker compose exec web python -m pytest --ds=config.settings.test
```

**Stop:**

```bash
docker compose down      # keep data
docker compose down -v   # wipe volumes (fresh start)
```

> **Port conflicts:** If PostgreSQL or Redis is already running locally, Docker Compose will fail on startup. Stop the local services first (`sudo systemctl stop postgresql redis`). Only port 8000 (web) is exposed to the host; db and redis communicate internally.

> **Scheduled sync:** A `celery_beat` service is included but disabled by default. To enable daily automatic re-syncs: `docker compose --profile scheduled-sync up`.

---

## Local development

**Prerequisites:** Python 3.11+, PostgreSQL 14+, Redis 6+.

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# Set DB_HOST=localhost in .env

createdb swapi_platform
python manage.py migrate
python manage.py createsuperuser
python manage.py sync_swapi
python manage.py runserver
```

Celery worker (separate terminal, needed for async sync via the API):

```bash
celery -A config worker --loglevel=info
```

---

## Running tests

**Locally:**

```bash
pip install -r requirements-dev.txt
pytest
```

**Inside Docker:**

```bash
docker compose exec web python -m pytest --ds=config.settings.test
```

94 tests, 98% coverage. HTML report written to `htmlcov/`. All external SWAPI calls are mocked — no real network requests.

---

## API reference

All endpoints are prefixed with `/api/v1/`.

Interactive docs (Swagger UI / ReDoc) are available at:
- `http://localhost:8000/api/docs/`
- `http://localhost:8000/api/redoc/`

### Authentication

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/auth/register/` | Public | Create account; returns user + JWT token pair |
| POST | `/auth/login/` | Public | Obtain JWT token pair |
| POST | `/auth/token/refresh/` | Public | Rotate refresh token |
| GET | `/auth/me/` | Required | Current user profile |

All authenticated requests require `Authorization: Bearer <access_token>`.

### Catalog

Applies to `/characters/`, `/films/`, and `/starships/`:

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/{resource}/` | Public | Paginated list; supports `?search=`, `?ordering=`, and resource-specific filters |
| GET | `/{resource}/{id}/` | Public | Full detail with related entities and vote count |
| POST | `/{resource}/{id}/vote/` | Required | Toggle vote (vote → un-vote on repeat) |

```
GET  /api/v1/characters/?search=skywalker
GET  /api/v1/characters/?gender=male&ordering=name
GET  /api/v1/films/?episode_id=4
GET  /api/v1/starships/?search=incom
POST /api/v1/characters/1/vote/
```

Catalog data is read-only through the API — `POST`/`PATCH`/`DELETE` return `405`. Population happens exclusively via the sync process.

### Sync

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/sync/trigger/` | Admin only | Queue async full catalog re-sync via Celery |

Returns `202 Accepted` with a Celery task ID. The sync runs in the background.

### Error shape

Every error response follows the same structure:

```json
{
  "error": {
    "code": "validation_error",
    "message": "One or more fields failed validation.",
    "details": { "password_confirm": ["Passwords do not match."] }
  }
}
```

---

## Design decisions

**Service layer.** Business logic lives in `services.py` modules as plain functions, independent of DRF. Views call into these. This makes sync orchestration and vote toggling testable without HTTP overhead.

**`GenericForeignKey` for votes.** One `Vote` model covers all three entity types instead of three separate models or three nullable FK columns. The trade-off (no DB-level FK constraint) is mitigated by validating the target against an explicit allow-list in `voting/services.py`.

**Correlated subquery for `vote_count`.** A join-based `annotate(Count(...))` alongside `prefetch_related` risks multiplying row counts. A `Subquery` with `Coalesce(..., 0)` is correct and still avoids N+1 (one subquery per list response, not one per row).

**Async sync via Celery.** A request-blocking external API call is a poor pattern regardless of dataset size. The Celery task includes exponential retry-with-backoff for transient SWAPI failures.

**JWT with token blacklisting.** `ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION` are both enabled, backed by `rest_framework_simplejwt.token_blacklist`. Old refresh tokens are invalidated on rotation rather than remaining valid indefinitely.

**Custom `User` model from day one.** Switching `AUTH_USER_MODEL` after the first migration is painful. Starting with a thin `AbstractUser` subclass costs nothing upfront and avoids the migration problem entirely if user fields are added later.

**PostgreSQL over SQLite.** Chosen to mirror a realistic production setup, exercise proper connection pooling (`CONN_MAX_AGE`), and ensure JSON/index behaviour matches production.

---

## Project structure

```
swapi_platform/
├── config/
│   ├── settings/
│   │   ├── base.py          # shared settings
│   │   ├── development.py
│   │   ├── production.py
│   │   └── test.py
│   ├── celery.py
│   └── urls.py
├── apps/
│   ├── accounts/            # User model, registration, JWT login
│   ├── catalog/             # Character/Film/Starship models, views, serializers
│   ├── swapi_sync/          # SWAPI client, sync service, Celery task
│   ├── voting/              # Vote model, vote toggle service
│   └── common/              # TimeStampedModel, exception handler
├── docker/
│   └── entrypoint.sh
├── conftest.py              # shared pytest fixtures
├── pytest.ini
├── Dockerfile
├── docker-compose.yml
├── requirements.txt         # production dependencies
├── requirements-dev.txt     # + testing/linting tools
└── .env.example
```
