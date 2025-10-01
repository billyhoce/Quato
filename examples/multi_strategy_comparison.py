"""Multi-Strategy Comparison Example.

This example demonstrates comparing multiple trading strategies side-by-side
to identify the best performer.
"""

from datetime import datetime
from typing import List, Dict, Any
from hypothesis_generation.generator import Hypothesis
from strategy_coder import StrategyCoder
from backtesting_orchestrator import BacktestingOrchestrator, BacktestConfig, BacktestResults


def create_strategies() -> List[Hypothesis]:
    """Create multiple strategy hypotheses for comparison.
    
    Returns:
        List of strategy hypotheses
    """
    strategies = [
        Hypothesis(
            id="strat_001",
            title="RSI Mean Reversion",
            description="Buy when RSI < 30, sell when RSI > 70",
            market="equities",
            timeframe="daily",
            score=0.75,
            generated_at=datetime.now(),
            tags=["mean_reversion", "RSI"]
        ),
        Hypothesis(
            id="strat_002",
            title="Moving Average Crossover",
            description="Buy on 50/200 MA golden cross, sell on death cross",
            market="equities",
            timeframe="daily",
            score=0.68,
            generated_at=datetime.now(),
            tags=["momentum", "moving_average"]
        ),
        Hypothesis(
            id="strat_003",
            title="Breakout Strategy",
            description="Buy on 20-day high breakout with volume confirmation",
            market="equities",
            timeframe="daily",
            score=0.81,
            generated_at=datetime.now(),
            tags=["breakout", "momentum"]
        ),
        Hypothesis(
            id="strat_004",
            title="Pairs Trading",
            description="Trade spread between correlated stock pairs",
            market="equities",
            timeframe="daily",
            score=0.73,
            generated_at=datetime.now(),
            tags=["mean_reversion", "pairs", "statistical_arbitrage"]
        ),
    ]
    return strategies


def print_comparison_table(results_dict: Dict[str, BacktestResults]) -> None:
    """Print a formatted comparison table of strategy results.
    
    Args:
        results_dict: Dictionary mapping strategy IDs to results
    """
    print("\n" + "=" * 120)
    print("STRATEGY COMPARISON TABLE")
    print("=" * 120)
    
    headers = ["Strategy ID", "Total Return", "Sharpe", "Max DD", "Win Rate", "Trades"]
    col_widths = [20, 15, 10, 12, 12, 10]
    
    # Print header
    header_row = ""
    for header, width in zip(headers, col_widths):
        header_row += f"{header:^{width}}"
    print(header_row)
    print("-" * 120)
    
    # Print data rows
    for strategy_id, results in results_dict.items():
        row = f"{strategy_id:<20}"
        row += f"{results.total_return:>14.2%}"
        row += f"{results.sharpe_ratio:>10.2f}"
        row += f"{results.max_drawdown:>11.2%}"
        row += f"{results.win_rate:>11.2%}"
        row += f"{results.num_trades:>10}"
        print(row)
    
    print("=" * 120)


def main() -> None:
    """Run multi-strategy comparison example."""
    print("=" * 80)
    print("Multi-Strategy Comparison Example")
    print("=" * 80)
    
    # Create strategies
    print("\n[1] Creating strategy hypotheses...")
    strategies = create_strategies()
    print(f"Created {len(strategies)} strategy hypotheses")
    for strategy in strategies:
        print(f"  - {strategy.title} (score: {strategy.score})")
    
    # Generate code for each strategy
    print("\n[2] Generating strategy code...")
    coder = StrategyCoder(model="gpt-4")
    strategy_codes = {}
    
    for strategy in strategies:
        print(f"  Generating code for: {strategy.title}")
        code = coder.generate_strategy_code(
            hypothesis=strategy.__dict__,
            template="basic"
        )
        if coder.validate_code(code):
            strategy_codes[strategy.id] = code
            print(f"    ✓ Code generated and validated")
        else:
            print(f"    ✗ Code validation failed")
    
    # Setup backtesting
    print("\n[3] Setting up backtesting environment...")
    orchestrator = BacktestingOrchestrator()
    
    # Common backtest configuration
    base_config = BacktestConfig(
        strategy_id="",  # Will be set for each strategy
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2023, 12, 31),
        initial_capital=100000.0,
        commission=0.001
    )
    
    # Run backtests
    print("\n[4] Running backtests...")
    results_dict: Dict[str, BacktestResults] = {}
    
    for strategy_id, strategy_code in strategy_codes.items():
        print(f"\n  Running backtest for: {strategy_id}")
        
        config = BacktestConfig(
            strategy_id=strategy_id,
            start_date=base_config.start_date,
            end_date=base_config.end_date,
            initial_capital=base_config.initial_capital,
            commission=base_config.commission
        )
        
        results = orchestrator.run_backtest(
            strategy_code=strategy_code.code,
            config=config
        )
        
        results_dict[strategy_id] = results
        print(f"    Return: {results.total_return:.2%}, Sharpe: {results.sharpe_ratio:.2f}")
    
    # Display comparison
    print_comparison_table(results_dict)
    
    # Compare strategies programmatically
    print("\n[5] Comparing strategies...")
    comparison = orchestrator.compare_strategies(list(results_dict.keys()))
    
    # Find best strategy by Sharpe ratio
    best_strategy_id = max(results_dict.keys(), key=lambda k: results_dict[k].sharpe_ratio)
    best_results = results_dict[best_strategy_id]
    
    print("\n" + "=" * 80)
    print("BEST STRATEGY")
    print("=" * 80)
    print(f"Strategy ID: {best_strategy_id}")
    print(f"Total Return: {best_results.total_return:.2%}")
    print(f"Sharpe Ratio: {best_results.sharpe_ratio:.2f}")
    print(f"Max Drawdown: {best_results.max_drawdown:.2%}")
    print(f"Win Rate: {best_results.win_rate:.2%}")
    
    # Generate detailed report for best strategy
    print("\n[6] Generating detailed report for best strategy...")
    report = orchestrator.generate_report(
        results=best_results,
        output_path=f"/tmp/best_strategy_{best_strategy_id}_report.md"
    )
    print(f"Report saved to: /tmp/best_strategy_{best_strategy_id}_report.md")
    
    # Summary statistics
    print("\n[7] Summary Statistics:")
    print(f"  Total strategies tested: {len(results_dict)}")
    avg_return = sum(r.total_return for r in results_dict.values()) / len(results_dict)
    avg_sharpe = sum(r.sharpe_ratio for r in results_dict.values()) / len(results_dict)
    print(f"  Average return: {avg_return:.2%}")
    print(f"  Average Sharpe ratio: {avg_sharpe:.2f}")
    print(f"  Best strategy: {best_strategy_id}")
    
    print("\n" + "=" * 80)
    print("Example Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
