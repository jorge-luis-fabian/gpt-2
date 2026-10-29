"""Bot de cartera: reparte el dinero entre varias monedas.

Cada estrategia devuelve una tabla de pesos objetivo (fecha x moneda, 0 a 1)
decididos con el cierre de cada día. Una fila con NaN significa "no tocar
nada ese día". La suma de una fila es lo invertido; el resto queda en USDT.

El motor aplica los pesos desde el día siguiente, cobra comisión y
deslizamiento sobre lo que compra y vende, y deja que los pesos se muevan con
los precios entre rebalanceos.
"""

import numpy as np
import pandas as pd

MIN_HISTORY = 200          # días de historia antes de poder operar una moneda
MIN_VOLUME = 5_000_000     # volumen medio diario mínimo (USDT, últimos 30 días)
COST = 0.001 + 0.0005      # comisión 0.1 % + deslizamiento 0.05 % por operación
REGIME = "BTC/USDT"        # el "termómetro" del mercado


def eligible(closes, volume, min_volume=MIN_VOLUME):
    """Monedas operables cada día: con historia suficiente y liquidez."""
    history = closes.notna().cumsum()
    liquid = volume.rolling(30, min_periods=30).mean() >= min_volume
    return closes.notna() & (history >= MIN_HISTORY) & liquid


def _only_changes(w):
    """Deja NaN las filas iguales a la anterior: así solo se opera si algo cambia."""
    same = (w.fillna(0).diff().abs().sum(axis=1) < 1e-12)
    same.iloc[0] = False
    w = w.copy()
    w[same] = np.nan
    return w


def _regime_on(closes, n=200):
    btc = closes[REGIME]
    return (btc > btc.rolling(n).mean()).reindex(closes.index).fillna(False)


# ---------------------------------------------------------------- estrategias

def hold_btc(closes, elig):
    w = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    w[REGIME] = 1.0
    w.iloc[1:] = np.nan
    return w


def hold_all(closes, elig, every=30):
    """Todas las monedas operables a partes iguales, rebalanceo mensual."""
    w = elig.astype(float).div(elig.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    w[np.arange(len(w)) % every != 0] = np.nan
    return w


def trend(closes, elig, n=200, regime=False):
    """Cada moneda entra si su precio está sobre su media de n días."""
    on = (closes > closes.rolling(n).mean()) & elig
    if regime:
        on = on.mul(_regime_on(closes), axis=0).astype(bool)
    count = elig.sum(axis=1).replace(0, np.nan)
    return _only_changes(on.astype(float).div(count, axis=0).fillna(0))


def momentum(closes, elig, lookback=60, top=5, every=7):
    """Rotación: cada semana compra las `top` monedas que más subieron.

    Solo con BTC sobre su media de 200 días; cada elegida debe haber subido en
    el periodo y estar sobre su propia media de 100 días. Si no hay ninguna, USDT.
    """
    ret = closes / closes.shift(lookback) - 1
    ok = elig & (ret > 0) & (closes > closes.rolling(100).mean())
    ok = ok.mul(_regime_on(closes), axis=0).astype(bool)
    score = ret.where(ok)
    rank = score.rank(axis=1, ascending=False)
    w = (rank <= top).astype(float) / top
    w[np.arange(len(w)) % every != 0] = np.nan
    return w


def donchian(closes, elig, entry=20, exit=10):
    """Ruptura por moneda: entra al superar el máximo de `entry` días, sale al perder el mínimo de `exit`."""
    upper = closes.rolling(entry).max().shift(1)
    lower = closes.rolling(exit).min().shift(1)
    c, up, lo, el = closes.to_numpy(), upper.to_numpy(), lower.to_numpy(), elig.to_numpy()
    on = np.zeros(c.shape, dtype=bool)
    inside = np.zeros(c.shape[1], dtype=bool)
    for t in range(len(c)):
        inside = np.where(~inside & (c[t] > up[t]), True, inside)
        inside = np.where(inside & (c[t] < lo[t]), False, inside)
        inside &= el[t]
        on[t] = inside
    count = elig.sum(axis=1).replace(0, np.nan)
    w = pd.DataFrame(on, index=closes.index, columns=closes.columns).astype(float)
    return _only_changes(w.div(count, axis=0).fillna(0))


STRATEGIES = {
    "hold_btc": hold_btc,
    "hold_all": hold_all,
    "trend": trend,
    "momentum": momentum,
    "donchian": donchian,
}

# Combinaciones a probar: pocas y con valores clásicos, para no sobreoptimizar.
GRID = (
    [("trend", {"n": n, "regime": r}) for n in (50, 100, 200) for r in (False, True)]
    + [("momentum", {"lookback": lb, "top": k}) for lb in (30, 60, 90) for k in (3, 5)]
    + [("donchian", {"entry": a, "exit": b}) for a, b in ((20, 10), (55, 20))]
)
BENCHMARKS = [("hold_btc", {}), ("hold_all", {})]


def label(name, params):
    names = {
        "hold_btc": "Comprar y mantener BTC",
        "hold_all": "Comprar y mantener todas",
        "trend": "Tendencia {n} días",
        "momentum": "Rotación top {top}, {lookback} días",
        "donchian": "Donchian {entry}/{exit}",
    }
    text = names[name].format(**params)
    if params.get("regime"):
        text += " + filtro BTC"
    return text


def weights(name, params, closes, elig):
    return STRATEGIES[name](closes, elig, **params)


# ---------------------------------------------------------------- motor

def run(closes, w, cost=COST):
    """Simula la cartera. Devuelve (capital diario, pesos reales, rotación diaria)."""
    rets = (closes / closes.shift(1) - 1).to_numpy()
    target = w.to_numpy()
    alive = closes.notna().to_numpy()
    n_days, n_assets = rets.shape
    held = np.zeros(n_assets)
    equity = np.ones(n_days)
    real = np.zeros((n_days, n_assets))
    turnover = np.zeros(n_days)
    for t in range(n_days):
        if t > 0:
            r = np.nan_to_num(rets[t])
            growth = 1 + held @ r
            equity[t] = equity[t - 1] * growth
            held = held * (1 + r) / growth if growth > 0 else held * 0
        new = held.copy()
        if not np.isnan(target[t]).all():
            new = np.nan_to_num(target[t])
        dead = ~alive[t]
        if t + 1 < n_days:
            dead |= ~alive[t + 1]       # la moneda deja de cotizar mañana: se vende hoy
        new[dead] = 0.0
        trade = np.abs(new - held).sum()
        if trade > 1e-9:
            equity[t] *= 1 - cost * trade
            turnover[t] = trade
            held = new
        real[t] = held
    idx = closes.index
    return (pd.Series(equity, idx), pd.DataFrame(real, idx, closes.columns),
            pd.Series(turnover, idx))


def metrics(equity, real=None, turnover=None):
    """Métricas de un tramo de la curva de capital (diaria)."""
    equity = equity / equity.iloc[0]
    days = (equity.index[-1] - equity.index[0]).days or 1
    daily = equity.pct_change().dropna()
    vol = daily.std() * np.sqrt(365)
    dd = (equity / equity.cummax() - 1).min()
    cagr = equity.iloc[-1] ** (365 / days) - 1
    out = {
        "retorno": equity.iloc[-1] - 1,
        "anual": cagr,
        "volatilidad": vol,
        "sharpe": daily.mean() / daily.std() * np.sqrt(365) if daily.std() > 0 else 0.0,
        "caida": dd,
        "calmar": cagr / -dd if dd < 0 else 0.0,
    }
    if real is not None:
        out["invertido"] = real.loc[equity.index].sum(axis=1).mean()
    if turnover is not None:
        out["rotacion"] = turnover.loc[equity.index].sum() / days * 365
    return out
