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

4. **Configure environment variables**:
   Create a `.env` file in the project root:
   ```bash
   # LLM API Configuration
   OPENAI_API_KEY=your_api_key_here
   LLM_MODEL=gpt-4

   # QuantRocket Configuration
   QUANTROCKET_URL=http://localhost:1969
   ```

5. **Verify installation**:
   ```bash
   python -c "import hypothesis_generation, strategy_coder, backtesting_orchestrator, refinement_agent; print('Quato modules loaded successfully!')"
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
