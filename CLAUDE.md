This repo contains a agent that helps convert natural language trading strategies into quantrocket's zipline backtesting code, and users can use the UI to start backtests using the generated code. If the code is invalid or throws an error when the backtest is started, it will be sent back to the agent along with the error to regenerate the code.

Important files: 
- services/agent_service: handles the agent and user interactions with it
- services/backtest_worker: handles backtesting requests from users