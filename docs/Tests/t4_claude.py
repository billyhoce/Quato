import zipline.api as algo
from zipline.pipeline import Pipeline, EquityPricing, master
from zipline.pipeline.factors import DailyReturns
from zipline.pipeline.filters import StaticUniverse

# Hold for exactly 3 trading days after entry
HOLD_DAYS = 3
# Trigger: single-day drop exceeding this threshold
DROP_THRESHOLD = -0.03
# Fixed dollar amount per position
POSITION_VALUE = 5000.0


def initialize(context):
    \"\"\"Set up pipeline and schedule daily check.\"\"\"
    context.positions_entry = {}  # asset -> entry day count

    are_in_universe = StaticUniverse(\"bluechip-us-stable\")

    pipe = Pipeline(
        columns={
            \"daily_return\": DailyReturns(),
        },
        initial_universe=are_in_universe,
    )
    algo.attach_pipeline(pipe, \"signals\")
    algo.schedule_function(
        trade,
        algo.date_rules.every_day(),
        algo.time_rules.market_close(minutes=1),
    )


def before_trading_start(context, data):
    \"\"\"Fetch today's pipeline output.\"\"\"
    context.pipe_output = algo.pipeline_output(\"signals\")
    # Increment hold counter for open positions
    to_delete = []
    for asset in list(context.positions_entry.keys()):
        context.positions_entry[asset] += 1
        if context.positions_entry[asset] >= HOLD_DAYS:
            to_delete.append(asset)
    for asset in to_delete:
        del context.positions_entry[asset]


def trade(context, data):
    \"\"\"Exit positions that have been held 3 days; enter on big drops.\"\"\"
    # Exit positions that have completed their 3-day hold
    current_positions = {p: v for p, v in context.portfolio.positions.items() if v.amount != 0}
    for asset in current_positions:
        if asset not in context.positions_entry:
            # Hold period expired (removed in before_trading_start)
            if data.can_trade(asset):
                algo.order_target_value(asset, 0)

    # Enter new positions: stocks that dropped more than 3% today
    pipe = context.pipe_output
    dropped = pipe[pipe[\"daily_return\"] < DROP_THRESHOLD]
    for asset in dropped.index:
        if asset not in context.positions_entry and data.can_trade(asset):
            algo.order_target_value(asset, POSITION_VALUE)
            context.positions_entry[asset] = 0