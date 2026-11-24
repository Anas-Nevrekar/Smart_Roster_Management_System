# Smart Roster Management API

FastAPI backend for Smart Roster. Master-data requests flow **route → service → repository**. Roster generation flows **route → management service → repository snapshot → isolated scheduling-engine worker**. MongoDB Atlas is the normal application storage; the in-memory repository remains available for tests and explicit local use.

## MongoDB Atlas setup

1. Create an Atlas database user with `readWrite` access to the development database.
2. Add your development machine's IP to Atlas Network Access (or configure the approved network range for your environment).
3. Copy `.env.example` to `.env` in this directory.
4. Replace the placeholder `MONGODB_URI` with the Atlas connection string locally. URL-encode special characters in the username/password. Keep the real `.env` private; never put the URI in frontend configuration or source control.
5. Keep `MONGODB_DATABASE=smart_roster_dev` and `STORAGE_BACKEND=mongodb` for normal development.

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The backend uses the official synchronous PyMongo driver. API route handlers are synchronous FastAPI handlers and run in its worker threadpool. One `MongoClient` is created per application lifespan and closed on shutdown. Connection failures are redacted, the process does not fall back to in-memory storage, `/api/v1/health` remains a process liveness check, and `/api/v1/ready` returns 503 until MongoDB and its indexes are ready.

Start the API from this directory:

```bash
uvicorn app.main:app --reload
```

Check `http://127.0.0.1:8000/api/v1/health`, `http://127.0.0.1:8000/api/v1/ready`, and `/docs`. Master-data and roster records persist across backend restarts.

To explicitly run without a database for local UI or unit testing, set `STORAGE_BACKEND=memory`. Tests can continue injecting a fresh `InMemoryRepository` directly.

## Collections and indexes

The repository preserves the existing domain field names and maps logical collections to MongoDB as follows:

| Repository collection | MongoDB collection | Key indexes |
|---|---|---|
| employees | `employees` | stable repository `_id`, unique employee ID and email, pod lookup |
| pods | `pods` | stable repository `_id`, unique name |
| brands | `brands` | stable repository `_id`, unique name |
| processes | `processes` | stable repository `_id`, unique name |
| eligibility | `employee_assignments` | unique employee/brand/process |
| operating_rules | `brand_process_rules` | unique brand/process |
| time_off | `employee_time_off` | employee/date-range lookup |
| public_holidays | `public_holidays` | unique holiday date |
| rosters | `rosters` | unique month/year, status/date lookup |
| roster_assignments | `roster_assignments` | unique working assignment tuple; unique weekly-off employee/date; coverage lookup |

Fixture entity IDs such as `E001`, `B003`, and `PR001` are stored as `_id`; API responses continue to expose `id`. The engine mapper uses the existing fixture-specific domain ID when present, or the repository `id` for entities created through the API. Date-only fields are stored as UTC-midnight BSON datetimes and converted back to ISO date strings at the repository boundary. Audit timestamps remain timezone-aware UTC datetimes.

Indexes are created idempotently during MongoDB startup and readiness checks. Existing duplicate data that prevents a unique index is reported without deleting records; reconcile those conflicting records before retrying.

Roster creation, regeneration, and publishing use MongoDB transactions. Conditional roster version and draft-status updates prevent concurrent edits from overwriting newer versions. MongoDB Atlas replica-set deployments support these transactions; standalone MongoDB deployments that do not support transactions will return a structured database error for those operations.

## Sample data

Seed the bundled expanded fixture once MongoDB is configured:

```bash
python -m app.scripts.seed_database
```

Seeding is additive and idempotent: fixture IDs are stable, unchanged records are left alone, changed fixture records are updated, and user-created records are not deleted. Indexes and fixture relationships are checked. The script prints actual collection totals and inserted/updated/unchanged counts. It does not generate a roster.

The valid fixture defaults to `smart_roster_dev`. The conflict fixture is restricted to its separate database:

```bash
python -m app.scripts.seed_database --scenario conflict --database smart_roster_conflict_test
```

The explicit `--reset` option is available only for the named development/test databases (`smart_roster_dev`, `smart_roster_conflict_test`, `smart_roster_test`) and requires typing the exact database name. Normal seeding and application startup never reset or drop data.

Generate and persist a December 2026 draft through the existing API after valid data has been seeded:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/rosters/generate \
  -H 'Content-Type: application/json' \
  -d '{"month":12,"year":2026}'
```

This endpoint refuses to overwrite an existing month/year roster. Use the existing versioned regeneration endpoint for an explicit draft regeneration.

## Tests

Run the regular backend suite without MongoDB access:

```bash
pytest -q
python -m unittest discover -s app/scheduling_engine/tests -v
```

MongoDB integration tests only run when `MONGODB_TEST_URI` is set, and they are hard-pinned to `smart_roster_test`. They reset only that test database and never use `MONGODB_URI` or the development database:

```bash
MONGODB_TEST_URI='mongodb+srv://…' pytest -q tests/test_mongodb_integration.py
```

The integration fixture cleans up only `smart_roster_test`. Configure its database user's permissions accordingly.

Frontend regression checks are run from `../frontend` with `npm test`, `npm run typecheck`, and `npm run build`.

## Security and current setup state

`backend/.env` and other `.env.*` files are ignored; `.env.example` contains placeholders only. Do not share credentials in chat or commit them. MongoDB connection and persistence checks require your local Atlas URI and network access to be configured first.
