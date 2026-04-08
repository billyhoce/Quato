import zipline.api as algo

RANGE_MINUTES = 30

def initialize(context):
    context.aapl = None
    context.range_high = None
    context.range_low = None
    context.range_set = False
    context.traded_today = False

    algo.schedule_function(
        set_opening_range,
        algo.date_rules.every_day(),
        algo.time_rules.market_open(minutes=RANGE_MINUTES)
    )

    algo.schedule_function(
        close_positions,
        algo.date_rules.every_day(),
        algo.time_rules.market_close(minutes=1)
    )


def before_trading_start(context, data):
    context.aapl = algo.sid(\"FIBBG000B9XRY4\")
    context.range_high = None
    context.range_low = None
    context.range_set = False
    context.traded_today = False


def set_opening_range(context, data):
    if context.aapl is None:
        return
    bars = data.history(context.aapl, [\"high\", \"low\"], RANGE_MINUTES, \"1m\")
    if bars is None or len(bars) < RANGE_MINUTES:
        return
    context.range_high = bars[\"high\"].max()
    context.range_low = bars[\"low\"].min()
    context.range_set = True


def handle_data(context, data):
    if not context.range_set:
        return
    if context.traded_today:
        return
    if context.aapl is None:
        return

    current_price = data.current(context.aapl, \"price\")

    if current_price > context.range_high:
        algo.order_target(context.aapl, 100)
        context.traded_today = True
    elif current_price < context.range_low:
        algo.order_target(context.aapl, -100)
        context.traded_today = True


def close_positions(context, data):
    if context.aapl is not None:
        algo.order_target(context.aapl, 0)