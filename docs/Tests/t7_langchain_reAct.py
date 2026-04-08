import zipline.api as algo

# --- Constants ---
AAPL_SID = "FIBBG000B9XRY4"
OPENING_RANGE_MINUTES = 30  # Number of minutes to observe at open


def initialize(context: algo.Context):
    """
    Set up the opening-range breakout strategy for Apple.
    Schedules two jobs each day:
      1. Capture the opening-range high and low after the first 30 minutes.
      2. Close all positions one minute before the end of the day.
    Per-minute breakout checks are handled by handle_data().
    """
    context.opening_high = None
    context.opening_low = None
    context.range_set = False
    context.position_taken = None  # "long", "short", or None

    # 1. Record the opening range after the 30th minute
    algo.schedule_function(
        record_opening_range,
        algo.date_rules.every_day(),
        algo.time_rules.market_open(minutes=OPENING_RANGE_MINUTES),
    )

    # 2. Close all positions one minute before market close
    algo.schedule_function(
        close_positions,
        algo.date_rules.every_day(),
        algo.time_rules.market_close(minutes=1),
    )


def before_trading_start(context: algo.Context, data: algo.BarData):
    """
    Reset daily state before each trading session begins.
    """
    context.opening_high = None
    context.opening_low = None
    context.range_set = False
    context.position_taken = None
    context.aapl_sid = AAPL_SID


def record_opening_range(context: algo.Context, data: algo.BarData):
    """
    After the first 30 minutes of trading, capture the high and low
    of that opening range using historical minute bars.
    """
    aapl = algo.sid(context.aapl_sid)

    if not data.can_trade(aapl):
        return

    # Fetch the last 30 closed minute bars (the opening range)
    bars = data.history(aapl, ["high", "low"], OPENING_RANGE_MINUTES, "1m")

    context.opening_high = bars["high"].max()
    context.opening_low = bars["low"].min()
    context.range_set = True


def handle_data(context: algo.Context, data: algo.BarData):
    """
    Called every market minute. Once the opening range is set, check if
    the current price breaks above the high (go long) or below the low
    (go short). Avoids re-entering an already-held direction.
    """
    # Do nothing until the opening range has been recorded
    if not context.range_set:
        return

    aapl = algo.sid(context.aapl_sid)

    if not data.can_trade(aapl):
        return

    current_price = data.current(aapl, "price")

    if current_price > context.opening_high and context.position_taken != "long":
        _cancel_open_orders(aapl)
        algo.order_target_percent(aapl, 1.0)
        context.position_taken = "long"

    elif current_price < context.opening_low and context.position_taken != "short":
        _cancel_open_orders(aapl)
        algo.order_target_percent(aapl, -1.0)
        context.position_taken = "short"


def close_positions(context: algo.Context, data: algo.BarData):
    """
    One minute before market close, flatten all open positions in Apple
    and cancel any outstanding orders.
    """
    aapl = algo.sid(context.aapl_sid)

    _cancel_open_orders(aapl)

    if context.position_taken is not None:
        if data.can_trade(aapl):
            algo.order_target_percent(aapl, 0.0)
        context.position_taken = None


def _cancel_open_orders(asset):
    """
    Cancel all open orders for the given asset.
    """
    open_orders = algo.get_open_orders(asset)
    if open_orders:
        for order in open_orders:
            algo.cancel_order(order)