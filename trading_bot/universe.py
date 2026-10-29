"""Monedas candidatas y descarga de su historia diaria (con caché en disco).

La lista incluye las monedas grandes de hoy y también varias que fueron grandes
en 2018 y luego se hundieron o salieron de Binance. Si solo probáramos las
ganadoras de hoy, el resultado saldría inflado (sesgo de supervivencia).
"""

import os
import time

import numpy as np
import pandas as pd

from . import data

UNIVERSE = [
    # grandes hoy
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT", "DOGE/USDT",
    "TRX/USDT", "LINK/USDT", "AVAX/USDT", "DOT/USDT", "LTC/USDT", "BCH/USDT", "XLM/USDT",
    "ATOM/USDT", "ETC/USDT", "NEAR/USDT", "UNI/USDT", "FIL/USDT", "AAVE/USDT",
    # grandes en 2018-2020 que perdieron peso (o ya no cotizan)
    "EOS/USDT", "NEO/USDT", "IOTA/USDT", "XMR/USDT", "ZEC/USDT", "DASH/USDT",
    "QTUM/USDT", "ONT/USDT", "VET/USDT", "ICX/USDT",
]

START = "2017-08-01"  # BTC/USDT empieza a cotizar en Binance en agosto de 2017
CACHE_DIR = "datos"


def _cache_path(symbol, cache_dir):
    return os.path.join(cache_dir, symbol.replace("/", "-") + "_1d.csv")


def download(symbols=UNIVERSE, start=START, cache_dir=CACHE_DIR, exchange_id="binance",
             refresh=False, log=print):
    """Descarga velas diarias de cada moneda. Devuelve {símbolo: DataFrame}.

    Guarda cada moneda en `cache_dir`; si el archivo es de hoy, no la vuelve a bajar.
    Las monedas que no existen en el exchange se saltan con un aviso.
    """
    os.makedirs(cache_dir, exist_ok=True)
    exchange = None
    days = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(start, tz="UTC")).days + 1
    out = {}
    for symbol in symbols:
        path = _cache_path(symbol, cache_dir)
        fresh = os.path.exists(path) and time.time() - os.path.getmtime(path) < 20 * 3600
        if fresh and not refresh:
            out[symbol] = data.load_csv(path)
            continue
        try:
            exchange = exchange or data.make_exchange(exchange_id)
            df = data.fetch_ohlcv(symbol, "1d", days, exchange_id, exchange=exchange)
        except Exception as e:  # moneda inexistente o retirada del exchange
            log(f"  {symbol}: no disponible ({type(e).__name__}), se omite")
            continue
        if len(df) < 30:
            log(f"  {symbol}: muy poca historia ({len(df)} días), se omite")
            continue
        df.to_csv(path, index_label="timestamp")
        log(f"  {symbol}: {len(df)} días ({df.index[0]:%Y-%m-%d} -> {df.index[-1]:%Y-%m-%d})")
        out[symbol] = df
    return out


def synthetic_universe(n_assets=12, days=3000, seed=7):
    """Monedas inventadas y correlacionadas, para probar sin internet.

    Hay un factor común (como BTC arrastrando al mercado) con fases alcistas y
    bajistas, monedas que empiezan a cotizar más tarde y algunas que se hunden.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range(end=pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=1),
                        periods=days, freq="D")
    regime = np.repeat(rng.choice([0.004, -0.004, 0.0], size=days // 200 + 1), 200)[:days]
    market = rng.normal(regime, 0.03)
    out = {}
    for i in range(n_assets):
        beta = 1.0 if i == 0 else rng.uniform(0.8, 1.6)
        drift = 0.0 if i < n_assets * 2 // 3 else -0.0015  # el último tercio se hunde
        r = beta * market + rng.normal(drift, 0.035 if i else 0.0, days)
        close = 100 * np.exp(np.cumsum(r))
        start = 0 if i < 3 else rng.integers(0, days // 2)
        df = pd.DataFrame({"open": np.r_[close[0], close[:-1]], "close": close}, index=idx)
        df["high"] = df[["open", "close"]].max(axis=1) * 1.01
        df["low"] = df[["open", "close"]].min(axis=1) * 0.99
        df["volume"] = 1e9 / close
        name = "BTC/USDT" if i == 0 else f"MON{i:02d}/USDT"
        out[name] = df.iloc[start:][data.COLUMNS[1:]]
    return out


def panel(frames):
    """Une las monedas en tablas fecha x moneda: cierres y volumen en USDT."""
    closes = pd.DataFrame({s: df["close"] for s, df in frames.items()}).sort_index()
    volume = pd.DataFrame({s: df["close"] * df["volume"] for s, df in frames.items()}).sort_index()
    return closes, volume
