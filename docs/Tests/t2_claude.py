import zipline.api as algo
from zipline.pipeline import Pipeline, master
from zipline.pipeline.filters import StaticUniverse

# 14 large-cap US tech stocks: AAPL, MSFT, IBM, INTC, CSCO, ORCL, QCOM, TXN,
# HPQ, DELL, EMC, AMZN, EBAY, GOOGL
UNIVERSE_CODE = \"large-cap-tech-2008\"
NUM_STOCKS = 14

def initialize(context):
    context.ordered = False

    are_in_universe = StaticUniverse(UNIVERSE_CODE)

    pipe = Pipeline(
        columns={},
        initial_universe=are_in_universe,
    )
    algo.attach_pipeline(pipe, \"tech_universe\")

    algo.schedule_function(
        buy_equal_weight,
        algo.date_rules.every_day(),
        algo.time_rules.market_open(minutes=30),
    )


def before_trading_start(context, data):
    context.tech_assets = algo.pipeline_output(\"tech_universe\").index.tolist()


def buy_equal_weight(context, data):
    if context.ordered:
        return

    assets = context.tech_assets
    if not assets:
        return

    target_weight = 1.0 / len(assets)

    for asset in assets:
        if data.can_trade(asset):
            algo.order_target_percent(asset, target_weight)

    context.ordered = True