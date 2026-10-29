"""Paper trading: ejecuta la estrategia en "vivo" con dinero ficticio.

Cada vez que cierra una vela descarga los precios, calcula la señal y simula
la compra o venta. El saldo y las operaciones se guardan en un JSON, así que
puedes parar y volver a arrancar sin perder el estado.

Ejemplos:
    python -m trading_bot.paper_trade                      # corre indefinidamente
    python -m trading_bot.paper_trade --strategy donchian --timeframe 1d
    python -m trading_bot.paper_trade --synthetic --iterations 3
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone

from . import config, data
from .backtest import add_common_args, params_from_args
from .strategy import describe, run_signals, warmup


def load_state(path, capital):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"cash": capital, "coins": 0.0, "entry_value": None, "trades": []}


def save_state(path, state):
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def step(state, df, strategy, params, fee):
    """Aplica la señal de la última vela cerrada al estado. Devuelve un mensaje."""
    last = run_signals(df, strategy, params).iloc[-1]
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
    info = describe(strategy, params)
    lines = f"{info['line1']} {last['line1']:,.2f}"
    if info["line2"]:
        lines += f" | {info['line2']} {last['line2']:,.2f}"
    if "rsi" in last:
        lines += f" | RSI {last['rsi']:.1f}"
    return f"[{now}] precio {price:,.2f} | {lines} | {action} | capital {equity:,.2f} USDT"


def main():
    p = argparse.ArgumentParser(description="Paper trading con dinero ficticio")
    add_common_args(p)
    p.add_argument("--state", help="archivo de estado (por defecto paper_<estrategia>_<velas>.json)")
    p.add_argument("--iterations", type=int, default=0, help="0 = sin límite")
    args = p.parse_args()

    params = params_from_args(args)
    print(f"Paper trading: {describe(args.strategy, params)['name']}, velas de {args.timeframe}", flush=True)
    state_file = args.state or config.PAPER_STATE_FILE.format(strategy=args.strategy, timeframe=args.timeframe)
    state = load_state(state_file, args.capital)
    candles = warmup(params) * 3
    step_ms = data.timeframe_to_ms(args.timeframe)
    days = max(2, candles * step_ms // 86_400_000 + 1)
    i = 0
    while args.iterations == 0 or i < args.iterations:
        if args.synthetic:  # precios inventados y sin esperar entre velas (para probar)
            df = data.synthetic_ohlcv(n=candles + i, step_ms=step_ms)
        else:
            df = data.fetch_ohlcv(args.symbol, args.timeframe, days, args.exchange)
        print(step(state, df, args.strategy, params, args.fee), flush=True)
        save_state(state_file, state)
        i += 1
        if not args.synthetic and (args.iterations == 0 or i < args.iterations):
            # esperar al cierre de la siguiente vela (+5 s de margen)
            period = data.timeframe_to_ms(args.timeframe) / 1000
            time.sleep(period - time.time() % period + 5)


if __name__ == "__main__":
    main()
