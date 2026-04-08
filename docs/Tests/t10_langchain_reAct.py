import zipline.api as algo
from zipline.pipeline import Pipeline, EquityPricing
from zipline.pipeline.factors import SimpleMovingAverage, Returns
from zipline.pipeline.filters import StaticSids

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
MA_WINDOW = 100       # days for the moving average trend filter
MOMENTUM_WINDOW = 252 # days for the 12-month return (earnings/revenue proxy)

# Confirmed S&P 500 large-cap SIDs available in the usstock-learn-1d bundle
SP500_SIDS = [
    "FIBBG000B9XRY4",  # AAPL
    "FIBBG000BCQZS4",  # AXP
    "FIBBG000BCSST7",  # BA
    "FIBBG000BCTLF6",  # BAC
    "FIBBG000BF0K17",  # CAT
    "FIBBG000BH4R78",  # DIS
    "FIBBG000BJ81C1",  # TRV
    "FIBBG000BK6MB5",  # GE
    "FIBBG000BKZB36",  # HD
    "FIBBG000BLNNH6",  # IBM
    "FIBBG000BMHYD1",  # JNJ
    "FIBBG000BMX289",  # KO
    "FIBBG000BNSZP1",  # MCD
    "FIBBG000BP52R2",  # MMM
    "FIBBG000BPD168",  # MRK
    "FIBBG000BPH459",  # MSFT
    "FIBBG000BR2B91",  # PFE
    "FIBBG000BR2TH3",  # PG
    "FIBBG000BSJK37",  # T
    "FIBBG000BWXBC2",  # WMT
    "FIBBG000C0G1D1",  # INTC
    "FIBBG000C3J3C9",  # CSCO
    "FIBBG000DH7JK6",  # PEP
    "FIBBG000DMBXR2",  # JPM
    "FIBBG000FY4S11",  # C
    "FIBBG000GZQ728",  # XOM
    "FIBBG000HS77T5",  # VZ
    "FIBBG000K4ND22",  # CVX
    "FIBBG00BN961G4",  # DD
    "FIBBG000B9XYV2",  # AMT
    "FIBBG000B9ZXB4",  # ABT
    "FIBBG000BB6KF5",  # MET
    "FIBBG000BB9KF2",  # AEP
    "FIBBG000BBDZG3",  # AIG
    "FIBBG000BBS2Y0",  # AMGN
    "FIBBG000BFC8J2",  # CELG
    "FIBBG000BGKTF9",  # COF
    "FIBBG000BGVW60",  # D
    "FIBBG000BHGDH5",  # DUK
    "FIBBG000BHX7N2",  # EMR
    "FIBBG000BJ2D31",  # SPG
    "FIBBG000BJSBJ0",  # NEE
    "FIBBG000BK67C7",  # GD
    "FIBBG000BKY1G5",  # WELL
    "FIBBG000BLZRJ2",  # MS
    "FIBBG000BNDN65",  # LOW
    "FIBBG000BNWG87",  # MDT
    "FIBBG000BQ2C28",  # NOC
    "FIBBG000BT9DW0",  # SO
    "FIBBG000BVVQQ8",  # TXT
    "FIBBG000BW8S60",  # RTX
    "FIBBG000BWQFY7",  # WFC
    "FIBBG000C17X76",  # BIIB
    "FIBBG000C1BW00",  # LMT
    "FIBBG000C2PW58",  # BLK
    "FIBBG000C2ZCH8",  # SRE
    "FIBBG000C6CFJ5",  # GS
    "FIBBG000CH5208",  # UNH
    "FIBBG000CKGBP2",  # GILD
    "FIBBG000DQLV23",  # BMY
    "FIBBG000F6H8W8",  # COST
    "FIBBG000FFDM15",  # USB
    "FIBBG000FV1Z23",  # CCI
    "FIBBG000H556T9",  # HON
    "FIBBG000H8TVT2",  # TGT
    "FIBBG000HCJMF9",  # PRU
    "FIBBG000J6XT05",  # EXC
]


def initialize(context: algo.Context):
    """
    Attach a pipeline that screens a static universe of S&P 500 large-caps
    using two price-based filters:
    - 12-month return above the median of the group (momentum proxy for
      earnings and revenue growth)
    - Price above the 100-day moving average (trend confirmation)

    Rebalances monthly on the first trading day.
    """
    in_universe = StaticSids(SP500_SIDS)

    # 12-month momentum: proxy for earnings/revenue trajectory
    momentum = Returns(window_length=MOMENTUM_WINDOW, mask=in_universe)
    above_median_momentum = momentum.percentile_between(50, 100, mask=in_universe)

    # 100-day moving average trend filter
    close = EquityPricing.close.latest
    ma_100 = SimpleMovingAverage(
        inputs=[EquityPricing.close],
        window_length=MA_WINDOW,
        mask=in_universe,
    )
    above_ma = close > ma_100

    screen = in_universe & above_median_momentum & above_ma

    pipe = Pipeline(
        columns={
            "momentum": momentum,
            "above_ma": above_ma,
        },
        initial_universe=in_universe,
        screen=screen,
    )

    algo.attach_pipeline(pipe, "sp500_momentum_ma")

    algo.schedule_function(
        rebalance,
        algo.date_rules.month_start(days_offset=0),
        algo.time_rules.market_open(minutes=30),
    )


def before_trading_start(context: algo.Context, data: algo.BarData):
    """
    Retrieve today's pipeline results before the market opens.
    """
    context.pipe_results = algo.pipeline_output("sp500_momentum_ma")


def rebalance(context: algo.Context, data: algo.BarData):
    """
    Equal-weight all stocks passing the momentum and moving average screens.
    Exit any position that no longer qualifies.
    """
    qualifying_assets = context.pipe_results.index.tolist()

    num_positions = len(qualifying_assets)
    target_weight = 1.0 / num_positions if num_positions > 0 else 0.0

    # Exit positions no longer in the qualifying set
    for asset in list(context.portfolio.positions.keys()):
        if asset not in qualifying_assets:
            algo.order_target_percent(asset, 0.0)

    # Enter or rebalance qualifying positions
    for asset in qualifying_assets:
        if data.can_trade(asset):
            algo.order_target_percent(asset, target_weight)