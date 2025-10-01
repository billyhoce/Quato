"""Momentum Strategy Example.

This example demonstrates creating and testing a momentum-based trading strategy.
"""

from datetime import datetime
from hypothesis_generation import HypothesisGenerator
from hypothesis_generation.generator import Hypothesis
from strategy_coder import StrategyCoder
from backtesting_orchestrator import BacktestingOrchestrator, BacktestConfig


def create_momentum_hypothesis() -> Hypothesis:
    """Create a momentum strategy hypothesis.
    
    Returns:
        Hypothesis object for momentum strategy
    """
    return Hypothesis(
        id="mom_001",
        title="Dual Momentum Strategy",
        description="""
        Buy stocks that show strong momentum over both 3-month and 6-month periods.
        
        Entry Rules:
        - Stock's 3-month return > market return
        - Stock's 6-month return > market return
        - Stock's 20-day volume > average volume
        
        Exit Rules:
        - Stock's 1-month return < market return
        - Stop loss at -10%
        
        Position Sizing:
        - Equal weight across selected stocks
        - Maximum 10 positions
        """,
        market="equities",
        timeframe="daily",
        score=0.78,
        generated_at=datetime.now(),
        tags=["momentum", "multi_timeframe", "relative_strength"]
    )


def main() -> None:
    """Run momentum strategy example."""
    print("=" * 80)
    print("Momentum Strategy Example")
    print("=" * 80)
    
    # Create hypothesis
    print("\n[1] Creating momentum hypothesis...")
    hypothesis = create_momentum_hypothesis()
    print(f"Hypothesis: {hypothesis.title}")
    print(f"Score: {hypothesis.score}")
    print(f"Tags: {', '.join(hypothesis.tags)}")
    
    # Generate strategy code
    print("\n[2] Generating strategy code...")
    coder = StrategyCoder(model="gpt-4")
    strategy_code = coder.generate_strategy_code(
        hypothesis=hypothesis.__dict__,
        template="momentum"
    )
    print("Strategy code generated successfully")
    
    # Validate code
    print("\n[3] Validating strategy code...")
    is_valid = coder.validate_code(strategy_code)
    if not is_valid:
        print("ERROR: Strategy code validation failed!")
        return
    print("Validation: PASSED")
    
    # Setup backtest
    print("\n[4] Setting up backtest...")
    orchestrator = BacktestingOrchestrator()
    
    # Prepare data for major tech stocks
    symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "TSLA"]
    print(f"Symbols: {', '.join(symbols)}")
    
    data = orchestrator.prepare_data(
        symbols=symbols,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2023, 12, 31)
    )
    
    # Run backtest
    print("\n[5] Running backtest...")
    config = BacktestConfig(
        strategy_id=strategy_code.hypothesis_id,
        start_date=datetime(2020, 1, 1),
        end_date=datetime(2023, 12, 31),
        initial_capital=100000.0,
        commission=0.001
    )
    
    results = orchestrator.run_backtest(
        strategy_code=strategy_code.code,
        config=config
    )
    
    # Display results
    print("\n" + "=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)
    print(f"Strategy ID: {results.strategy_id}")
    print(f"Period: {config.start_date.date()} to {config.end_date.date()}")
    print(f"\nPerformance Metrics:")
    print(f"  Total Return:     {results.total_return:>10.2%}")
    print(f"  Sharpe Ratio:     {results.sharpe_ratio:>10.2f}")
    print(f"  Max Drawdown:     {results.max_drawdown:>10.2%}")
    print(f"  Win Rate:         {results.win_rate:>10.2%}")
    print(f"  Number of Trades: {results.num_trades:>10}")
    print(f"  Execution Time:   {results.execution_time:>10.2f}s")
    
    # Analyze results
    print("\n[6] Analyzing results...")
    analysis = orchestrator.analyze_results(results)
    print(f"Performance: {analysis.get('performance', 'N/A')}")
    print(f"Risk Adjusted: {analysis.get('risk_adjusted', 'N/A')}")
    
    # Generate report
    print("\n[7] Generating report...")
    report = orchestrator.generate_report(results, output_path="/tmp/momentum_strategy_report.md")
    print("Report saved to: /tmp/momentum_strategy_report.md")
    
    # Export strategy code
    print("\n[8] Exporting strategy code...")
    export_path = "/tmp/momentum_strategy.py"
    coder.export_to_file(strategy_code, export_path)
    print(f"Strategy code exported to: {export_path}")
    
    print("\n" + "=" * 80)
    print("Example Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
