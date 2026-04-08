# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Cloth Gallery — fashion image asset management API. Handles bulk image ingestion, AI classification/embedding, taxonomy-based tagging, pgvector semantic search, and buyer-facing lookbooks.

## Development Commands

```bash
# Run API (from gallery-api/)
conda activate qiaofei
uvicorn app.main:app --reload

# Run all tests (requires live PostgreSQL)
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cloth_gallery \
  conda run -n qiaofei python -m pytest tests/ -v

# Run a single test file
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cloth_gallery \
  conda run -n qiaofei python -m pytest tests/test_assets.py -v

# Database migrations
conda run -n qiaofei alembic upgrade head
conda run -n qiaofei alembic revision -m "description"

# Create first admin user
python scripts/create_admin.py --email admin@example.com --name "Admin" --password <pw>

# Start infrastructure (postgres, redis, minio)
docker compose -f docker-compose.dev.yml up -d

# Start embedding-svc (downloads ~1.5GB model on first run)
docker compose -f docker-compose.dev.yml --profile ai up -d embedding-svc

# Start Celery worker (requires ASYNC_MODE=celery in .env)
celery -A app.celery_app:celery_app worker --loglevel=info --concurrency=2
```

## Architecture

### Module layout

Each domain is a package under `app/` with `router.py`, `service.py`, `schemas.py`:

| Package | Responsibility |
|---------|---------------|
| `app/auth/` | JWT auth, bcrypt password hashing, `require_role()` dependency |
| `app/users/` | User CRUD (admin only) |
| `app/assets/` | Image upload, tag management, batch ingest, reprocess |
| `app/taxonomy/` | Taxonomy tree (5 dimensions), candidate labels from VLM |
| `app/lookbooks/` | Curated collections, per-buyer access grants |
| `app/search/` | Tag-filter search, pgvector cosine search, semantic text search |
| `app/jobs/` | `GET /jobs/{job_id}` — poll batch operation progress |
| `app/ai/` | HTTP clients for VLM + embedding; processing pipeline |

### Data model (key tables)

```
asset           — image record; feature_status JSONB tracks {"classify": "pending|done", "embed": "pending|done"}
image_group     — folder/batch grouping for assets
taxonomy_node   — self-referencing tree, 5 dimensions: category/style/color/scene/detail
taxonomy_candidate — VLM labels not found in taxonomy; hit_count incremented each time
asset_tag       — M:M asset↔taxonomy_node; source=ai|human; reprocess only clears ai tags
asset_embedding — pgvector 768-dim vector; column added via raw SQL (not ORM mapped type)
lookbook / lookbook_item / lookbook_access — buyer-facing curated sets
processing_job  — tracks bulk reprocess/ingest progress (total/processed/failed_count)
user            — roles: admin, editor, viewer, buyer
```

### pgvector

The `vector` column in `asset_embedding` is added via raw SQL in the initial migration (`CREATE INDEX USING hnsw`) because SQLAlchemy can't declare pgvector columns natively. Always use raw `text()` SQL for vector operations:

```python
db.execute(text("UPDATE asset_embedding SET vector = CAST(:v AS vector) WHERE asset_id = :id"), ...)
db.execute(text("SELECT ..., (e.vector <=> CAST(:qv AS vector)) AS distance FROM ..."), ...)
```

Use `CAST(:v AS vector)` — not `:v::vector` — because psycopg2 interprets `::` as part of the bind expression and breaks the query.

### AI pipeline

`app/ai/` never loads models. All calls are HTTP:

- **VLM** (`vlm_client.py`): `POST {VLM_ENDPOINT}/v1/chat/completions` — OpenAI-compatible vision endpoint (works with Qwen-VL DashScope, vLLM, Ollama). Returns structured JSON via `response_format: {"type": "json_object"}`.
- **Embedding** (`embed_client.py`): `POST {EMBED_ENDPOINT}/v1/embeddings` with `modality: "image"|"text"` — Infinity-compatible endpoint serving `Marqo/marqo-fashionSigLIP` (768 dims).
- **processing.py**: `classify_asset()` and `embed_asset()` — call the clients, match labels to taxonomy, write tags/embeddings. Both use `db.flush()` (not `db.commit()`) so callers control transaction boundaries.

### Async processing modes

Controlled by `ASYNC_MODE` env var:
- `background` (default): `trigger_asset_processing()` / `run_reprocess_job()` use FastAPI `BackgroundTasks`. No extra infrastructure needed.
- `celery`: dispatch to `celery_process_asset.delay()` / `celery_run_reprocess_job.delay()` in `app/ai/tasks.py`. Each Celery task opens its own `SessionLocal()` session (separate from web process). Requires Redis.

### Auth pattern

`require_role(UserRole.admin, UserRole.editor)` is a dependency factory. Place it as the last `Depends` in a route that doesn't need the user object; assign to `_:` if you do. `get_current_user` is used when you need the user.

### Image variants

Every uploaded image is stored as three S3 objects:
- `original/` — raw bytes, archived
- `display/` — max 1200px longest side, used by VLM and for display
- `thumb/` — max 400px longest side, used in grids

Presigned HTTPS URLs for display images are passed to both VLM and embedding service.

## Test isolation

Tests use connection-level transaction rollback — each `db` fixture wraps everything in a transaction that rolls back at the end. **Never call `db.commit()` in code under test.** Use `db.flush()` instead when the code runs inside a test. Service functions that need to commit in production should commit; the test fixture overrides `get_db` to inject the rollback session.

Embedding vector inserts in tests must use raw SQL:
```python
db.execute(text("INSERT INTO asset_embedding ... VALUES (:id, :ver, CAST(:v AS vector))"), ...)
```

## Configuration

All settings via `app/config.py` (pydantic-settings, reads `.env`). Required: `DATABASE_URL`, `SECRET_KEY`. See `.env.example` at project root for all variables including `S3_*`, `VLM_*`, `EMBED_*`, `ASYNC_MODE`, `CELERY_BROKER_URL`.
