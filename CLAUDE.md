# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Quato is an LLM-powered agent that converts plain-text trading strategy ideas into runnable QuantRocket Zipline backtests. It exposes a REST API for strategy generation, queuing, and execution with distributed coordination via Redis.

**Tech stack**: FastAPI, LangGraph, Google Gemini 2.5 Flash, Redis, MinIO/S3, QuantRocket, GitHub (strategy delivery)

## Development Commands

### Setup
```bash
# Install dependencies
pip install -e .

# Start Redis and MinIO (required for local dev)
docker compose up -d

# Wipe all state and start fresh
docker compose down -v

# Run the API server
uvicorn api.main:app --reload
```

### Testing
```bash
# Run all tests (requires running API server)
pytest -v

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests (excluding slow tests that need QuantRocket/LLM)
pytest tests/integration/ -v -m "not slow"

# Run integration tests with QuantRocket (takes minutes)
pytest tests/integration/ -v
```

### Environment
Requires a `.env` file with:
- `GOOGLE_API_KEY` (Gemini)
- `HOUSTON_URL` (QuantRocket instance)
- `GITHUB_TOKEN`, `GITHUB_USERNAME`, `REPO_PATH` (strategy delivery)
- `REDIS_URL` (default: `redis://localhost:6379`)
- `OBJECT_STORE_*` (MinIO for local, S3 for production)

## Architecture

### Multi-instance coordination
All server instances share the same Redis. A distributed lock (`backtest:lock`) ensures only one backtest runs globally at a time, even across multiple deployments. Workers continuously poll the queue (`backtest:queue`) using blocking Redis BRPOP.

### Backtest lifecycle
1. `POST /api/backtest` creates a task hash in Redis, enqueues the `task_id`
2. A `BacktestWorker` dequeues the task and acquires the distributed lock
3. Strategy code is uploaded to GitHub → pulled into QuantRocket via `/codeload/repo`
4. `zipline.backtest()` runs in a thread pool (blocking QuantRocket API call)
5. **If backtest fails with a code error**: Worker automatically sends error to agent for correction and retries (up to `MAX_AGENT_RETRIES` times)
6. Results CSV is uploaded to MinIO/S3; summary metrics extracted and written to task hash
7. Lock released; local files deleted

**Key**: Lock TTL is 3 hours (`config.BACKTEST_LOCK_TTL_SECONDS`). If your backtests run longer, increase this value.

### Failure recovery
- **Automatic code error retry**: If QuantRocket returns a code error (syntax, runtime, API misuse), worker automatically requests agent correction and retries up to `MAX_AGENT_RETRIES` times (default: 5)
- **Startup recovery**: On boot, if no lock is held, mark orphaned `running` tasks as `failed`
- **Periodic cleanup**: Every 15 minutes, mark tasks running beyond the lock TTL as `failed` (handles lock expiry without task update)
- **Lock holder protection**: Recovery logic skips cleanup when a lock is held to avoid disrupting active backtests

### Session identity
The `X-Session-ID` header (client-generated UUID) is the sole user identity. All state (strategy code, conversation history, turn count, backtest history) is keyed by this ID in Redis. No authentication or user accounts.

### Redis key schema
| Key | Type | Purpose |
|---|---|---|
| `strategy:{session_id}` | String | Current strategy Python code |
| `session:turns:{session_id}` | Integer | Conversation turn counter |
| `backtest:queue` | List | FIFO queue of pending `task_id`s |
| `backtest:task:{task_id}` | Hash | Task status, config, metrics, object store key |
| `session:{session_id}:tasks` | Set | All `task_id`s for a session |
| `backtest:lock` | String | Distributed lock (holds `task_id` of running backtest) |
| LangGraph keys | Various | Conversation checkpoint data (managed by `AsyncRedisSaver`) |

### Object store
Backtest CSVs are stored in S3-compatible object storage:
- **Local dev**: MinIO (port 9000, console on 9001)
- **Production**: AWS S3 (remove `OBJECT_STORE_ENDPOINT` from `.env` to use default AWS endpoint)

Pre-signed download URLs (`GET /api/backtest/{task_id}/download`) are valid for 1 hour.

## Key Components

### Agent Service ([services/agent_service.py](services/agent_service.py))
- Manages LangGraph agent with MCP tools exposed by `mcp_server/quato_server.py`
- Extracts Python code from agent responses (markdown code blocks or raw code)
- Builds prompt with system instructions + Zipline API resources on first turn
- Stores strategy code in Redis when code is detected in response

### MCP Server ([mcp_server/quato_server.py](mcp_server/quato_server.py))
Exposes Zipline/Pipeline API documentation to the agent via FastMCP:
- **Resources**: `ziplineApi://overview_of_pipeline_functions_and_classes`, `ziplineApi://overview_of_zipline_functions_and_classes`
- **Tool**: `get_function_or_class_details(function_class_names: list[str])` — retrieve detailed docs for specific functions/classes

### Backtest Queue ([services/backtest_queue.py](services/backtest_queue.py))
Redis-based distributed queue with CRUD operations:
- `create_task()`, `get_task()`, `update_task()` — task hash persistence
- `enqueue_task()`, `dequeue_task()` — FIFO queue operations (LPUSH/BRPOP)
- `acquire_backtest_lock()`, `release_backtest_lock()` — distributed lock (SET NX EX + Lua script for atomic release)
- `mark_running_as_failed()`, `cleanup_stale_running_tasks()` — failure recovery

### Backtest Worker ([services/backtest_worker.py](services/backtest_worker.py))
Async worker loop that:
1. Dequeues tasks (blocks for `WORKER_QUEUE_TIMEOUT_SECONDS`)
2. Checks for active lock before processing (skips if lock held)
3. Acquires lock, runs backtest with automatic retry on code errors
4. **On code error**: Sends error to agent, gets corrected code, retries (up to `MAX_AGENT_RETRIES`)
5. Uploads results or marks as failed after max retries
6. Releases lock
7. Runs periodic cleanup every `WORKER_CLEANUP_INTERVAL_SECONDS`
8. Gracefully shuts down on server stop (waits `WORKER_SHUTDOWN_TIMEOUT_SECONDS`)

### Orchestrator ([backtesting_orchestrator/orchestrator.py](backtesting_orchestrator/orchestrator.py))
Handles the full backtest lifecycle:
- Writes strategy code to temporary file
- Uploads to GitHub (commit to main, QuantRocket pulls via `/codeload/repo`)
- Calls `zipline.backtest()` via QuantRocket client (blocking call in thread pool)
- **Extracts detailed error messages** from QuantRocket HTTPError responses for agent feedback
- Extracts summary metrics (`total_return`, `sharpe_ratio`, `max_drawdown`) from results CSV
- Uploads CSV to object store
- Deletes local files

### API Routes ([api/main.py](api/main.py))
- `POST /api/chat` — send message to agent, get response + strategy code if updated
- `GET /api/strategy/current` — retrieve current strategy code for session
- `POST /api/backtest` — queue backtest, returns `task_id` immediately
- `GET /api/backtest/{task_id}` — poll for status/results (includes summary metrics when complete)
- `GET /api/backtest/{task_id}/download` — generate pre-signed URL for CSV download
- `GET /api/backtest/history` — get all backtests for session, newest first
- `GET /health` — health check

## Configuration

All tuneable values are in [config.py](config.py):
- `BACKTEST_LOCK_TTL_SECONDS` (default: 10800 = 3 hours) — distributed lock TTL
- `WORKER_QUEUE_TIMEOUT_SECONDS` (default: 5) — worker blocking timeout on queue
- `WORKER_SHUTDOWN_TIMEOUT_SECONDS` (default: 30.0) — graceful shutdown grace period
- `WORKER_CLEANUP_INTERVAL_SECONDS` (default: 900 = 15 min) — periodic stale task cleanup
- `MAX_AGENT_RETRIES` (default: 5) — maximum automatic retries with agent for code errors

## Important Notes

- **Conversation turn tracking**: `session:turns:{session_id}` is atomically incremented on each message. Turn 0 includes full system prompt + API resources; subsequent turns send only the user message (history managed by LangGraph checkpointer).
- **Lock release is atomic**: Uses a Lua script to prevent TOCTOU races (check-and-delete in one operation).
- **Strategy delivery via GitHub**: QuantRocket has no direct file upload, so strategies are committed to a GitHub repo and pulled via `/codeload/repo`.
- **Backtest execution is synchronous**: `zipline.backtest()` blocks until complete (runs in thread pool to avoid blocking async event loop).
- **Object store is region-agnostic**: For S3, the region is only used for signing; the actual endpoint is determined by AWS SDK defaults (or `OBJECT_STORE_ENDPOINT` for MinIO).
- **Test markers**: Use `-m "not slow"` to skip integration tests that require a running QuantRocket instance and LLM.