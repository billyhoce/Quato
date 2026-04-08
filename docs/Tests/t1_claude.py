import zipline.api as algo

def initialize(context):
    # SID lookup deferred to before_trading_start
    context.bought = False
    context.spy_sid = \"FIBBG000BDTBL9\"  # SPY

def before_trading_start(context, data):
    if not hasattr(context, 'spy'):
        context.spy = algo.sid(\"FIBBG000BDTBL9\")

def rebalance(context, data):
    if not context.bought:
        algo.order_target_percent(context.spy, 1.0)
        context.bought = True