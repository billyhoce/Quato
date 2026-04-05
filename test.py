from quantrocket import master
# Build post-fetch filter for usstock_SecurityType2 (not a native API param)

df = master.get_securities(
    exchanges=["XNAS", "XNYS", "ARCX", "BATS"],
    sec_types=None,
    symbols=["MMM", "AOS", "ABT", "ABBV", "ACN", "ATVI", "AYI", "ADBE", "AAP", "AES"],
    universes=None,
    exclude_delisted=True,
    fields=["Symbol", "Name", "usstock_SecurityType2", "Exchange", "SecType"],
)

print(df)