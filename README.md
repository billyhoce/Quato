# Quato

An LLM-powered platform that converts plain-text trading strategy ideas into runnable [QuantRocket Zipline](https://www.quantrocket.com/docs/api/zipline/) backtests, executes them, and presents the results — all from a chat interface or directly through Claude via MCP.

## Overview

Quato has three components:

1. **Backtesting engine** — a Redis-queued, distributed backtest runner that executes Zipline strategies against a QuantRocket instance and stores results in S3-compatible object storage (MinIO).
2. **Agent backend** — a FastAPI server hosting a LangGraph agent (Claude Sonnet) that generates Zipline code from natural language, plus an MCP server that exposes backtesting tools over HTTP.
3. **Frontend** — a React (Vite + Tailwind) chat UI for interacting with the agent, viewing strategies, and reviewing backtest results.

All three run as Docker containers on a single instance, with Caddy handling TLS and routing.

## Workflows

Quato supports two ways to create and run backtests:

### Workflow 1: Native agent (chat UI)

Use the built-in chat interface to collaborate with the agent:

1. Open the frontend and describe a strategy in plain English (e.g. "Create a momentum strategy that buys the top 10 stocks by 12-month return").
2. The agent uses Zipline/Pipeline API docs (via MCP tools) to generate valid Zipline Python code.
3. Review the generated strategy code in the UI. Ask follow-up questions or request revisions.
4. When satisfied, submit the strategy for backtesting — configure the date range, data bundle, and capital.
5. The backtest is queued and executed against QuantRocket. Poll for status or wait for completion.
6. View results: total return, Sharpe ratio, max drawdown, execution time, and download the full results CSV or tear sheet PDF.

### Workflow 2: MCP server (Claude Desktop / claude.ai)

Connect Claude directly to Quato's MCP server for a fully automated workflow:

1. Add Quato as a remote MCP server in Claude Desktop or claude.ai, pointing to `https://<your-domain>:8443/mcp`.
2. Claude gains access to these tools:
   - `get_functions_in_category` / `get_function_or_class_details` — browse Zipline and Pipeline API docs
   - `list_universes` / `search_securities` / `create_universe` / `delete_universe` — manage QuantRocket security universes
   - `submit_backtest` — submit Zipline strategy code for execution
   - `wait_for_backtest` — block until a backtest completes and return results
   - `get_backtest_results` — fetch results and download URLs for a completed backtest
3. Ask Claude to design and backtest a strategy. Claude will write the code, submit it, wait for results, and interpret the performance — all in one conversation.

## Tech stack

| Concern | Technology |
|---|---|
| Frontend | React 19, Vite, Tailwind CSS 4 |
| API server | FastAPI |
| LLM (agent) | Claude Sonnet via LangChain |
| Agent framework | LangGraph |
| MCP servers | FastMCP (stdio for internal agent, HTTP for external clients) |
| Session & strategy state | Redis |
| Conversation history | Redis (LangGraph `AsyncRedisSaver`) |
| Backtest queue & locking | Redis |
| Backtest execution | QuantRocket / Zipline |
| Strategy delivery to QuantRocket | GitHub (commit + pull workflow) |
| Backtest result storage | MinIO (S3-compatible object store) |
| Reverse proxy & TLS | Caddy (with Cloudflare DNS challenge) |

---

## Setup guide

### Prerequisites

- Docker and Docker Compose
- A running [QuantRocket](https://www.quantrocket.com/) instance
- A GitHub repository for storing strategy files (used as a bridge to QuantRocket)
- API keys (see environment variables below)

### 1. Clone the repo

```bash
git clone https://github.com/billyhoce/Quato.git
cd Quato
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```bash
# --- LLM ---
ANTHROPIC_API_KEY=              # Claude API key (used by the agent)
GOOGLE_API_KEY=                 # Google Gemini API key (optional, for strategy summaries)
GOOGLE_GENAI_USE_VERTEXAI=True  # Set to True if using Vertex AI

# --- QuantRocket ---
HOUSTON_URL=https://your-quantrocket-host
HOUSTON_USERNAME=               # QuantRocket username
HOUSTON_PASSWORD=               # QuantRocket password

# --- GitHub (strategy file bridge to QuantRocket) ---
GITHUB_TOKEN=                   # Personal access token with repo contents read/write
GITHUB_USERNAME=                # Your GitHub username
REPO_PATH=user/repo             # e.g. billyhoce/quato-strategies

# --- Redis ---
REDIS_URL=redis://redis:6379    # Use "redis://redis:6379" for Docker, "redis://localhost:6379" for local dev

# --- Object store (MinIO) ---
OBJECT_STORE_ENDPOINT=http://minio:9000       # Use "http://minio:9000" for Docker, "http://localhost:9000" for local dev
OBJECT_STORE_ACCESS_KEY=minioadmin
OBJECT_STORE_SECRET_KEY=minioadmin
OBJECT_STORE_BUCKET=quato-backtests
OBJECT_STORE_REGION=us-east-1
OBJECT_STORE_PUBLIC_ENDPOINT=https://minio.yourdomain.com:9443  # Public URL for presigned download links

# --- Caddy / TLS (production) ---
CF_API_TOKEN=                   # Cloudflare API token for DNS-01 TLS challenge

# --- LangSmith tracing (optional) ---
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=Quato
```

### 3. Update the Caddyfile (production)

Edit `Caddyfile` and replace `app.quato.space` and `minio.quato.space` with your own domain names. If running locally without TLS, use `docker-compose.dev.yml` instead (see below).

### 4. Start everything

**Production** (Caddy with TLS, frontend built as static files):

```bash
docker compose up -d --build
```

This starts five containers:
- `quato-redis` — Redis for state, queue, and conversation history
- `quato-minio` — MinIO object store for backtest results
- `quato-frontend-build` — builds the React frontend into static files, then exits
- `quato-backend` — FastAPI server + agent + MCP server + backtest worker
- `quato-caddy` — Caddy reverse proxy with automatic TLS

**Development** (hot-reload frontend, backend exposed on port 8000):

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

This starts:
- `quato-redis` — Redis (no persistence, faster for dev)
- `quato-minio` — MinIO with web console at [http://localhost:9001](http://localhost:9001)
- `quato-backend` — FastAPI on [http://localhost:8000](http://localhost:8000)
- `quato-frontend` — Vite dev server on [http://localhost:5173](http://localhost:5173)

### 5. QuantRocket setup

Your QuantRocket instance needs IBKR listings collected and a data bundle ingested before backtests can run. Scripts in `quantrocket_setup_scripts/` can help with this. At minimum:

1. Activate your QuantRocket license
2. Collect IBKR listings (US stocks)
3. Ingest the `usstock-learn-1d` free daily bundle (or your preferred bundle)

Refer to the [QuantRocket docs](https://www.quantrocket.com/docs/) for details.

---

## Architecture

### Deployment

```
Internet
  │
  ▼
Caddy (:8443 / :9443)
  ├── app.yourdomain.com → Frontend static files + /api/* → Backend
  └── minio.yourdomain.com → MinIO S3 API
         │
   ┌─────┴──────┐
   │  Backend   │──→ Redis
   │  (FastAPI) │──→ MinIO
   │            │──→ QuantRocket (via HOUSTON_URL)
   │            │──→ GitHub (strategy upload)
   └────────────┘
```

### Project structure

```
Quato/
├── frontend/                        # React UI (Vite + Tailwind)
│   ├── src/
│   ├── Dockerfile.frontend          # Production build (static files)
│   └── Dockerfile.frontend.dev      # Dev server with hot reload
├── agent_backend/
│   ├── api/main.py                  # FastAPI app, all HTTP endpoints, MCP mount
│   ├── agent/
│   │   ├── agent_service.py         # LangGraph agent (Claude Sonnet)
│   │   ├── strategy_manager.py      # Per-session strategy & turn state in Redis
│   │   └── constants.py             # System prompt
│   └── mcp_server/
│       ├── quato_server.py          # Internal MCP server (stdio, used by agent)
│       ├── external_server.py       # External MCP server (HTTP, mounted at /mcp)
│       └── tools.py                 # Shared tool implementations
├── backtesting/
│   ├── orchestrator/                # QuantRocket/Zipline execution
│   ├── queue/
│   │   ├── backtest_queue.py        # Redis-based job queue
│   │   └── backtest_worker.py       # Async worker loop
│   ├── models/                      # Pydantic data models
│   └── storage/                     # MinIO/S3 object store
├── quantrocket_setup_scripts/       # Helper scripts for QuantRocket setup
├── docker-compose.yml               # Production (Caddy + static frontend)
├── docker-compose.dev.yml           # Development (Vite dev server)
├── Dockerfile                       # Backend image
├── Dockerfile.caddy                 # Caddy with Cloudflare DNS plugin
├── Caddyfile                        # Reverse proxy config
├── config.py                        # Tunable constants
└── requirements.txt                 # Python dependencies
```

### Backtest execution flow

1. `POST /api/backtest` (or `submit_backtest` via MCP) creates a task in Redis and pushes it onto the FIFO queue
2. The `BacktestWorker` dequeues the task and acquires a distributed Redis lock (only one backtest runs globally at a time)
3. Strategy code is committed to GitHub and pulled into QuantRocket via `/codeload/repo`
4. `zipline.backtest()` runs on the QuantRocket instance
5. Results CSV and tear sheet PDF are uploaded to MinIO; summary metrics are written to the task hash in Redis
6. The lock is released and temporary files are cleaned up

### Session identity

The `X-Session-ID` header is the sole user identity mechanism. The client generates a UUID on first load and sends it with every request. All per-user state (strategy code, conversation history, backtest history) is keyed by this ID in Redis.

---

## Configuration

Tunable values in `config.py`:

| Setting | Default | Description |
|---|---|---|
| `BACKTEST_LOCK_TTL_SECONDS` | 10800 (3 h) | Distributed lock TTL; set above your longest expected backtest |
| `WORKER_QUEUE_TIMEOUT_SECONDS` | 5 | How long a worker blocks waiting for a queued task |
| `WORKER_SHUTDOWN_TIMEOUT_SECONDS` | 30.0 | Grace period for the worker to finish on server shutdown |
| `WORKER_CLEANUP_INTERVAL_SECONDS` | 900 (15 min) | How often the periodic stale-task cleanup runs |

---

## API reference

See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for the full endpoint reference.

---

**Note**: This project is for research and educational purposes. Always validate strategies thoroughly before deploying with real capital.
