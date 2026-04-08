import zipline.api as algo
from zipline.pipeline import Pipeline, EquityPricing
from zipline.pipeline.factors import SimpleMovingAverage
from zipline.pipeline.filters import StaticUniverse

# --- Strategy Parameters ---
SHORT_WINDOW = 20   # Short moving average window (days)
LONG_WINDOW = 50    # Long moving average window (days)
UNIVERSE_CODE = "us-tech"


def initialize(context: algo.Context):
    """
    Attach a pipeline that computes 20-day and 50-day simple moving
    averages for every stock in the us-tech universe, and schedule
    the rebalance function to run every trading day at market open.
    """
    # Restrict the pipeline to our named tech universe
    tech_universe = StaticUniverse(UNIVERSE_CODE)

    pipe = Pipeline(
        columns={
            "sma_short": SimpleMovingAverage(
                inputs=[EquityPricing.close],
                window_length=SHORT_WINDOW,
            ),
            "sma_long": SimpleMovingAverage(
                inputs=[EquityPricing.close],
                window_length=LONG_WINDOW,
            ),
        },
        initial_universe=tech_universe,
        screen=tech_universe,
    )

    algo.attach_pipeline(pipe, "tech_mavgs")

    # Run the rebalance logic every day shortly after market open
    algo.schedule_function(
        rebalance,
        algo.date_rules.every_day(),
        algo.time_rules.market_open(minutes=30),
    )


def before_trading_start(context: algo.Context, data: algo.BarData):
    """
    Fetch today's pipeline output so the moving averages are ready
    before the rebalance function fires.
    """
    context.tech_signals = algo.pipeline_output("tech_mavgs")


def rebalance(context: algo.Context, data: algo.BarData):
    """
    For each stock in the tech universe:
      - Buy (allocate an equal share of the portfolio) when the 20-day
        moving average crosses above the 50-day moving average.
      - Sell (close the position entirely) when the 20-day moving
        average crosses below the 50-day moving average.
    Each stock is treated independently; only one position per stock
    is held at any given time.
    """
    signals = context.tech_signals

    # Determine how many stocks could be active at once for equal sizing
    num_stocks = len(signals)
    if num_stocks == 0:
        return

    target_weight = 1.0 / num_stocks  # Equal weight allocation

    for asset in signals.index:
        sma_short = signals.at[asset, "sma_short"]
        sma_long = signals.at[asset, "sma_long"]

        if not data.can_trade(asset):
            continue

        if sma_short > sma_long:
            # Golden cross: move into (or stay in) a long position
            algo.order_target_percent(asset, target_weight)
        elif sma_short < sma_long:
            # Death cross: exit the position entirely
            algo.order_target_percent(asset, 0.0)