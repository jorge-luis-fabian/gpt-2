"""El bot de cartera en paper trading (dinero ficticio).

Usa la estrategia y las monedas que eligió la investigación (bot_config.json).
Cada día, después del cierre diario (00:00 UTC), descarga los precios, calcula
la cartera objetivo y "compra/vende" para acercarse a ella. El estado se guarda
en paper_cartera.json.

Ejemplos:
    python -m trading_bot.bot              # una revisión y termina
    python -m trading_bot.bot --loop       # revisa cada día (deja la ventana abierta)
    python -m trading_bot.bot --synthetic  # prueba sin internet
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone

import pandas as pd

from . import portfolio as pf
from . import universe

STATE = "paper_cartera.json"


def load_config(path, synthetic):
    if synthetic:
        return {"strategy": "trend", "params": {"n": 200, "regime": False},
                "label": "Tendencia 200 días (prueba)", "universe": None, "passes": False}
    if not os.path.exists(path):
        raise SystemExit("Falta bot_config.json. Ejecuta primero: py -3.11 -m trading_bot.research")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def target_weights(cfg, closes, volume):
    """Cartera objetivo con los datos hasta el último cierre."""
    elig = pf.eligible(closes, volume)
    params = dict(cfg["params"])
    if cfg["strategy"] == "momentum":
        params["every"] = 1  # en vivo, el bot decide cuándo toca rebalancear
    w = pf.weights(cfg["strategy"], params, closes, elig)
    return w.ffill().iloc[-1].fillna(0)


def rebalance(state, target, prices, cost=pf.COST, threshold=0.02):
    """Lleva la cartera ficticia a los pesos objetivo. Devuelve las órdenes."""
    coins = state["coins"]
    value = state["cash"] + sum(q * prices[s] for s, q in coins.items())
    orders = []
    for s in sorted(set(coins) | set(target[target > 0].index)):
        want = target.get(s, 0.0) * value
        have = coins.get(s, 0.0) * prices[s]
        diff = want - have
        if abs(diff) < threshold * value and want > 0:
            continue  # cambio pequeño: no vale la comisión
        if abs(diff) < 1e-9:
            continue
        state["cash"] -= diff + abs(diff) * cost
        coins[s] = coins.get(s, 0.0) + diff / prices[s]
        if coins[s] * prices[s] < 1e-6:
            coins.pop(s)
        orders.append((s, "COMPRA" if diff > 0 else "VENTA", abs(diff), prices[s]))
    return orders, value


def step(cfg, state, frames):
    closes, volume = universe.panel(frames)
    if cfg.get("universe"):
        closes = closes[[s for s in cfg["universe"] if s in closes]]
        volume = volume[closes.columns]
    prices = closes.ffill().iloc[-1]
    day = closes.index[-1].strftime("%Y-%m-%d")
    target = target_weights(cfg, closes, volume)

    due = True
    if cfg["strategy"] == "momentum" and state.get("last_rebalance"):
        days = (pd.Timestamp(day) - pd.Timestamp(state["last_rebalance"])).days
        due = days >= cfg["params"].get("every", 7) or target.sum() == 0
    orders, value = rebalance(state, target, prices) if due else ([], None)
    if orders:
        state["last_rebalance"] = day
    value = state["cash"] + sum(q * prices[s] for s, q in state["coins"].items())
    state["history"].append({"day": day, "value": round(value, 2)})

    print(f"[{day}] {cfg['label']} · capital {value:,.2f} USDT")
    for s, side, amount, price in orders:
        print(f"  {side:<6} {s:<10} {amount:>10,.2f} USDT a {price:,.4f}")
    if not orders:
        print("  sin cambios" if due else "  sin cambios (la rotación es semanal)")
    held = {s: q * prices[s] / value for s, q in state["coins"].items()}
    print("  cartera: " + (", ".join(f"{s.replace('/USDT', '')} {w:.0%}"
                                     for s, w in sorted(held.items(), key=lambda x: -x[1]))
                           or "100 % en USDT"))


def main():
    p = argparse.ArgumentParser(description="Bot de cartera en paper trading")
    p.add_argument("--config", default="bot_config.json")
    p.add_argument("--state", default=STATE)
    p.add_argument("--capital", type=float, default=1000.0)
    p.add_argument("--loop", action="store_true", help="repetir cada día")
    p.add_argument("--synthetic", action="store_true", help="monedas inventadas (sin internet)")
    args = p.parse_args()

    cfg = load_config(args.config, args.synthetic)
    if not cfg.get("passes", False) and not args.synthetic:
        print("AVISO: la investigación dijo que esta estrategia NO cumple el criterio. "
              "Úsala solo para aprender, nunca con dinero real.")
    state = {"cash": args.capital, "coins": {}, "history": []}
    if os.path.exists(args.state):
        with open(args.state, encoding="utf-8") as f:
            state = json.load(f)

    while True:
        if args.synthetic:
            frames = universe.synthetic_universe()
        else:
            frames = universe.download(cfg["universe"], log=lambda *_: None)
        step(cfg, state, frames)
        with open(args.state, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        if not args.loop:
            break
        now = time.time()
        time.sleep(86_400 - now % 86_400 + 10 * 60)  # 00:10 UTC del día siguiente
        print(f"--- {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC ---", flush=True)


if __name__ == "__main__":
    main()
