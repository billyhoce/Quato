"""Basic Workflow Example for Quato.

This example demonstrates the complete end-to-end workflow of using Quato
to generate, code, backtest, and refine a trading strategy.
"""

from datetime import datetime
from hypothesis_generation import HypothesisGenerator
from strategy_coder import StrategyCoder
from backtesting_orchestrator import BacktestingOrchestrator, BacktestConfig
from refinement_agent import RefinementAgent


def main() -> None:
    """Run a basic Quato workflow."""
    print("=" * 80)
    print("Quato Basic Workflow Example")
    print("=" * 80)
    
    # Step 1: Generate trading hypotheses
    print("\n[Step 1] Generating trading hypotheses...")
    generator = HypothesisGenerator(model="gpt-4")
    
    # Example market data (in real use, this would be actual market data)
    market_data = {
        "symbols": ["AAPL", "GOOGL", "MSFT"],
        "timeframe": "daily",
        "indicators": ["RSI", "MACD", "Moving Averages"]
    }
    
    hypotheses = generator.generate_from_market_data(
        market_data=market_data,
        num_hypotheses=3
    )
    print(f"Generated {len(hypotheses)} hypotheses")
    
    # For this example, we'll create a mock hypothesis
    from hypothesis_generation.generator import Hypothesis
    example_hypothesis = Hypothesis(
        id="hyp_001",
        title="RSI Mean Reversion Strategy",
        description="Buy when RSI < 30, sell when RSI > 70",
        market="equities",
        timeframe="daily",
        score=0.85,
        generated_at=datetime.now(),
        tags=["mean_reversion", "RSI", "oversold_oversought"]
    )
    
    # Step 2: Generate strategy code
    print("\n[Step 2] Generating strategy code...")
    coder = StrategyCoder(model="gpt-4")
    strategy_code = coder.generate_strategy_code(
        hypothesis=example_hypothesis.__dict__,
        template="mean_reversion"
    )
    
    is_valid = coder.validate_code(strategy_code)
    print(f"Code validation: {'PASSED' if is_valid else 'FAILED'}")
    
    # Step 3: Run backtest
    print("\n[Step 3] Running backtest...")
    orchestrator = BacktestingOrchestrator()
    
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
    
    print(f"\nBacktest Results:")
    print(f"  Total Return: {results.total_return:.2%}")
    print(f"  Sharpe Ratio: {results.sharpe_ratio:.2f}")
    print(f"  Max Drawdown: {results.max_drawdown:.2%}")
    print(f"  Win Rate: {results.win_rate:.2%}")
    print(f"  Number of Trades: {results.num_trades}")
    
    # Step 4: Analyze results
    print("\n[Step 4] Analyzing results...")
    analysis = orchestrator.analyze_results(results)
    print(f"Performance assessment: {analysis.get('performance', 'N/A')}")
    
    # Step 5: Refine strategy
    print("\n[Step 5] Refining strategy...")
    agent = RefinementAgent(model="gpt-4", max_iterations=3)
    
    performance_analysis = agent.analyze_performance(results.__dict__)
    suggestions = agent.generate_refinement_suggestions(
        analysis=performance_analysis,
        strategy_code=strategy_code.code
    )
    
    print(f"Generated {len(suggestions)} refinement suggestions")
    
    # Apply iterative refinement
    refined_result = agent.iterative_refinement(
        initial_strategy_code=strategy_code.code,
        initial_results=results.__dict__,
        target_metric="sharpe_ratio",
        target_value=2.0
    )
    
    # Step 6: Generate final report
    print("\n[Step 6] Generating report...")
    report = orchestrator.generate_report(results)
    
    # Save report to file
    report_path = "/tmp/quato_backtest_report.md"
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"Report saved to: {report_path}")
    
    # Summary
    print("\n" + "=" * 80)
    print("Workflow Complete!")
    print("=" * 80)
    print(f"\nOriginal Performance: Sharpe Ratio = {results.sharpe_ratio:.2f}")
    print(f"Refined Performance: Sharpe Ratio = {refined_result.refined_performance.get('sharpe_ratio', 0.0):.2f}")
    print(f"Improvement: {refined_result.improvement:.2%}")


if __name__ == "__main__":
    main()
