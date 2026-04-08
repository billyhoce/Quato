import zipline.api as algo
from zipline.pipeline import Pipeline, master
from zipline.pipeline.filters import StaticUniverse

# The universe of well-known large-cap US tech stocks created for this strategy.
UNIVERSE_NAME = "large-cap-tech-2008"


def initialize(context: algo.Context):
    """
    Attach a pipeline scoped to the large-cap tech universe and schedule
    a one-time buy on the first trading day. A flag ensures no further
    trades are placed after the initial allocation.
    """
    context.invested = False

    # Build a pipeline that simply identifies all stocks in our tech universe.
    tech_universe = StaticUniverse(UNIVERSE_NAME)

    pipe = Pipeline(
        columns={},
        initial_universe=tech_universe,
        screen=tech_universe,
    )
    algo.attach_pipeline(pipe, "tech_universe")

    # Schedule the allocation function to run every day so we can catch
    # the first available trading day, then do nothing afterwards.
    algo.schedule_function(
        allocate,
        algo.date_rules.every_day(),
        algo.time_rules.market_open(minutes=1),
    )


def before_trading_start(context: algo.Context, data: algo.BarData):
    """
    Retrieve today's pipeline output to get the current list of
    tradeable stocks in the large-cap tech universe.
    """
    context.tech_stocks = algo.pipeline_output("tech_universe")


def allocate(context: algo.Context, data: algo.BarData):
    """
    On the very first trading day, buy an equal-weight position in every
    stock in the universe. After the initial allocation, this function
    exits immediately without placing any further orders (buy and hold).
    """
    # Only invest once at the very start of the backtest.
    if context.invested:
        return

    stocks = context.tech_stocks.index
    num_stocks = len(stocks)

    if num_stocks == 0:
        return

    # Equal weight: each stock gets 1/N of total portfolio value.
    target_pct = 1.0 / num_stocks

    for stock in stocks:
        if data.can_trade(stock):
            algo.order_target_percent(stock, target_pct)

    context.invested = True