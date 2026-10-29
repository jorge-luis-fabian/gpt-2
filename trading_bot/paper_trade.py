"""Paper trading: ejecuta la estrategia en "vivo" con dinero ficticio.

Cada vez que cierra una vela descarga los precios, calcula la señal y simula
la compra o venta. El saldo y las operaciones se guardan en un JSON, así que
puedes parar y volver a arrancar sin perder el estado.

Ejemplos:
    python -m trading_bot.paper_trade                      # corre indefinidamente
    python -m trading_bot.paper_trade --synthetic --iterations 3
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone

from . import config, data
from .strategy import generate_signals


def load_state(path, capital):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"cash": capital, "coins": 0.0, "entry_value": None, "trades": []}


def save_state(path, state):
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def step(state, df, fast, slow, fee):
    """Aplica la señal de la última vela cerrada al estado. Devuelve un mensaje."""
    last = generate_signals(df, fast, slow).iloc[-1]
    price = last["close"]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if last["signal"] == 1 and state["coins"] == 0:
        state["entry_value"] = state["cash"]
        state["coins"] = state["cash"] * (1 - fee) / price
        state["cash"] = 0.0
        state["trades"].append({"time": now, "side": "buy", "price": price})
        action = f"COMPRA a {price:,.2f}"
    elif last["signal"] == 0 and state["coins"] > 0:
        state["cash"] = state["coins"] * price * (1 - fee)
        state["coins"] = 0.0
        pnl = state["cash"] - state["entry_value"]
        state["trades"].append({"time": now, "side": "sell", "price": price, "pnl": pnl})
        action = f"VENTA a {price:,.2f} (resultado {pnl:+,.2f} USDT)"
    else:
        action = "sin cambios"

    equity = state["cash"] + state["coins"] * price
    return (f"[{now}] precio {price:,.2f} | media rápida {last['sma_fast']:,.2f} | "
            f"media lenta {last['sma_slow']:,.2f} | {action} | capital {equity:,.2f} USDT")


def main():
    p = argparse.ArgumentParser(description="Paper trading de cruce de medias móviles")
    p.add_argument("--symbol", default=config.SYMBOL)
    p.add_argument("--timeframe", default=config.TIMEFRAME)
    p.add_argument("--exchange", default=config.EXCHANGE)
    p.add_argument("--fast", type=int, default=config.FAST_PERIOD)
    p.add_argument("--slow", type=int, default=config.SLOW_PERIOD)
    p.add_argument("--capital", type=float, default=config.INITIAL_CAPITAL)
    p.add_argument("--fee", type=float, default=config.FEE_RATE)
    p.add_argument("--state", default=config.PAPER_STATE_FILE)
    p.add_argument("--iterations", type=int, default=0, help="0 = sin límite")
    p.add_argument("--synthetic", action="store_true",
                   help="precios inventados y sin esperar entre velas (para probar)")
    args = p.parse_args()

    state = load_state(args.state, args.capital)
    days = max(2, args.slow * data.timeframe_to_ms(args.timeframe) * 3 // 86_400_000 + 1)
    i = 0
    while args.iterations == 0 or i < args.iterations:
        if args.synthetic:
            df = data.synthetic_ohlcv(n=args.slow * 3 + i)
        else:
            df = data.fetch_ohlcv(args.symbol, args.timeframe, days, args.exchange)
        print(step(state, df, args.fast, args.slow, args.fee), flush=True)
        save_state(args.state, state)
        i += 1
        if not args.synthetic and (args.iterations == 0 or i < args.iterations):
            # esperar al cierre de la siguiente vela (+5 s de margen)
            period = data.timeframe_to_ms(args.timeframe) / 1000
            time.sleep(period - time.time() % period + 5)


if __name__ == "__main__":
    main()
