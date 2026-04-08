import zipline.api as algo
from zipline.pipeline import Pipeline, EquityPricing, master
from zipline.pipeline.factors import RSI
from zipline.pipeline.filters import StaticUniverse

MAX_POSITIONS = 2
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
RSI_WINDOW = 14

def initialize(context):
    are_in_universe = StaticUniverse(\"large-cap-defensive-us\")
    rsi = RSI(window_length=RSI_WINDOW)
    pipe = Pipeline(
        columns={\"rsi\": rsi},
        initial_universe=are_in_universe,
    )
    algo.attach_pipeline(pipe, \"rsi_pipe\")
    algo.schedule_function(
        rebalance,
        algo.date_rules.every_day(),
        algo.time_rules.market_open(minutes=30),
    )

def before_trading_start(context, data):
    context.pipe_results = algo.pipeline_output(\"rsi_pipe\")

def rebalance(context, data):
    pipe = context.pipe_results
    current_positions = set(context.portfolio.positions.keys())

    # Exit: sell any held stock where RSI is now above overbought threshold
    for asset in list(current_positions):
        if asset in pipe.index:
            rsi_val = pipe.loc[asset, \"rsi\"]
            if rsi_val > RSI_OVERBOUGHT:
                algo.order_target_percent(asset, 0)
                current_positions.discard(asset)

    # Refresh current positions count after sells
    held = set(
        asset for asset in context.portfolio.positions
        if context.portfolio.positions[asset].amount > 0
    )

    # Entry: buy oversold stocks if we have capacity
    open_slots = MAX_POSITIONS - len(held)
    if open_slots <= 0:
        return

    buy_candidates = pipe[pipe[\"rsi\"] < RSI_OVERSOLD].index.tolist()
    # Exclude stocks we already hold
    buy_candidates = [a for a in buy_candidates if a not in held]

    # Pick up to open_slots candidates
    to_buy = buy_candidates[:open_slots]

    # Equal weight: each position gets 1/MAX_POSITIONS of portfolio
    target_pct = 1.0 / MAX_POSITIONS
    for asset in to_buy:
        if data.can_trade(asset):
            algo.order_target_percent(asset, target_pct)