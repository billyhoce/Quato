import zipline.api as algo
from zipline.pipeline import Pipeline, EquityPricing, master
from zipline.pipeline.factors import (
    SimpleMovingAverage,
    AverageDollarVolume,
    AnnualizedVolatility,
    Returns,
)

# Parameters
TOP_LIQUID = 100       # top N stocks by dollar volume
MA_FAST = 50
MA_SLOW = 200
VOL_WINDOW = 20        # 20-day volatility window
NUM_HOLDINGS = 2       # pick top-2 highest volatility stocks


def make_pipeline():
    are_common_stocks = master.SecuritiesMaster.usstock_SecurityType2.latest.eq(\"Common Stock\")

    # Liquidity: average dollar volume
    adv = AverageDollarVolume(window_length=30)
    top_liquid = adv.top(TOP_LIQUID)

    # Moving averages for golden-cross filter
    sma_fast = SimpleMovingAverage(inputs=[EquityPricing.close], window_length=MA_FAST)
    sma_slow = SimpleMovingAverage(inputs=[EquityPricing.close], window_length=MA_SLOW)
    golden_cross = sma_fast > sma_slow

    # 20-day volatility (use AnnualizedVolatility with 20-day window of returns)
    vol_20 = AnnualizedVolatility(
        inputs=[Returns(window_length=2)],
        window_length=MA_FAST,  # placeholder; override below
        mask=top_liquid & golden_cross & are_common_stocks,
    )
    # AnnualizedVolatility uses Returns(window_length=2) by default; window_length
    # on the factor sets how many daily-return observations to include.
    vol_20 = AnnualizedVolatility(
        window_length=VOL_WINDOW + 1,
        mask=top_liquid & golden_cross & are_common_stocks,
    )

    screen = top_liquid & golden_cross & are_common_stocks

    return Pipeline(
        columns={
            \"adv\": adv,
            \"sma_fast\": sma_fast,
            \"sma_slow\": sma_slow,
            \"vol_20\": vol_20,
        },
        initial_universe=are_common_stocks,
        screen=screen,
    )


def initialize(context):
    algo.attach_pipeline(make_pipeline(), \"signals\")
    # Rebalance every Monday at market open
    algo.schedule_function(
        rebalance,
        algo.date_rules.week_start(days_offset=0),
        algo.time_rules.market_open(minutes=30),
    )


def before_trading_start(context, data):
    context.pipeline_data = algo.pipeline_output(\"signals\")


def rebalance(context, data):
    pipe = context.pipeline_data

    if pipe.empty:
        # Liquidate all if no candidates
        for asset in context.portfolio.positions:
            algo.order_target_percent(asset, 0)
        return

    # Pick top-2 by 20-day volatility
    top2 = pipe.nlargest(NUM_HOLDINGS, \"vol_20\").index.tolist()

    # Liquidate positions not in target set
    for asset in list(context.portfolio.positions.keys()):
        if asset not in top2:
            algo.order_target_percent(asset, 0)

    # Equal-weight the top-2
    weight = 1.0 / NUM_HOLDINGS
    for asset in top2:
        if data.can_trade(asset):
            algo.order_target_percent(asset, weight)