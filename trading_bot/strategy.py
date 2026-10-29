"""Estrategia de cruce de medias móviles (SMA crossover).

- Si la media rápida está por encima de la lenta -> queremos estar comprados (1).
- Si está por debajo -> queremos estar fuera, en USDT (0).
"""

from . import config


def generate_signals(df, fast=config.FAST_PERIOD, slow=config.SLOW_PERIOD):
    """Añade columnas sma_fast, sma_slow, signal y position al DataFrame.

    `signal` se calcula con el cierre de cada vela. `position` es la señal
    desplazada una vela: solo podemos actuar DESPUÉS de ver el cierre, así que
    la posición nueva se aplica en la vela siguiente. Sin este desplazamiento el
    backtest "mira el futuro" y da resultados irreales.
    """
    if fast >= slow:
        raise ValueError("La media rápida debe tener menos velas que la lenta")
    df = df.copy()
    df["sma_fast"] = df["close"].rolling(fast).mean()
    df["sma_slow"] = df["close"].rolling(slow).mean()
    df["signal"] = (df["sma_fast"] > df["sma_slow"]).astype(int)
    df.loc[df["sma_slow"].isna(), "signal"] = 0  # sin datos suficientes, no operamos
    df["position"] = df["signal"].shift(1).fillna(0).astype(int)
    return df
