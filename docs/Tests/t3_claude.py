import zipline.api as algo
from zipline.pipeline import Pipeline, EquityPricing, master
from zipline.pipeline.factors import AverageDollarVolume, Returns

# Top N most liquid stocks to consider
TOP_N_LIQUID = 100
RETURN_WINDOW = 6  # 5-day return needs window_length=6 (current day + 5 prior closes)

def initialize(context):
    \"\"\"
    Build a pipeline that:
    1. Screens to the top 100 stocks by average dollar volume (liquidity).
    2. Computes the 5-day return for each stock.
    Schedule daily rebalancing at market open.
    \"\"\"
    are_common_stocks = master.SecuritiesMaster.usstock_SecurityType2.latest.eq(\"Common Stock\")

    avg_dv = AverageDollarVolume(window_length=30, mask=are_common_stocks)
    top_liquid = avg_dv.top(TOP_N_LIQUID)

    five_day_return = Returns(window_length=RETURN_WINDOW, mask=top_liquid)

    pipe = Pipeline(
        columns={
            \"five_day_return\": five_day_return,
        },
        initial_universe=are_common_stocks,
        screen=top_liquid,
    )
    algo.attach_pipeline(pipe, \"momentum\")

    algo.schedule_function(
        rebalance,
        algo.date_rules.every_day(),
        algo.time_rules.market_open()
    )


def before_trading_start(context, data):
    context.pipeline_data = algo.pipeline_output(\"momentum\")


def rebalance(context, data):
    pipeline_data = context.pipeline_data

    if pipeline_data.empty:
        return

    # Find the stock with the highest 5-day return
    best_asset = pipeline_data[\"five_day_return\"].idxmax()

    # Exit all positions not equal to the best asset
    for asset in list(context.portfolio.positions.keys()):
        if asset != best_asset:
            algo.order_target_percent(asset, 0)

    # Go 100% into the best asset
    if data.can_trade(best_asset):
        algo.order_target_percent(best_asset, 1.0)