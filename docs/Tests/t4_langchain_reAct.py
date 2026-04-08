import zipline.api as algo
from zipline.pipeline import Pipeline, EquityPricing, master
from zipline.pipeline.factors import DailyReturns, AverageDollarVolume
from zipline.pipeline.filters import StaticUniverse
from zipline.finance.execution import MarketOnCloseOrder

# --- Strategy Parameters ---
DROP_THRESHOLD = -0.03   # Buy when daily return drops more than 3%
HOLD_DAYS = 3            # Hold each position for exactly 3 trading days
MAX_POSITIONS = 10       # Maximum concurrent positions allowed
POSITION_SIZE = 1.0 / MAX_POSITIONS  # Equal weighting per position


def initialize(context):
    """
    Set up the pipeline to detect daily dips in the blue-chip universe,
    and schedule the daily rebalance function to run at market close.
    """
    # Track open positions: maps asset -> number of days held
    context.days_held = {}

    # Filter to the blue-chip universe
    in_blue_chip = StaticUniverse("blue-chip-us")

    # Liquidity filter: require meaningful average dollar volume
    avg_dv = AverageDollarVolume(window_length=30)
    liquid_enough = avg_dv > 1_000_000

    # Daily return factor to detect dips
    daily_ret = DailyReturns()
    big_drop = daily_ret < DROP_THRESHOLD

    pipe = Pipeline(
        columns={
            "daily_return": daily_ret,
            "big_drop": big_drop,
        },
        initial_universe=in_blue_chip,
        screen=liquid_enough,
    )

    algo.attach_pipeline(pipe, "dip_signals")

    # Run rebalance at market close every day
    algo.schedule_function(
        rebalance,
        algo.date_rules.every_day(),
        algo.time_rules.market_close(),
    )


def before_trading_start(context, data):
    """
    Fetch today's pipeline output containing dip signals.
    """
    context.pipeline_data = algo.pipeline_output("dip_signals")


def rebalance(context, data):
    """
    1. Age all existing positions by one day and exit any that have been
       held for exactly HOLD_DAYS trading days.
    2. For any stock that dropped more than 3% today and is not already
       held, open a new position at the close if capacity allows.
    """
    # --- Step 1: Age existing positions and exit when hold period expires ---
    assets_to_exit = []
    for asset, days in list(context.days_held.items()):
        updated_days = days + 1
        if updated_days >= HOLD_DAYS:
            assets_to_exit.append(asset)
        else:
            context.days_held[asset] = updated_days

    for asset in assets_to_exit:
        if data.can_trade(asset):
            algo.order_target_value(asset, 0, style=MarketOnCloseOrder())
        del context.days_held[asset]

    # --- Step 2: Enter new positions on today's dip signals ---
    pipe_data = context.pipeline_data
    dip_candidates = pipe_data[pipe_data["big_drop"]].index.tolist()

    # Filter to stocks not already in our book
    current_holdings = set(context.days_held.keys())
    new_candidates = [a for a in dip_candidates if a not in current_holdings]

    # Determine how many slots remain
    open_slots = MAX_POSITIONS - len(context.days_held)
    if open_slots <= 0 or not new_candidates:
        return

    # Limit to available slots
    to_buy = new_candidates[:open_slots]

    target_value = context.portfolio.portfolio_value * POSITION_SIZE

    for asset in to_buy:
        if data.can_trade(asset):
            algo.order_target_value(asset, target_value, style=MarketOnCloseOrder())
            context.days_held[asset] = 0  # Day 0: just entered