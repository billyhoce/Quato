# Quato Examples

This directory contains example scripts demonstrating how to use Quato for automated quantitative strategy research.

## Running Examples

All examples should be run from the project root directory with the PYTHONPATH set:

```bash
cd /path/to/Quato
PYTHONPATH=. python examples/<example_name>.py
```

Or on Windows:
```cmd
cd C:\path\to\Quato
set PYTHONPATH=.
python examples\<example_name>.py
```

## Available Examples

### 1. basic_workflow.py

**Description**: Demonstrates the complete end-to-end Quato workflow.

**What it shows**:
- Generating trading hypotheses from market data
- Converting hypotheses to executable strategy code
- Running backtests
- Analyzing results
- Iteratively refining strategies
- Generating reports

**Run**:
```bash
PYTHONPATH=. python examples/basic_workflow.py
```

### 2. momentum_strategy.py

**Description**: Creates and tests a dual momentum trading strategy.

**What it shows**:
- Creating a momentum-based hypothesis
- Generating strategy code with momentum template
- Backtesting on multiple tech stocks
- Detailed performance analysis
- Exporting strategy code to file

**Run**:
```bash
PYTHONPATH=. python examples/momentum_strategy.py
```

### 3. mean_reversion_strategy.py

**Description**: Implements a Bollinger Bands mean reversion strategy.

**What it shows**:
- Mean reversion hypothesis creation
- Strategy refinement loop
- Performance comparison before/after refinement
- Detailed refinement explanations
- Report generation

**Run**:
```bash
PYTHONPATH=. python examples/mean_reversion_strategy.py
```

### 4. multi_strategy_comparison.py

**Description**: Compares multiple trading strategies side-by-side.

**What it shows**:
- Creating multiple strategy hypotheses
- Batch code generation and validation
- Running parallel backtests
- Strategy performance comparison
- Identifying best performing strategy

**Run**:
```bash
PYTHONPATH=. python examples/multi_strategy_comparison.py
```

## Output Files

Examples generate output files in `/tmp/` directory:
- `quato_backtest_report.md` - Detailed backtest report
- `momentum_strategy_report.md` - Momentum strategy results
- `mean_reversion_report.md` - Mean reversion strategy results
- `best_strategy_*_report.md` - Best strategy from comparison
- `momentum_strategy.py` - Exported strategy code

## Customization

You can customize the examples by:
- Changing the date ranges for backtests
- Modifying initial capital and commission rates
- Adding different symbols/markets
- Adjusting refinement parameters
- Creating your own hypothesis definitions

## Notes

- These are placeholder examples with mock data
- In production, integrate with real QuantRocket data
- Set up your LLM API keys before running
- Adjust parameters based on your trading objectives
