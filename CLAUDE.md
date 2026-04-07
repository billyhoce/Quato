This repo contains a agent that helps convert natural language trading strategies into quantrocket's zipline backtesting code, and users can use the UI to start backtests using the generated code. If the code is invalid or throws an error when the backtest is started, it will be sent back to the agent along with the error to regenerate the code.

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