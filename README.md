# CreatorOS AI API

FastAPI backend for CreatorOS AI, an AI-powered Social Growth Intelligence Platform for Facebook and Instagram creators.

## Project repositories

- Frontend: https://github.com/akindaG/creatoros-web
- Backend: https://github.com/akindaG/creatoros-api
- Documentation: https://github.com/akindaG/creatoros-docs

## MVP capabilities

- JWT registration, login, logout, profile and password reset
- Facebook and Instagram account connections
- Encrypted social access tokens at rest
- Posts CRUD and filtering
- Image/video upload with Supabase Storage or local fallback
- Scheduling, calendar, rescheduling and cancellation
- Automatic due-post publishing worker
- Ollama + Qwen caption generation, hashtag generation and content analysis
- Analytics snapshots, dashboard metrics, live overview, CSV export
- Best posting-time and growth recommendation engine
- Simulated or live Meta Graph publishing
- PostgreSQL + SQLAlchemy + Alembic
- Automated pytest coverage and GitHub Actions CI

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `DATABASE_URL` and `JWT_SECRET_KEY` in `.env`, then run:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

API docs: `http://localhost:8000/docs`

Health checks:

- `GET /health`
- `GET /health/db`

## Frontend integration

The Next.js frontend reads the backend URL from:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

The backend must allow the frontend origin:

```env
FRONTEND_ORIGINS=http://localhost:3000
```

For deployed Vercel URLs, use a comma-separated list if more than one origin is required.

## AI

CreatorOS calls Ollama at `OLLAMA_BASE_URL` using `OLLAMA_MODEL=qwen3`.

```bash
ollama serve
ollama pull qwen3
```

`AI_FALLBACK_ENABLED=true` keeps the MVP demonstrable if Ollama is temporarily unavailable.

## Social publishing

Safe demo mode:

```env
SOCIAL_PUBLISH_MODE=simulate
```

Live Meta mode:

```env
SOCIAL_PUBLISH_MODE=live
META_GRAPH_BASE_URL=https://graph.facebook.com/v23.0
```

Only Facebook and Instagram are supported in Version 1.0.

Social access and refresh tokens are encrypted before database storage. Set `SOCIAL_TOKEN_ENCRYPTION_KEY` to a long deployment secret, or CreatorOS will derive the encryption key from `JWT_SECRET_KEY` for backward-compatible operation.

## Scheduled publishing worker

Scheduling persists posts in PostgreSQL. To automatically publish due posts, run:

```bash
python -m app.jobs.publish_due
```

For deployment, create a scheduled/cron service that runs this command periodically. The API also exposes `POST /api/v1/internal/process-due` for external schedulers. Configure `CRON_SECRET` and send it as `X-Cron-Secret`.

## Tests

The test suite expects PostgreSQL. After configuring the test database:

```bash
python -m compileall app
alembic upgrade head
pytest -q --cov=app --cov-report=term-missing
```

GitHub Actions provisions PostgreSQL 16 and performs these checks automatically.

## Railway

`railway.json` starts the API with:

```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Recommended Railway environment variables:

- `APP_ENV=production`
- `DEBUG=false`
- `DATABASE_URL=<Supabase/PostgreSQL connection string>`
- `JWT_SECRET_KEY=<strong random secret>`
- `FRONTEND_ORIGINS=<Vercel frontend URL>`
- `SUPABASE_URL=<project URL>`
- `SUPABASE_SERVICE_ROLE_KEY=<service role key>`
- `SUPABASE_STORAGE_BUCKET=creatoros-media`
- `SOCIAL_TOKEN_ENCRYPTION_KEY=<strong random secret>`
- `SOCIAL_PUBLISH_MODE=simulate` for demonstrations, or `live` with approved Meta credentials

## Primary demo journey

1. Register and log in.
2. Connect Instagram or Facebook.
3. Upload media and save a draft.
4. Generate/refine the caption with AI.
5. Schedule the post.
6. Record or sync analytics data.
7. View analytics and growth recommendations.
8. Publish in simulation mode or live Meta mode.

For architecture, testing, deployment and presentation documentation, see the `creatoros-docs` repository.
