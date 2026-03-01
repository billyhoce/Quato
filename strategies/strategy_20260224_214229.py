import zipline.api as algo
from zipline.pipeline import Pipeline
from zipline.pipeline.data import EquityPricing
from zipline.pipeline.factors import SimpleMovingAverage
from zipline.pipeline.filters import StaticUniverse

# Define the data bundle to use for the backtest.
# This assumes a QuantRocket 'usstock-1min' bundle is available.
BUNDLE = "usstock-1min"

# Define SMA lengths and target position value as module-level constants.
# These values can be tuned based on backtesting results.
SHORT_SMA_LENGTH = 50
LONG_SMA_LENGTH = 200
TARGET_POSITION_VALUE = 10000  # Target dollar value for each position

# Define a universe of assets to trade.
# For demonstration, we use a placeholder static universe.
# You should replace "your-custom-universe" with a universe name
# defined in your QuantRocket securities master database,
# or define a StaticAssets filter with specific SIDs/symbols.
# Example: STATIC_UNIVERSE_NAME = "tech-giants"
STATIC_UNIVERSE_NAME = "your-custom-universe"


def initialize(context: algo.Context):
    """
    Called once at the start of the backtest.
    Sets up the pipeline, schedules the rebalance function, and initializes
    strategy parameters.
    """
    context.target_value = TARGET_POSITION_VALUE

    # Create a Pipeline to calculate short and long Simple Moving Averages.
    # The initial_universe should be set to a filter that defines the assets
    # you want to consider for trading.
    pipe = Pipeline(
        columns={
            "short_mavg": SimpleMovingAverage(
                inputs=[EquityPricing.close], window_length=SHORT_SMA_LENGTH
            ),
            "long_mavg": SimpleMovingAverage(
                inputs=[EquityPricing.close], window_length=LONG_SMA_LENGTH
            ),
        },
        initial_universe=StaticUniverse(STATIC_UNIVERSE_NAME),
    )

    # Attach the pipeline to the algorithm with a name for later retrieval.
    algo.attach_pipeline(pipe, "sma_crossover_pipeline")

    # Schedule the rebalance function to run daily, 30 minutes after market open.
    algo.schedule_function(
        rebalance,
        algo.date_rules.every_day(),
        algo.time_rules.market_open(minutes=30),
    )

    # Optional: Set commission and slippage models
    # algo.set_commission(algo.commission.PerShare(cost=0.005, min_trade_cost=1.0))
    # algo.set_slippage(algo.slippage.VolumeShareSlippage(volume_limit=0.025, price_impact=0.1))


def before_trading_start(context: algo.Context, data: algo.BarData):
    """
    Called once per day before market open.
    Retrieves the output of the pipeline for the current day.
    """
    # Store the pipeline output in context for access by scheduled functions.
    context.sma_data = algo.pipeline_output("sma_crossover_pipeline")


def rebalance(context: algo.Context, data: algo.BarData):
    """
    Called daily to rebalance the portfolio based on SMA crossover signals.
    """
    if context.sma_data is None:
        return

    # Iterate over assets that had valid SMA data from the pipeline
    for asset in context.sma_data.index:
        short_mavg = context.sma_data.loc[asset, "short_mavg"]
        long_mavg = context.sma_data.loc[asset, "long_mavg"]

        # Ensure we have valid SMA values and the asset is tradable
        if pd.isna(short_mavg) or pd.isna(long_mavg) or not data.can_trade(asset):
            continue

        # Crossover logic
        # If short SMA crosses above long SMA, buy (go long)
        if short_mavg > long_mavg:
            # Check if we already have a position or are trying to increase
            if context.portfolio.positions.get(asset) is None or context.portfolio.positions[asset].amount == 0:
                algo.order_target_value(asset, context.target_value)
            elif context.portfolio.positions[asset].amount < 0:
                # If currently short, cover and go long
                algo.order_target_value(asset, context.target_value)

        # If short SMA crosses below long SMA, sell (close position)
        elif short_mavg < long_mavg:
            # Check if we have a long position
            if context.portfolio.positions.get(asset) is not None and context.portfolio.positions[asset].amount > 0:
                algo.order_target_value(asset, 0)
            elif context.portfolio.positions.get(asset) is None or context.portfolio.positions[asset].amount == 0:
                # Optionally, you could go short here if your strategy allows
                # algo.order_target_value(asset, -context.target_value)
                pass # Do nothing if no position or already flat/short

    # Record some values for analysis (optional)
    algo.record(
        num_positions=len(context.portfolio.positions),
        cash=context.portfolio.cash,
        total_value=context.portfolio.portfolio_value,
    )

# Note: You will need to ensure `pandas` is available if using `pd.isna`.
# Zipline environments usually include it, but it's good practice to ensure.
import pandas as pd