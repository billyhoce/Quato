import zipline.api as algo
import numpy as np
from zipline.pipeline import Pipeline, EquityPricing, master
from zipline.pipeline.factors import (
    AverageDollarVolume,
    SimpleMovingAverage,
    CustomFactor,
)

# Number of most-liquid stocks to consider
LIQUIDITY_POOL = 100
# Number of top-volatility stocks to hold at any time
MAX_POSITIONS = 2
# Equal weight per position
POSITION_WEIGHT = 1.0 / MAX_POSITIONS
# Moving average windows
FAST_MA_WINDOW = 50
SLOW_MA_WINDOW = 200
# Volatility window (trading days)
VOL_WINDOW = 20


class DailyReturnStdDev(CustomFactor):
    """
    Compute the standard deviation of daily close-to-close returns
    over the given window. window_length should be VOL_WINDOW + 1 so
    that we get exactly VOL_WINDOW return observations.
    """
    inputs = [EquityPricing.close]

    def compute(self, today, assets, out, close):
        # close shape: (window_length, num_assets)
        # compute daily returns along time axis
        returns = np.diff(close, axis=0) / close[:-1]
        out[:] = np.nanstd(returns, axis=0)


def make_pipeline():
    """
    Build the pipeline that selects the top-2 most volatile stocks
    from the top-100 most liquid common US stocks where the 50-day
    moving average is above the 200-day moving average.

    Volatility is measured as the standard deviation of daily returns
    over the past 20 trading days via a custom factor, keeping the
    total price lookback to just 21 days.
    """
    # Limit to common US stocks only
    are_common_stocks = master.SecuritiesMaster.usstock_SecurityType2.latest.eq(
        "Common Stock"
    )

    # Dollar volume filter: keep the top LIQUIDITY_POOL stocks by 30-day ADV
    adv = AverageDollarVolume(window_length=30)
    top_liquid = adv.top(LIQUIDITY_POOL, mask=are_common_stocks)

    # Moving averages for trend filter
    fast_ma = SimpleMovingAverage(
        inputs=[EquityPricing.close],
        window_length=FAST_MA_WINDOW,
        mask=top_liquid,
    )
    slow_ma = SimpleMovingAverage(
        inputs=[EquityPricing.close],
        window_length=SLOW_MA_WINDOW,
        mask=top_liquid,
    )

    # Trend confirmation: fast MA above slow MA
    uptrend = fast_ma > slow_ma

    # Combined mask for volatility computation
    vol_mask = top_liquid & uptrend

    # 20-day return std dev: needs VOL_WINDOW + 1 prices to get VOL_WINDOW returns
    vol = DailyReturnStdDev(
        window_length=VOL_WINDOW + 1,
        mask=vol_mask,
    )

    # Select the 2 highest-volatility stocks among the filtered candidates
    top_vol = vol.top(MAX_POSITIONS, mask=vol_mask)

    pipe = Pipeline(
        columns={
            "vol": vol,
        },
        initial_universe=are_common_stocks,
        screen=top_vol,
    )
    return pipe


def initialize(context: algo.Context):
    """
    Attach the selection pipeline and schedule a weekly rebalance
    that runs on the first trading day of each week, shortly after
    the market opens.
    """
    algo.attach_pipeline(make_pipeline(), "selection")

    algo.schedule_function(
        rebalance,
        algo.date_rules.week_start(days_offset=0),
        algo.time_rules.market_open(minutes=30),
    )


def before_trading_start(context: algo.Context, data: algo.BarData):
    """
    Retrieve the pipeline results for today and store the selected
    assets for use during the rebalance.
    """
    context.pipeline_results = algo.pipeline_output("selection")


def rebalance(context: algo.Context, data: algo.BarData):
    """
    Exit any positions not in the current selection, then equally
    weight the selected stocks at 50% of the portfolio each.
    """
    selected = context.pipeline_results.index

    # Exit positions that are no longer selected
    for asset in context.portfolio.positions:
        if asset not in selected:
            algo.order_target_percent(asset, 0.0)

    # Enter or rebalance into each selected stock
    for asset in selected:
        if data.can_trade(asset):
            algo.order_target_percent(asset, POSITION_WEIGHT)