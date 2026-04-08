import zipline.api as algo
from zipline.pipeline import Pipeline, EquityPricing, master
from zipline.pipeline.factors import AverageDollarVolume, Returns

# --- Module-level constants ---
LIQUIDITY_WINDOW = 30       # Days for average dollar volume calculation
RETURN_WINDOW = 6           # window_length=6 gives a 5-period price change
TOP_N_LIQUID = 200          # Number of most liquid stocks to consider
MIN_PRICE = 1.0             # Minimum stock price filter


def initialize(context: algo.Context):
    """
    Build a pipeline that:
      - Restricts to the top 200 most liquid US common stocks (by avg dollar volume).
      - Computes 5-day returns for each stock.
    Schedule daily rebalancing at market open.
    """
    # Filter: common stocks only
    are_common_stocks = master.SecuritiesMaster.usstock_SecurityType2.latest.eq("Common Stock")

    # Liquidity factor and screen: top N by average dollar volume
    adv = AverageDollarVolume(window_length=LIQUIDITY_WINDOW)
    top_liquid = adv.top(TOP_N_LIQUID, mask=are_common_stocks)

    # Price filter
    above_min_price = EquityPricing.close.latest >= MIN_PRICE

    # 5-day returns (window_length=6 captures 5 periods of change)
    five_day_return = Returns(window_length=RETURN_WINDOW)

    pipe = Pipeline(
        columns={
            "five_day_return": five_day_return,
        },
        initial_universe=are_common_stocks,
        screen=top_liquid & above_min_price,
    )

    algo.attach_pipeline(pipe, "momentum")

    algo.schedule_function(
        rebalance,
        algo.date_rules.every_day(),
        algo.time_rules.market_open(),
    )

    # context.target_asset will be set in before_trading_start
    context.target_asset = None


def before_trading_start(context: algo.Context, data: algo.BarData):
    """
    Fetch today's pipeline output and identify the single stock
    with the highest 5-day return. Store the asset object on context.
    """
    results = algo.pipeline_output("momentum")

    if results.empty:
        context.target_asset = None
        return

    # Find the asset (index entry) with the highest 5-day return
    context.target_asset = results["five_day_return"].idxmax()


def rebalance(context: algo.Context, data: algo.BarData):
    """
    Sell all positions that are no longer the top-momentum stock,
    then invest 100% of the portfolio in the top-momentum stock.
    """
    target_asset = context.target_asset

    # Exit all positions not matching the current top stock
    for asset in list(context.portfolio.positions.keys()):
        if target_asset is None or asset != target_asset:
            algo.order_target_percent(asset, 0.0)

    # Enter or maintain 100% position in the top-momentum stock
    if target_asset is not None and data.can_trade(target_asset):
        algo.order_target_percent(target_asset, 1.0)