import zipline.api as algo
from zipline.pipeline import Pipeline, EquityPricing, master
from zipline.pipeline.factors import RSI, AverageDollarVolume

# Strategy parameters
RSI_WINDOW = 14
RSI_BUY_THRESHOLD = 30
RSI_SELL_THRESHOLD = 70
MAX_POSITIONS = 2
POSITION_SIZE = 1.0 / MAX_POSITIONS  # 50% per position

# Minimum average dollar volume to target large-cap stocks (~$50M/day)
MIN_ADV = 50e6


def initialize(context):
    """
    Set up the pipeline with RSI and large-cap defensive stock filters,
    and schedule daily rebalancing 30 minutes after market open.
    """
    context.rsi_data = None

    # initial_universe: only ANDed SecuritiesMaster terms are allowed here
    are_common_stocks = master.SecuritiesMaster.usstock_SecurityType2.latest.eq(
        "Common Stock"
    )
    are_primary_shares = (
        master.SecuritiesMaster.usstock_PrimaryShareSid.latest.isnull()
    )

    initial_universe = are_common_stocks & are_primary_shares

    # Sector filter for defensive sectors (placed in screen, not initial_universe,
    # because OR is not allowed in initial_universe)
    are_health_care = master.SecuritiesMaster.usstock_Sector.latest.eq("Health Care")
    are_consumer_staples = master.SecuritiesMaster.usstock_Sector.latest.eq(
        "Consumer Staples"
    )
    are_defensive = are_health_care | are_consumer_staples

    # Large-cap proxy: high average dollar volume over past quarter
    adv = AverageDollarVolume(window_length=63)
    are_large_cap = adv >= MIN_ADV

    # Price filter to avoid very cheap / distressed names
    are_above_5 = EquityPricing.close.latest >= 5

    pipe = Pipeline(
        columns={
            "rsi": RSI(window_length=RSI_WINDOW),
            "adv": adv,
        },
        initial_universe=initial_universe,
        screen=are_defensive & are_large_cap & are_above_5,
    )

    algo.attach_pipeline(pipe, "rsi_pipe")

    algo.schedule_function(
        rebalance,
        algo.date_rules.every_day(),
        algo.time_rules.market_open(minutes=30),
    )


def before_trading_start(context, data):
    """
    Retrieve today's pipeline output containing RSI values
    for all qualifying defensive large-cap stocks.
    """
    context.rsi_data = algo.pipeline_output("rsi_pipe")


def rebalance(context, data):
    """
    Each day:
    - Exit any position whose RSI has risen above 70 (overbought).
    - Enter up to MAX_POSITIONS stocks whose RSI has fallen below 30
      (oversold), equally weighted at 50% of portfolio value each.
    """
    if context.rsi_data is None or context.rsi_data.empty:
        return

    rsi_series = context.rsi_data["rsi"]

    # --- Exits: close positions that have become overbought ---
    for asset, position in context.portfolio.positions.items():
        if position.amount == 0:
            continue
        if asset in rsi_series.index:
            rsi_val = rsi_series.loc[asset]
            if rsi_val > RSI_SELL_THRESHOLD:
                algo.order_target_percent(asset, 0)
        else:
            # Asset dropped out of pipeline universe; close it
            algo.order_target_percent(asset, 0)

    # --- Entries: find oversold candidates ---
    current_positions = {
        asset
        for asset, pos in context.portfolio.positions.items()
        if pos.amount != 0
    }

    oversold = rsi_series[rsi_series < RSI_BUY_THRESHOLD]

    # Sort by most oversold (lowest RSI first) to prioritise strongest signals
    oversold = oversold.sort_values()

    slots_available = MAX_POSITIONS - len(current_positions)
    if slots_available <= 0:
        return

    for asset in oversold.index:
        if slots_available <= 0:
            break
        if asset in current_positions:
            continue
        if not data.can_trade(asset):
            continue
        algo.order_target_percent(asset, POSITION_SIZE)
        slots_available -= 1