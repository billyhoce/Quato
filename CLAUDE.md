This repo contains three components, a backtesting adapter for quantrocket's zipline backtesting including a redis queue management system, a agent backend that contains an MCP server that exposes backtesting capabilities to agents as well as a implementation of an agent, and lastly a frontend component.

The idea is to allow agents to draft backtesting strategies from plaintext and automatically backtest them and review the results with the user.

My deployment architecture:
1 singular instance, hosting quantrocket, backend, and frontend in docker containers. Routing is handled with caddy.

Repository structure:
- frontend/: React UI
- agent_backend/: FastAPI server, LangGraph agent, and MCP servers
  - agent_backend/api/main.py: FastAPI app and all HTTP endpoints
  - agent_backend/agent/agent_service.py: handles the agent and user interactions with it
  - agent_backend/mcp_server/quato_server.py: internal MCP server (stdio, used by local agent)
  - agent_backend/mcp_server/external_server.py: external MCP server (HTTP, for Claude to connect to)
- backtesting/: pure backtesting engine with no agent coupling
  - backtesting/queue/backtest_worker.py: handles backtesting requests from queue
  - backtesting/queue/backtest_queue.py: Redis-based job queue
  - backtesting/orchestrator/: QuantRocket/Zipline execution
  - backtesting/models/: Pydantic data models
  - backtesting/storage/: MinIO/S3 object store