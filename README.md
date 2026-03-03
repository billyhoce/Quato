# Quato

An LLM-Powered Agent for Automated Quantitative Strategy Research

## Overview

Quato is an intelligent agent that automates the quantitative trading strategy research process using Large Language Models (LLMs) and QuantRocket. It combines the creative capabilities of LLMs with systematic backtesting to generate, code, test, and refine trading strategies autonomously.

### Key Features

- **Hypothesis Generation**: Automatically generates trading strategy ideas from market data, research papers, and historical patterns
- **Strategy Coding**: Translates hypotheses into executable QuantRocket strategy code with proper risk management
- **Backtesting Orchestration**: Manages the complete backtesting lifecycle with comprehensive performance analysis
- **Iterative Refinement**: Analyzes results and automatically refines strategies to improve performance

### Architecture

Quato consists of four main modules that work together in an automated pipeline:

1. **hypothesis_generation/**: Generates novel trading strategy hypotheses using LLM analysis
2. **strategy_coder/**: Translates hypotheses into executable QuantRocket Python code
3. **backtesting_orchestrator/**: Executes backtests and analyzes performance metrics
4. **refinement_agent/**: Iteratively refines strategies based on backtest results

## Installation

### Prerequisites

- Python 3.8 or higher
- QuantRocket account and installation (for strategy execution)
- OpenAI API key or other LLM API access

### Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone https://github.com/billyhoce/Quato.git
   cd Quato
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up Redis** (required for distributed backtesting):
   
   Redis is used as a distributed task queue to manage backtest execution across multiple server instances.
   
   **Option A: Using Docker (Recommended for Development)**
   ```bash
   docker run -d -p 6379:6379 --name quato-redis redis:7-alpine
   ```
   
   **Option B: Using Homebrew (macOS)**
   ```bash
   brew install redis
   brew services start redis
   ```
   
   **Option C: Using apt (Ubuntu/Debian)**
   ```bash
   sudo apt update
   sudo apt install redis-server
   sudo systemctl start redis-server
   ```
   
   **Production Deployment**: For production, use a managed Redis service:
   - AWS ElastiCache
   - Redis Cloud
   - Google Cloud Memorystore
   - Azure Cache for Redis
   
   **Verify Redis is running**:
   ```bash
   redis-cli ping
   # Should respond with: PONG
   ```

5. **Configure environment variables**:
   Create a `.env` file in the project root:
   ```bash
   # LLM API Configuration
   OPENAI_API_KEY=your_api_key_here
   LLM_MODEL=gpt-4

   # QuantRocket Configuration
   QUANTROCKET_URL=http://localhost:1969
   
   # Redis Configuration (for distributed backtesting)
   REDIS_URL=redis://localhost:6379

   # Langsmith Tracing (Optional - for debugging agent behavior)
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_API_KEY=your_langsmith_api_key
   LANGCHAIN_PROJECT=quato-strategy-coder
   ```

6. **Set up Langsmith tracing** (Optional):
   Langsmith provides powerful tracing and debugging capabilities for the agent's decision-making process:
   - Sign up at [smith.langchain.com](https://smith.langchain.com)
   - Create a new project named "quato-strategy-coder" (or use your preferred name)
   - Generate an API key from your account settings
   - Add the API key to your `.env` file
   - View traces at [smith.langchain.com](https://smith.langchain.com) while running the agent

7. **Verify installation**:
   ```bash
   python -c "import hypothesis_generation, strategy_coder, backtesting_orchestrator, refinement_agent; print('Quato modules loaded successfully!')"
   ```

## Configuration

### Application Settings

Main configuration is in [config.py](config.py). Key settings:

- **`BACKTEST_LOCK_TTL_SECONDS`** (default: 10800 = 3 hours)
  - Distributed lock timeout for backtest execution
  - Prevents deadlocks if a server crashes while running a backtest
  - Set this higher than your longest expected backtest duration
  - Auto-releases lock if server crashes, allowing recovery

- **`WORKER_QUEUE_TIMEOUT_SECONDS`** (default: 5)
  - How long worker waits for new tasks before checking shutdown flag
  - Lower values = faster shutdown, higher CPU usage

- **`WORKER_SHUTDOWN_TIMEOUT_SECONDS`** (default: 30.0)
  - Grace period for worker to finish current task on shutdown
  - Increase if your backtests need more time to complete gracefully

- **`WORKER_CLEANUP_INTERVAL_SECONDS`** (default: 900 = 15 minutes)
  - How often the worker runs cleanup to detect stale running tasks
  - Automatically marks tasks as failed if they've been running longer than `BACKTEST_LOCK_TTL_SECONDS`
  - Prevents orphaned tasks from staying in "running" status indefinitely

### Multi-Instance Deployment

When running multiple FastAPI server instances (for high availability or load balancing):

1. **All instances share the same Redis** - Point all instances to the same `REDIS_URL`
2. **Only one backtest runs at a time** - Distributed lock ensures sequential execution on the shared QuantRocket instance
3. **Startup recovery is safe** - When a server restarts, it only marks tasks as failed if NO lock is held, preventing killing of active backtests running on other servers
4. **Lock auto-expires** - If a server crashes while holding the lock, it auto-releases after `BACKTEST_LOCK_TTL_SECONDS`
5. **Periodic cleanup** - Every 15 minutes, workers check for stale running tasks (running > 3 hours) and mark them as failed
6. **Efficient dequeuing** - Workers check for active lock before dequeuing, minimizing task re-queue churn

**How multiple workers coordinate:**
- Before dequeuing, workers check if a backtest is running (lock exists)
- If lock exists, workers sleep instead of dequeuing unnecessary tasks
- If no lock, worker dequeues and attempts to acquire lock
- Small race window exists (multiple workers may dequeue simultaneously), but lock ensures only one executes
- Failed lock attempts safely re-queue the task for next worker

### Failure Recovery Scenarios

| Scenario | What Happens | When Task Marked Failed |
|----------|--------------|------------------------|
| Server crashes mid-backtest, other servers running | Lock expires after 3h, other servers continue | Within 15 min of lock expiration (periodic cleanup) ✅ |
| Server crashes mid-backtest, no other servers | Lock expires after 3h | When any server restarts (startup recovery) ✅ |
| All servers crash mid-backtest | Lock expires after 3h, tasks orphaned | When first server restarts (startup recovery) ✅ |
| Server A running backtest, Server B restarts | Server B sees lock held, skips recovery | Never - backtest completes normally ✅ |
| Task runs > 3 hours (legitimate long backtest) | Lock expires, task continues if server is healthy | After 3h by periodic cleanup (configure longer TTL if needed) ⚠️ |

**Key Points:**
- **Startup recovery** runs once when a server starts - only cleans up if no lock exists
- **Periodic cleanup** runs every 15 minutes on all servers - detects stale tasks even without restart
- Tasks running longer than `BACKTEST_LOCK_TTL_SECONDS` are considered stale and marked as failed
- If your backtests take >3 hours, increase `BACKTEST_LOCK_TTL_SECONDS` in [config.py](config.py)

**Example multi-instance setup:**
```bash
# Terminal 1
uvicorn api.main:app --host 0.0.0.0 --port 8000

# Terminal 2  
uvicorn api.main:app --host 0.0.0.0 --port 8001

# Both share the same Redis and QuantRocket instance
```

## Usage

### Basic Workflow

Here's a complete example of using Quato to generate and test a trading strategy:

```python
from hypothesis_generation import HypothesisGenerator
from strategy_coder import StrategyCoder
from backtesting_orchestrator import BacktestingOrchestrator, BacktestConfig
from refinement_agent import RefinementAgent
from datetime import datetime

# Step 1: Generate hypotheses
generator = HypothesisGenerator(model="gpt-4")
market_data = {...}  # Your market data
hypotheses = generator.generate_from_market_data(market_data, num_hypotheses=5)
top_hypothesis = generator.get_top_hypotheses(n=1)[0]

# Step 2: Generate strategy code
coder = StrategyCoder(model="gpt-4")
strategy_code = coder.generate_strategy_code(top_hypothesis)
coder.validate_code(strategy_code)

# Step 3: Run backtest
orchestrator = BacktestingOrchestrator()
config = BacktestConfig(
    strategy_id=strategy_code.hypothesis_id,
    start_date=datetime(2020, 1, 1),
    end_date=datetime(2023, 12, 31),
    initial_capital=100000
)
results = orchestrator.run_backtest(strategy_code.code, config)

# Step 4: Refine strategy
agent = RefinementAgent(model="gpt-4", max_iterations=5)
refined_result = agent.iterative_refinement(
    initial_strategy_code=strategy_code.code,
    initial_results=results.__dict__,
    target_metric="sharpe_ratio",
    target_value=2.0
)

# Step 5: Generate report
report = orchestrator.generate_report(results)
print(report)
```

### Module-Specific Usage

#### Hypothesis Generation

```python
from hypothesis_generation import HypothesisGenerator

generator = HypothesisGenerator()

# Generate from research papers
hypotheses = generator.generate_from_research(
    research_papers=["path/to/paper1.pdf", "path/to/paper2.pdf"],
    num_hypotheses=3
)

# Score and rank hypotheses
for hypothesis in hypotheses:
    score = generator.score_hypothesis(hypothesis)
    print(f"{hypothesis.title}: {score}")
```

#### Strategy Coding

```python
from strategy_coder import StrategyCoder

coder = StrategyCoder()

# Generate strategy code
strategy_code = coder.generate_strategy_code(
    hypothesis=hypothesis_dict,
    template="momentum"
)

# Validate and export
if coder.validate_code(strategy_code):
    coder.export_to_file(strategy_code, "strategies/my_strategy.py")
```

#### Backtesting

```python
from backtesting_orchestrator import BacktestingOrchestrator, BacktestConfig

orchestrator = BacktestingOrchestrator()

# Prepare data
data = orchestrator.prepare_data(
    symbols=["AAPL", "GOOGL", "MSFT"],
    start_date=datetime(2020, 1, 1),
    end_date=datetime(2023, 12, 31)
)

# Run backtest
config = BacktestConfig(
    strategy_id="momentum_v1",
    start_date=datetime(2020, 1, 1),
    end_date=datetime(2023, 12, 31),
    initial_capital=100000
)
results = orchestrator.run_backtest(strategy_code, config)

# Analyze and compare
analysis = orchestrator.analyze_results(results)
comparison = orchestrator.compare_strategies(["momentum_v1", "momentum_v2"])
```

#### Strategy Refinement

```python
from refinement_agent import RefinementAgent

agent = RefinementAgent(max_iterations=5)

# Analyze performance
analysis = agent.analyze_performance(backtest_results)

# Generate and apply refinements
suggestions = agent.generate_refinement_suggestions(analysis, strategy_code)
refined_code = agent.apply_refinement(suggestions[0], strategy_code)

# View refinement history
history = agent.get_refinement_history()
```

## Examples

The `examples/` directory contains complete end-to-end examples:

- **basic_workflow.py**: Simple example of the complete Quato pipeline
- **momentum_strategy.py**: Momentum strategy generation and testing
- **mean_reversion_strategy.py**: Mean reversion strategy example
- **multi_strategy_comparison.py**: Comparing multiple strategies

Run an example:
```bash
python examples/basic_workflow.py
```

## Project Structure

```
Quato/
├── hypothesis_generation/     # Hypothesis generation module
│   ├── __init__.py
│   └── generator.py
├── strategy_coder/           # Strategy coding module
│   ├── __init__.py
│   └── coder.py
├── backtesting_orchestrator/ # Backtesting module
│   ├── __init__.py
│   └── orchestrator.py
├── refinement_agent/         # Refinement module
│   ├── __init__.py
│   └── agent.py
├── examples/                 # Usage examples
│   ├── basic_workflow.py
│   ├── momentum_strategy.py
│   ├── mean_reversion_strategy.py
│   └── multi_strategy_comparison.py
├── requirements.txt          # Python dependencies
├── README.md                # This file
├── .gitignore              # Git ignore rules
└── .env.example            # Environment variable template
```

## Development

### Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Style

- Follow PEP 8 guidelines
- Use type hints for all function signatures
- Include docstrings for all public classes and methods
- Run tests before submitting PRs

### Testing

Run tests with:
```bash
pytest tests/
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- QuantRocket for providing the backtesting infrastructure
- OpenAI for LLM capabilities
- The quantitative trading research community

## Support

For issues, questions, or contributions, please:
- Open an issue on GitHub
- Contact the maintainers
- Check the documentation

## Roadmap

- [ ] Add support for multiple LLM providers (Anthropic, Cohere, etc.)
- [ ] Implement real-time strategy monitoring
- [ ] Add portfolio-level optimization
- [ ] Create web-based dashboard for strategy management
- [ ] Integrate additional data sources
- [ ] Add machine learning-based refinement techniques

---

**Note**: This project is for educational and research purposes. Always validate strategies thoroughly before deploying with real capital.
