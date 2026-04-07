This repo contains a agent that helps convert natural language trading strategies into quantrocket's zipline backtesting code, and users can use the UI to start backtests using the generated code. If the code is invalid or throws an error when the backtest is started, it will be sent back to the agent along with the error to regenerate the code.

Important files: 
- services/agent_service: handles the agent and user interactions with it
- services/backtest_worker: handles backtesting requests from users

There are two mcp severs, one for my UI's usage, and one designed for agents like claude to connect to to work. The latter version has backtesting endpoints. The details are in the mcp_server folder.