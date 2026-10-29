"""Estrategias del bot.

Cada estrategia añade al DataFrame:
- `signal`: 1 = queremos estar comprados, 0 = fuera (en USDT), calculado con el
  cierre de cada vela.
- `position`: la señal desplazada una vela. Solo podemos actuar DESPUÉS de ver el
  cierre, así que la posición nueva se aplica en la vela siguiente. Sin este
  desplazamiento el backtest "mira el futuro" y da resultados irreales.
- `line1` / `line2`: las líneas que se dibujan sobre el precio en el reporte.

Estrategias disponibles (ver STRATEGIES al final):
- sma:      cruce de medias móviles (seguimiento de tendencia).
- donchian: ruptura de máximos/mínimos, el sistema de las "tortugas".
- rsi:      compra caídas puntuales (RSI bajo) solo dentro de una tendencia alcista.
"""

import numpy as np

from . import config


def _finish(df, signal, line1, line2=None):
    df["signal"] = signal
    df["position"] = df["signal"].shift(1).fillna(0).astype(int)
    df["line1"] = line1
    df["line2"] = np.nan if line2 is None else line2
    return df


def generate_signals(df, fast=config.FAST_PERIOD, slow=config.SLOW_PERIOD):
    """Cruce de medias: comprado mientras la media rápida está sobre la lenta."""
    if fast >= slow:
        raise ValueError("La media rápida debe tener menos velas que la lenta")
    df = df.copy()
    df["sma_fast"] = df["close"].rolling(fast).mean()
    df["sma_slow"] = df["close"].rolling(slow).mean()
    signal = (df["sma_fast"] > df["sma_slow"]).astype(int)
    signal[df["sma_slow"].isna()] = 0  # sin datos suficientes, no operamos
    return _finish(df, signal, df["sma_fast"], df["sma_slow"])


def donchian_signals(df, entry=20, exit=10):
    """Ruptura de Donchian.

    Compra cuando el cierre supera el máximo de las `entry` velas anteriores y
    vende cuando cae por debajo del mínimo de las `exit` velas anteriores.
    """
    df = df.copy()
    upper = df["high"].rolling(entry).max().shift(1)
    lower = df["low"].rolling(exit).min().shift(1)
    close, up, low = df["close"].to_numpy(), upper.to_numpy(), lower.to_numpy()
    signal = np.zeros(len(df), dtype=int)
    inside = 0
    for i in range(len(df)):
        if not inside and close[i] > up[i]:
            inside = 1
        elif inside and close[i] < low[i]:
            inside = 0
        signal[i] = inside
    return _finish(df, signal, upper, lower)


def rsi(close, period=14):
    """RSI de Wilder (0-100): bajo = el precio cayó mucho en poco tiempo."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    return 100 - 100 / (1 + gain / loss)


def rsi_signals(df, period=14, buy=30, sell=55, trend=200):
    """RSI con filtro de tendencia.

    Solo opera si el precio está sobre su media de `trend` velas. Compra cuando
    el RSI baja de `buy` y vende cuando sube de `sell` o el precio pierde la media.
    """
    df = df.copy()
    df["rsi"] = rsi(df["close"], period)
    sma = df["close"].rolling(trend).mean()
    close, r, t = df["close"].to_numpy(), df["rsi"].to_numpy(), sma.to_numpy()
    signal = np.zeros(len(df), dtype=int)
    inside = 0
    for i in range(len(df)):
        if not inside and close[i] > t[i] and r[i] < buy:
            inside = 1
        elif inside and (r[i] > sell or close[i] < t[i]):
            inside = 0
        signal[i] = inside
    return _finish(df, signal, sma)


STRATEGIES = {
    "sma": {
        "fn": generate_signals,
        "defaults": {"fast": config.FAST_PERIOD, "slow": config.SLOW_PERIOD},
        "name": "cruce de medias {fast}/{slow}",
        "rule": "Compra cuando la media de {fast} velas cruza por encima de la de {slow}, "
                "y vende cuando cruza por debajo.",
        "how": "Mientras la línea naranja (media rápida) está por encima de la morada (lenta), "
               "el bot está comprado.",
        "lines": ("Media rápida ({fast})", "Media lenta ({slow})"),
    },
    "donchian": {
        "fn": donchian_signals,
        "defaults": {"entry": 20, "exit": 10},
        "name": "ruptura de Donchian {entry}/{exit}",
        "rule": "Compra cuando el precio cierra por encima del máximo de las {entry} velas "
                "anteriores, y vende cuando cierra por debajo del mínimo de las {exit} anteriores.",
        "how": "El bot compra cuando el precio rompe la línea naranja (máximo) y vende cuando "
               "rompe la morada (mínimo).",
        "lines": ("Máximo de {entry} velas", "Mínimo de {exit} velas"),
    },
    "rsi": {
        "fn": rsi_signals,
        "defaults": {"period": 14, "buy": 30, "sell": 55, "trend": 200},
        "name": "RSI {buy}/{sell} con tendencia {trend}",
        "rule": "Solo si el precio está sobre su media de {trend} velas: compra cuando el RSI({period}) "
                "baja de {buy} y vende cuando sube de {sell} o el precio pierde la media.",
        "how": "El bot solo compra cuando el precio está sobre la línea naranja (media de {trend}) "
               "y acaba de caer con fuerza.",
        "lines": ("Media de {trend} velas", None),
    },
}


def get_params(strategy, **overrides):
    """Parámetros por defecto de la estrategia, con los cambios que se pasen."""
    params = dict(STRATEGIES[strategy]["defaults"])
    params.update({k: v for k, v in overrides.items() if k in params and v is not None})
    return params


def warmup(params):
    """Velas que necesita la estrategia antes de poder dar señales."""
    return max(v for v in params.values() if isinstance(v, int))


def describe(strategy, params):
    s = STRATEGIES[strategy]
    label2 = s["lines"][1]
    return {
        "name": s["name"].format(**params),
        "rule": s["rule"].format(**params),
        "how": s["how"].format(**params),
        "line1": s["lines"][0].format(**params),
        "line2": label2.format(**params) if label2 else None,
    }


def run_signals(df, strategy="sma", params=None):
    params = params or get_params(strategy)
    return STRATEGIES[strategy]["fn"](df, **params)
