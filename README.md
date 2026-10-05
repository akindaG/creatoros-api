# CreatorOS AI API

FastAPI backend for CreatorOS AI, an AI-powered Social Growth Intelligence Platform for Facebook and Instagram creators.

## Project repositories

- Frontend: https://github.com/akindaG/creatoros-web
- Backend: https://github.com/akindaG/creatoros-api
- Documentation: https://github.com/akindaG/creatoros-docs
- Experimental mobile extension: https://github.com/akindaG/creatoros-mobile

## Current capabilities

- JWT registration, login, logout, profile management, password change, and password reset
- Facebook Page OAuth
- Instagram Business or Creator OAuth through Instagram Login
- Encrypted social access credentials at rest
- Posts CRUD and filtering
- Image/video upload with Supabase Storage or local fallback
- Instagram-compatible image normalization
- Single-platform scheduling, rescheduling, cancellation, and calendar retrieval
- One-click multi-platform scheduling with grouped calendar entries
- Exact-time in-process scheduled publishing
- Worker command and protected cron alternative
- Immediate Post Now publishing
- One-click Facebook Page and Instagram multi-platform publishing
- Retry-safe partial publishing results
- Facebook personal-profile assisted sharing
- Gemini or Ollama/Qwen caption generation, hashtag generation, and content analysis
- Deterministic AI fallback when enabled
- Analytics snapshots, dashboard metrics, overview, and CSV export
- Best posting-time and growth recommendation engine
- Simulated or live Meta publishing
- PostgreSQL + SQLAlchemy + Alembic
- Automated pytest coverage

## Local setup

~~~bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
~~~

Set DATABASE_URL and JWT_SECRET_KEY, then run:

~~~bash
alembic upgrade head
uvicorn app.main:app --reload
~~~

Useful endpoints:

- GET /health
- GET /health/db
- GET /docs

The /health response also reports the exact-time scheduler state.

## Frontend integration

The Next.js frontend reads:

~~~env
NEXT_PUBLIC_API_URL=http://localhost:8000
~~~

The backend should allow and redirect to the matching frontend URL:

~~~env
FRONTEND_ORIGINS=http://localhost:3000
FRONTEND_URL=http://localhost:3000
~~~

## AI providers

CreatorOS supports two providers behind the same AI endpoints.

Hosted production:

~~~env
AI_PROVIDER=gemini
GEMINI_API_KEY=<your Gemini API key>
GEMINI_MODEL=gemini-3.5-flash-lite
AI_FALLBACK_ENABLED=true
~~~

Local Qwen:

~~~env
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3
AI_FALLBACK_ENABLED=true
~~~

Then run:

~~~bash
ollama pull qwen3
ollama serve
~~~

The endpoints /api/v1/ai/caption, /api/v1/ai/hashtags, and /api/v1/ai/analyze use the selected provider.

If the selected provider is unavailable and AI_FALLBACK_ENABLED=true, CreatorOS uses a deterministic fallback rather than breaking the workflow.

Never commit GEMINI_API_KEY or other production secrets.

## Social OAuth

### Facebook Page

Configure:

~~~env
META_GRAPH_BASE_URL=https://graph.facebook.com/v26.0
META_APP_ID=
META_APP_SECRET=
META_REDIRECT_URI=http://localhost:8000/api/v1/social-accounts/facebook/callback
~~~

Facebook automatic publishing targets Pages, not personal timelines.

### Instagram

Configure:

~~~env
INSTAGRAM_APP_ID=
INSTAGRAM_APP_SECRET=
INSTAGRAM_REDIRECT_URI=http://localhost:8000/api/v1/social-accounts/instagram/callback
INSTAGRAM_GRAPH_BASE_URL=https://graph.instagram.com/v26.0
INSTAGRAM_OAUTH_AUTHORIZE_URL=https://www.instagram.com/oauth/authorize
INSTAGRAM_OAUTH_TOKEN_URL=https://api.instagram.com/oauth/access_token
INSTAGRAM_SCOPES=instagram_business_basic,instagram_business_content_publish,instagram_business_manage_insights
~~~

The Instagram OAuth path supports professional Instagram accounts compatible with the configured Instagram API permissions.

## Social publishing

Safe simulation:

~~~env
SOCIAL_PUBLISH_MODE=simulate
~~~

Live mode:

~~~env
SOCIAL_PUBLISH_MODE=live
~~~

Automatic live targets:

- Facebook Page
- Instagram Business or Creator account

Facebook personal profiles use an assisted manual-share workflow. The API deliberately rejects automatic personal-profile publishing.

Social access and refresh credentials are encrypted before database storage. Set SOCIAL_TOKEN_ENCRYPTION_KEY to a long deployment secret. If omitted, CreatorOS derives a compatible key from JWT_SECRET_KEY.

## Scheduling

The FastAPI application starts app/services/exact_scheduler.py in its lifespan.

The scheduler:

1. Finds the nearest scheduled database timestamp.
2. Sleeps until that exact time.
3. Wakes early when a schedule is created, edited, or cancelled.
4. Processes due content through the publishing service.
5. Converts due Facebook personal-profile items to ready_to_share.

For simultaneous Facebook and Instagram scheduling, platform-specific posts receive schedules with the same schedule_group_id.

Operational alternatives remain available.

Worker:

~~~bash
python -m app.jobs.publish_due
~~~

Protected endpoint:

~~~text
POST /api/v1/internal/process-due
X-Cron-Secret: <CRON_SECRET>
~~~

## Tests

The current repository contains 30 backend test functions covering authentication, core CRUD, media validation, AI provider selection, OAuth, Facebook and Instagram publishing, Facebook personal-profile assisted sharing, multi-platform publishing, multi-platform scheduling, analytics, and social-image normalization.

Run:

~~~bash
python -m compileall app
alembic upgrade head
pytest -q --cov=app --cov-report=term-missing
~~~

Do not treat the test inventory as a pass result. Record the actual passed and failed counts from the current run.

## Railway

The repository starts production with migrations before Uvicorn.

Recommended environment variables include:

- APP_ENV=production
- DEBUG=false
- DATABASE_URL
- JWT_SECRET_KEY
- FRONTEND_ORIGINS
- FRONTEND_URL
- AI_PROVIDER
- GEMINI_API_KEY when Gemini is selected
- GEMINI_MODEL
- AI_FALLBACK_ENABLED
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
- SUPABASE_STORAGE_BUCKET
- SOCIAL_TOKEN_ENCRYPTION_KEY
- SOCIAL_PUBLISH_MODE
- META_GRAPH_BASE_URL
- META_APP_ID
- META_APP_SECRET
- META_REDIRECT_URI
- INSTAGRAM_APP_ID
- INSTAGRAM_APP_SECRET
- INSTAGRAM_REDIRECT_URI
- CRON_SECRET

## Primary demo journey

1. Register and log in.
2. Connect Facebook Page and/or Instagram through OAuth.
3. Upload media and save a draft.
4. Generate or refine the caption with AI.
5. Publish now or schedule one or both automatic platforms.
6. Confirm scheduled items in Calendar.
7. View analytics and growth recommendations.
8. Demonstrate Facebook personal-profile assisted sharing separately if required.

For architecture, data-model, testing, deployment, demo, and final-report alignment documentation, see creatoros-docs.
