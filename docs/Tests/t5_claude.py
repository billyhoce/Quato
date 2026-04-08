import zipline.api as algo
from zipline.pipeline import Pipeline, EquityPricing
from zipline.pipeline.factors import SimpleMovingAverage
from zipline.pipeline.filters import StaticUniverse

# Equal dollar allocation per stock position
POSITION_VALUE = 5000  # $5,000 per stock out of $100,000 capital

def initialize(context):
    \"\"\"Attach pipeline and schedule daily rebalancing.\"\"\"
    in_universe = StaticUniverse(\"us-tech-2008-2011\")

    sma20 = SimpleMovingAverage(inputs=[EquityPricing.close], window_length=20)
    sma50 = SimpleMovingAverage(inputs=[EquityPricing.close], window_length=50)

    pipe = Pipeline(
        columns={
            \"sma20\": sma20,
            \"sma50\": sma50,
        },
        initial_universe=in_universe,
    )
    algo.attach_pipeline(pipe, \"ma_crossover\")
    algo.schedule_function(
        rebalance,
        algo.date_rules.every_day(),
        algo.time_rules.market_open(minutes=30),
    )


def before_trading_start(context, data):
    \"\"\"Load today's pipeline output.\"\"\"
    context.signals = algo.pipeline_output(\"ma_crossover\")


def rebalance(context, data):
    \"\"\"Buy on golden cross, sell on death cross. One position per stock at a time.\"\"\"
    signals = context.signals

    for asset in signals.index:
        sma20 = signals.at[asset, \"sma20\"]
        sma50 = signals.at[asset, \"sma50\"]

        if not data.can_trade(asset):
            continue

        current_position = context.portfolio.positions[asset].amount

        if sma20 > sma50 and current_position == 0:
            # Golden cross: open position
            algo.order_target_value(asset, POSITION_VALUE)
        elif sma20 < sma50 and current_position > 0:
            # Death cross: close position
            algo.order_target_value(asset, 0)