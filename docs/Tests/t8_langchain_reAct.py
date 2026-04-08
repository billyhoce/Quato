import zipline.api as algo

# SIDs for the three target assets
SID_AAPL = "FIBBG000B9XRY4"
SID_MSFT = "FIBBG000BPH459"
SID_SPY  = "FIBBG000BDTBL9"

# Number of 1-minute bars needed to compute a 30-minute return
# We need 31 bars: bar[0] is the start price, bar[30] is the end price
HISTORY_BARS = 31

# Long and short target allocations (market-neutral: +50% / -50%)
LONG_WEIGHT  =  0.5
SHORT_WEIGHT = -0.5


def initialize(context):
    """
    Look up assets and schedule the rebalance function every 15 minutes
    throughout the trading day (from market open to ~6 hours 15 minutes after open,
    covering the full 6.5-hour NYSE session in 15-minute increments).
    """
    # Store SID strings only -- asset objects are resolved in before_trading_start
    context.sids = [SID_AAPL, SID_MSFT, SID_SPY]

    # Schedule rebalance every 15 minutes across the trading day.
    # NYSE regular session: 9:30 AM - 4:00 PM ET = 390 minutes = 26 intervals of 15 min.
    # We start at 1 minute after open (to have a valid price bar) and step every 15 minutes.
    # Offsets from market open (in minutes): 1, 16, 31, ..., up to 376 (just before close).
    for offset in range(1, 391, 15):
        algo.schedule_function(
            rebalance,
            algo.date_rules.every_day(),
            algo.time_rules.market_open(minutes=offset)
        )


def before_trading_start(context, data):
    """
    Resolve asset objects from their SIDs each morning so they are
    available for the intraday rebalance calls.
    """
    context.assets = [algo.sid(s) for s in context.sids]


def rebalance(context, data):
    """
    Every 15 minutes, compute the 30-minute return for each asset,
    rank them, go long the best performer and short the worst,
    and close the middle asset. Portfolio is kept market-neutral
    at roughly +50% long / -50% short.
    """
    assets = context.assets

    # Fetch the last HISTORY_BARS minutes of closing prices for all assets
    prices = data.history(assets, "close", HISTORY_BARS, "1m")

    # Drop any asset that has NaN values (e.g., not yet trading)
    prices = prices.dropna(axis=1)

    if prices.shape[1] < 3:
        # Not enough valid assets to form a long/short pair -- skip this bar
        return

    # Compute 30-minute return: (last bar / first bar) - 1
    returns = prices.iloc[-1] / prices.iloc[0] - 1

    # Rank assets by return: best = index 2, worst = index 0
    ranked = returns.sort_values()
    worst_asset  = ranked.index[0]
    middle_asset = ranked.index[1]
    best_asset   = ranked.index[2]

    # Rebalance: long the best, short the worst, flat the middle
    algo.order_target_percent(best_asset,   LONG_WEIGHT)
    algo.order_target_percent(worst_asset,  SHORT_WEIGHT)
    algo.order_target_percent(middle_asset, 0.0)