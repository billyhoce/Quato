import zipline.api as algo

# SIDs for AAPL, MSFT, SPY
AAPL_SID = \"FIBBG000B9XRY4\"
MSFT_SID = \"FIBBG000BPH459\"
SPY_SID  = \"FIBBG000BDTBL9\"

# Number of 1-minute bars spanning 30 minutes of history
LOOKBACK_BARS = 31  # 31 bars gives us open-to-close of a 30-minute window
REBALANCE_INTERVAL = 15  # rebalance every 15 minutes

def initialize(context):
    \"\"\"Schedule rebalancing every 15 minutes using market_open offsets.\"\"\"
    context.assets = None  # will be populated in before_trading_start

    # Market session is 9:30 - 16:00 = 390 minutes
    # Schedule at minute offsets: 15, 30, 45, ... up to 375 (last rebalance)
    trading_minutes = list(range(REBALANCE_INTERVAL, 390, REBALANCE_INTERVAL))

    for minute_offset in trading_minutes:
        algo.schedule_function(
            rebalance,
            algo.date_rules.every_day(),
            algo.time_rules.market_open(minutes=minute_offset),
        )


def before_trading_start(context, data):
    \"\"\"Look up asset objects once per day.\"\"\"
    context.assets = [
        algo.sid(AAPL_SID),
        algo.sid(MSFT_SID),
        algo.sid(SPY_SID),
    ]


def rebalance(context, data):
    \"\"\"
    Every 15 minutes:
    - Compute 30-minute return for each asset.
    - Go long the best performer (50% of portfolio).
    - Go short the worst performer (-50% of portfolio).
    - Keep the middle asset flat (0%).
    \"\"\"
    assets = context.assets
    if assets is None:
        return

    # Fetch last 31 minute close prices to get a 30-bar return
    prices = data.history(assets, \"close\", LOOKBACK_BARS, \"1m\")

    if prices.isnull().any().any():
        return

    # 30-minute return: last close vs close 30 bars ago
    start_prices = prices.iloc[0]
    end_prices   = prices.iloc[-1]
    returns = (end_prices - start_prices) / start_prices

    # Rank: best (long), worst (short), middle (flat)
    ranked = returns.sort_values()
    worst  = ranked.index[0]
    best   = ranked.index[-1]
    middle = ranked.index[1]

    # Market-neutral: +50% long, -50% short, 0% middle
    algo.order_target_percent(best,   0.5)
    algo.order_target_percent(worst, -0.5)
    algo.order_target_percent(middle, 0.0)