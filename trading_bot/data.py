"""Obtención de precios (velas OHLCV): desde un exchange, un CSV o datos sintéticos."""

import time

import numpy as np
import pandas as pd

from . import config

COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

_TIMEFRAME_MS = {"m": 60_000, "h": 3_600_000, "d": 86_400_000}


def timeframe_to_ms(timeframe):
    return int(timeframe[:-1]) * _TIMEFRAME_MS[timeframe[-1]]


def _to_frame(rows):
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("timestamp").astype(float)


def fetch_ohlcv(symbol=config.SYMBOL, timeframe=config.TIMEFRAME, days=180,
                exchange_id=config.EXCHANGE):
    """Descarga velas públicas del exchange (no necesita API keys)."""
    import ccxt  # import aquí para que el modo sintético funcione sin ccxt instalado

    exchange = getattr(ccxt, exchange_id)({"enableRateLimit": True})
    step = timeframe_to_ms(timeframe)
    since = exchange.milliseconds() - days * 86_400_000
    rows = []
    while since < exchange.milliseconds():
        batch = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        if not batch:
            break
        rows.extend(batch)
        since = batch[-1][0] + step
    df = _to_frame(rows)
    df = df[~df.index.duplicated(keep="last")]
    # La última vela sigue abierta: su cierre aún puede cambiar, así que no la usamos.
    return df.iloc[:-1]


def load_csv(path):
    """Carga un CSV con columnas timestamp,open,high,low,close,volume."""
    df = pd.read_csv(path, parse_dates=["timestamp"], index_col="timestamp")
    return df[COLUMNS[1:]].astype(float)


def synthetic_ohlcv(n=2000, seed=42, drift=0.0002, volatility=0.01, start_price=30_000.0):
    """Genera precios aleatorios (paseo aleatorio) para probar sin internet."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(drift, volatility, n)
    close = start_price * np.exp(np.cumsum(returns))
    open_ = np.concatenate([[start_price], close[:-1]])
    spread = np.abs(rng.normal(0, volatility / 2, n)) * close
    end = int(time.time() // 3600 * 3600 * 1000)
    timestamps = end - np.arange(n)[::-1] * 3_600_000
    rows = np.column_stack([
        timestamps, open_, np.maximum(open_, close) + spread,
        np.minimum(open_, close) - spread, close, rng.uniform(10, 100, n),
    ])
    return _to_frame(rows)
