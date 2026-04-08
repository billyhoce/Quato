import zipline.api as algo


def initialize(context: algo.Context):
    """
    Schedule a one-time buy of SPY at the open on the first trading day.
    No further trades are made after the initial purchase.
    """
    context.has_bought = False
    context.spy_sid = "FIBBG000BDTBL9"

    algo.schedule_function(
        buy_and_hold,
        algo.date_rules.every_day(),
        algo.time_rules.market_open(minutes=1),
    )


def buy_and_hold(context: algo.Context, data: algo.BarData):
    """
    On the very first trading day, invest 100% of the portfolio in SPY.
    After that, do nothing.
    """
    if context.has_bought:
        return

    spy = algo.sid(context.spy_sid)

    if not data.can_trade(spy):
        return

    algo.order_target_percent(spy, 1.0)
    context.has_bought = True