# Quato Architecture: Agent & Backtest Execution

## Two Agent Paths

Quato exposes its backtesting capabilities through two distinct agent interfaces, each with different tool sets and responsibilities.

### Internal Agent (LangGraph via UI)

The internal agent is a LangGraph-based assistant served through the React frontend. It connects to an MCP server (`quato_server.py`) over stdio.

**Available tools:** API documentation lookup, universe management (list, search, create, delete).

**Not available:** Backtest submission, waiting, or result retrieval.

**Rationale:** The frontend already has dedicated UI controls for backtest execution: a configuration form, a "Run Backtest" button, a history panel with status polling, and detail modals. Giving the agent backtest tools would create two competing execution paths, leading to:

- **Timeout issues:** The agent's `wait_for_backtest` tool blocks for up to 300 seconds. Since the frontend communicates with the backend through Cloudflare, this triggers 524 gateway timeouts on Cloudflare's free tier.
- **State confusion:** The user wouldn't know whether the agent or the UI initiated a backtest, making it harder to track what's running.
- **Redundant infrastructure:** The UI already has polling, progress display, and error handling for backtests.

Instead, the agent focuses on strategy code generation. The user runs backtests through the UI, and when a backtest fails, the frontend automatically sends the error to the agent as a system message so it can fix the code.

### External Agent (Claude via HTTP MCP)

External Claude users (via Claude Desktop or claude.ai) connect to an HTTP MCP server (`external_server.py`). This server exposes **all tools**, including backtest submission, waiting, and result retrieval.

**Rationale:** External Claude has no UI — it must be fully autonomous. It submits backtests, waits for results, handles timeouts and retries, and reports back to the user entirely through conversation.

## Backtest Execution Flow (UI Path)

```
User clicks "Run Backtest"
    |
    v
Frontend calls POST /api/backtest directly
    |
    v
Backend queues task in Redis, returns task_id
    |
    v
Frontend polls GET /api/backtest/history every 5s
    |
    +-- On success: History panel updates automatically
    |
    +-- On failure: System message sent to agent
            |
            v
        Agent reads error, fixes strategy code
            |
            v
        User clicks "Run Backtest" again
```

## Backtest Execution Flow (External Claude Path)

```
User describes strategy in conversation
    |
    v
Claude generates strategy code
    |
    v
Claude calls submit_backtest tool
    |
    v
Claude calls wait_for_backtest (retries on pending/524)
    |
    +-- On success: Claude summarizes results
    |
    +-- On failure: Claude fixes code and resubmits (up to 15 retries)
```
