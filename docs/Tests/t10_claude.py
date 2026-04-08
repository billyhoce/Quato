import zipline.api as algo
from zipline.pipeline import Pipeline, EquityPricing, master
from zipline.pipeline.factors import SimpleMovingAverage, Returns, AverageDollarVolume

def initialize(context):
    # Proxies for fundamental quality — using price momentum
    ret_6m  = Returns(window_length=126)   # ~6-month return: proxy for earnings growth
    ret_12m = Returns(window_length=252)   # ~12-month return: proxy for revenue growth

    # Technical filter: price above 100-day moving average
    ma100 = SimpleMovingAverage(inputs=[EquityPricing.close], window_length=100)
    close = EquityPricing.close.latest
    above_ma = close > ma100

    # Large-cap proxy: top stocks by average daily dollar volume (replaces S&P 500 filter)
    adv = AverageDollarVolume(window_length=252)
    large_cap = adv.percentile_between(80, 100)

    # Common stocks only
    are_common_stocks = master.SecuritiesMaster.usstock_SecurityType2.latest.eq(\"Common Stock\")

    earnings_proxy = ret_6m  > 0
    revenue_proxy  = ret_12m > 0

    screen = are_common_stocks & large_cap & earnings_proxy & revenue_proxy & above_ma

    pipe = Pipeline(
        columns={
            'ret_6m':  ret_6m,
            'ret_12m': ret_12m,
            'ma100':   ma100,
        },
        initial_universe=are_common_stocks,
        screen=screen,
    )
    algo.attach_pipeline(pipe, 'largecap_momentum_proxy')

    algo.schedule_function(
        rebalance,
        algo.date_rules.month_start(),
        algo.time_rules.market_open(minutes=30)
    )


def before_trading_start(context, data):
    context.pipeline_data = algo.pipeline_output('largecap_momentum_proxy')


def rebalance(context, data):
    selected = context.pipeline_data.index.tolist()

    # Exit positions that no longer qualify
    for asset in list(context.portfolio.positions.keys()):
        if asset not in selected:
            algo.order_target_percent(asset, 0)

    # Equal-weight all qualifying stocks
    if len(selected) > 0:
        weight = 1.0 / len(selected)
        for asset in selected:
            if data.can_trade(asset):
                algo.order_target_percent(asset, weight)