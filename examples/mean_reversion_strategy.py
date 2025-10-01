"""Mean Reversion Strategy Example.

This example demonstrates creating and testing a mean reversion trading strategy.
"""

from datetime import datetime
from hypothesis_generation.generator import Hypothesis
from strategy_coder import StrategyCoder
from backtesting_orchestrator import BacktestingOrchestrator, BacktestConfig
from refinement_agent import RefinementAgent


def create_mean_reversion_hypothesis() -> Hypothesis:
    """Create a mean reversion strategy hypothesis.
    
    Returns:
        Hypothesis object for mean reversion strategy
    """
    return Hypothesis(
        id="mr_001",
        title="Bollinger Bands Mean Reversion",
        description="""
        Trade reversals when price touches Bollinger Bands.
        
        Entry Rules:
        - Buy when price touches lower Bollinger Band (2 std dev)
        - RSI < 30 (oversold confirmation)
        - Volume > 1.5x average volume
        
        Exit Rules:
        - Sell when price reaches middle Bollinger Band
        - Or when RSI > 70
        - Stop loss at 5% below entry
        
        Position Sizing:
        - Risk 2% of capital per trade
        - Maximum 5 concurrent positions
        """,
        market="equities",
        timeframe="daily",
        score=0.82,
        generated_at=datetime.now(),
        tags=["mean_reversion", "bollinger_bands", "RSI", "oversold"]
    )


def main() -> None:
    """Run mean reversion strategy example."""
    print("=" * 80)
    print("Mean Reversion Strategy Example")
    print("=" * 80)
    
    # Create hypothesis
    print("\n[1] Creating mean reversion hypothesis...")
    hypothesis = create_mean_reversion_hypothesis()
    print(f"Hypothesis: {hypothesis.title}")
    print(f"Description: {hypothesis.description[:100]}...")
    
    # Generate strategy code
    print("\n[2] Generating strategy code...")
    coder = StrategyCoder(model="gpt-4")
    strategy_code = coder.generate_strategy_code(
        hypothesis=hypothesis.__dict__,
        template="mean_reversion"
    )
    
    # Validate code
    print("\n[3] Validating code...")
    if not coder.validate_code(strategy_code):
        print("ERROR: Code validation failed!")
        return
    print("Validation: PASSED")
    
    # Setup and run backtest
    print("\n[4] Running initial backtest...")
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
    
    print("\nInitial Results:")
    print(f"  Total Return:  {results.total_return:.2%}")
    print(f"  Sharpe Ratio:  {results.sharpe_ratio:.2f}")
    print(f"  Max Drawdown:  {results.max_drawdown:.2%}")
    
    # Refine strategy
    print("\n[5] Starting strategy refinement...")
    agent = RefinementAgent(model="gpt-4", max_iterations=5)
    
    # Analyze performance
    print("\n  [5.1] Analyzing performance...")
    analysis = agent.analyze_performance(results.__dict__)
    print(f"  Issues identified: {len(analysis.get('issues', []))}")
    
    # Generate refinement suggestions
    print("\n  [5.2] Generating refinement suggestions...")
    suggestions = agent.generate_refinement_suggestions(
        analysis=analysis,
        strategy_code=strategy_code.code
    )
    print(f"  Suggestions generated: {len(suggestions)}")
    
    # Apply iterative refinement
    print("\n  [5.3] Applying iterative refinement...")
    refined_result = agent.iterative_refinement(
        initial_strategy_code=strategy_code.code,
        initial_results=results.__dict__,
        target_metric="sharpe_ratio",
        target_value=2.5
    )
    
    # Display refinement explanation
    print("\n[6] Refinement Summary:")
    explanation = agent.explain_refinements(refined_result)
    print(explanation)
    
    # Compare original vs refined
    print("\n" + "=" * 80)
    print("PERFORMANCE COMPARISON")
    print("=" * 80)
    print(f"{'Metric':<20} {'Original':>15} {'Refined':>15} {'Change':>15}")
    print("-" * 80)
    
    original_sharpe = results.sharpe_ratio
    refined_sharpe = refined_result.refined_performance.get('sharpe_ratio', 0.0)
    sharpe_change = ((refined_sharpe - original_sharpe) / original_sharpe) if original_sharpe != 0 else 0
    
    print(f"{'Sharpe Ratio':<20} {original_sharpe:>15.2f} {refined_sharpe:>15.2f} {sharpe_change:>14.2%}")
    print(f"{'Iterations':<20} {'-':>15} {refined_result.iteration:>15} {'-':>15}")
    print(f"{'Refinements':<20} {'-':>15} {len(refined_result.applied_suggestions):>15} {'-':>15}")
    
    # Generate final report
    print("\n[7] Generating final report...")
    report = orchestrator.generate_report(results, output_path="/tmp/mean_reversion_report.md")
    print("Report saved to: /tmp/mean_reversion_report.md")
    
    print("\n" + "=" * 80)
    print("Example Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
