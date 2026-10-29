"""Bot de compras periódicas (DCA): compra una cantidad fija de BTC cada semana.

Es lo que mejor respaldan las pruebas: ninguna estrategia de entrar y salir le
ganó a mantener BTC, así que el bot solo compra de forma constante, sin
intentar adivinar el momento.

Modos:
    python -m trading_bot.dca                         # simulación con precios reales desde 2018
    python -m trading_bot.dca --bot                   # una revisión del bot con dinero ficticio
    python -m trading_bot.dca --bot --loop            # revisa cada día y compra cuando toca
    python -m trading_bot.dca --bot --loop --testnet  # órdenes reales en la Testnet de Binance

Para la Testnet crea un archivo .env junto a esta carpeta con:
    BINANCE_TESTNET_KEY=...
    BINANCE_TESTNET_SECRET=...
(las claves se crean en https://testnet.binance.vision; no son las de tu cuenta real).

Avisos por Telegram (compras, errores y prueba superada): ver notify.py.
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone

import pandas as pd

from . import notify, universe

FEE = 0.001
STATE = "paper_dca.json"


# ---------------------------------------------------------------- simulación

def simulate(close, amount, every, fee=FEE):
    """Compra `amount` USDT de BTC cada `every` días. Devuelve el día a día."""
    buy = pd.Series(False, index=close.index)
    buy.iloc[::every] = True
    invested = (buy * amount).cumsum()
    coins = (buy * amount * (1 - fee) / close).cumsum()
    value = coins * close
    return pd.DataFrame({"invertido": invested, "valor": value, "btc": coins})


def lump_sum(close, total, fee=FEE):
    coins = total * (1 - fee) / close.iloc[0]
    return pd.DataFrame({"invertido": total, "valor": coins * close, "btc": coins}, index=close.index)


def summary(df):
    ratio = df["valor"] / df["invertido"]
    last = df.iloc[-1]
    return {
        "invertido": last["invertido"],
        "valor": last["valor"],
        "ganancia": last["valor"] / last["invertido"] - 1,
        "peor": ratio.min() - 1,  # el peor momento: cuánto llegó a estar por debajo de lo invertido
        "peor_dia": ratio.idxmin(),
        "costo_medio": last["invertido"] / last["btc"],
    }


def run_simulation(close, amount, every, start):
    close = close[close.index >= pd.Timestamp(start, tz="UTC")]
    lines = []

    def out(text=""):
        print(text, flush=True)
        lines.append(text)

    weekly = simulate(close, amount, every)
    total = weekly["invertido"].iloc[-1]
    once = lump_sum(close, total)
    d, l = summary(weekly), summary(once)

    out(f"SIMULACIÓN DCA BTC · {amount:,.0f} USDT cada {every} días · comisión {FEE:.1%}")
    out(f"Periodo: {close.index[0]:%Y-%m-%d} -> {close.index[-1]:%Y-%m-%d}")
    out()
    out(f"{'':<34}{'DCA':>14}{'Todo de golpe':>16}")
    out(f"{'Total invertido':<34}{d['invertido']:>14,.0f}{l['invertido']:>16,.0f}")
    out(f"{'Valor hoy':<34}{d['valor']:>14,.0f}{l['valor']:>16,.0f}")
    out(f"{'Ganancia':<34}{d['ganancia']:>+14.0%}{l['ganancia']:>+16.0%}")
    out(f"{'Precio medio de compra':<34}{d['costo_medio']:>14,.0f}{l['costo_medio']:>16,.0f}")
    out(f"{'Peor momento vs lo invertido':<34}{d['peor']:>+14.0%}{l['peor']:>+16.0%}")
    out(f"{'  fecha del peor momento':<34}{d['peor_dia'].strftime('%Y-%m'):>14}{l['peor_dia'].strftime('%Y-%m'):>16}")

    out()
    out("Si hubieras empezado el DCA en cada año y lo mantuvieras hasta hoy:")
    out(f"{'Inicio':<8}{'Invertido':>12}{'Valor hoy':>12}{'Ganancia':>10}{'Peor momento':>14}")
    for year in range(close.index[0].year, close.index[-1].year + 1):
        part = close[close.index >= pd.Timestamp(f"{year}-01-01", tz="UTC")]
        if len(part) < 30:
            continue
        s = summary(simulate(part, amount, every))
        out(f"{year:<8}{s['invertido']:>12,.0f}{s['valor']:>12,.0f}{s['ganancia']:>+10.0%}{s['peor']:>+14.0%}")

    with open("dca.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\nGuardado en dca.txt")


# ---------------------------------------------------------------- bot

def testnet_exchange():
    import ccxt

    notify.load_env()
    key, secret = os.environ.get("BINANCE_TESTNET_KEY"), os.environ.get("BINANCE_TESTNET_SECRET")
    if not key or not secret:
        raise SystemExit("Faltan BINANCE_TESTNET_KEY y BINANCE_TESTNET_SECRET en el archivo .env")
    exchange = ccxt.binance({"apiKey": key, "secret": secret, "enableRateLimit": True})
    exchange.set_sandbox_mode(True)
    return exchange


def bot_step(state, price, amount, every, today, exchange=None):
    """Compra si toca. Devuelve el mensaje del día."""
    last = state.get("last_buy")
    due = last is None or (pd.Timestamp(today) - pd.Timestamp(last)).days >= every
    if due:
        if exchange is not None:  # orden real en la Testnet
            order = exchange.create_market_buy_order_with_cost("BTC/USDT", amount)
            qty = float(order["filled"])
            price = float(order["average"] or price)
            spent = float(order["cost"])
        else:
            qty = amount * (1 - FEE) / price
            spent = amount
        state["btc"] += qty
        state["invertido"] += spent
        state["last_buy"] = today
        state["compras"].append({"dia": today, "precio": price, "btc": qty, "usdt": spent})
    value = state["btc"] * price
    gain = value / state["invertido"] - 1 if state["invertido"] else 0.0
    action = f"COMPRA {amount:,.0f} USDT a {price:,.2f}" if due else \
        f"sin compra (próxima en {every - (pd.Timestamp(today) - pd.Timestamp(last)).days} días)"
    return (f"[{today}] {action} | BTC acumulado {state['btc']:.6f} | invertido "
            f"{state['invertido']:,.2f} | valor {value:,.2f} USDT ({gain:+.1%})")


def run_bot(args):
    folder = os.getcwd()
    mode = "TESTNET de Binance (dinero de prueba)" if args.testnet else "Dinero ficticio"
    state_file = "testnet_dca.json" if args.testnet else args.state
    state = {"btc": 0.0, "invertido": 0.0, "last_buy": None, "compras": []}
    if os.path.exists(state_file):
        with open(state_file, encoding="utf-8") as f:
            state = json.load(f)
    print(f"{mode} · {args.amount:,.0f} USDT de BTC cada {args.every} días", flush=True)
    while True:
        try:
            exchange = testnet_exchange() if args.testnet else None
            if args.synthetic:
                close = universe.synthetic_universe()["BTC/USDT"]["close"]
                price, today = float(close.iloc[-1]), close.index[-1].strftime("%Y-%m-%d")
            else:
                from . import data
                ticker = (exchange or data.make_exchange()).fetch_ticker("BTC/USDT")
                price = float(ticker["last"])
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            buys = len(state["compras"])
            message = bot_step(state, price, args.amount, args.every, today, exchange)
            print(message, flush=True)
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            if len(state["compras"]) > buys:
                notify.send(f"🟢 Bot DCA · {mode}\n{message}\n📁 {folder}")
            if len(state["compras"]) >= args.test_buys and not state.get("prueba_superada"):
                state["prueba_superada"] = True
                with open(state_file, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2)
                notify.send(f"🎉 Prueba superada: {args.test_buys} compras sin errores ({mode}).\n"
                            f"Invertido {state['invertido']:,.2f} USDT · BTC {state['btc']:.6f}\n📁 {folder}")
                print(f"Prueba superada: {args.test_buys} compras sin errores.", flush=True)
                notify.send_code("📦 Código completo del bot DCA (prueba superada)")
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            print(f"ERROR: {error}", flush=True)
            notify.send(f"❌ El bot DCA falló ({mode})\n{error[:500]}\n📁 {folder}")
            if not args.loop:
                raise SystemExit(1)
        if not args.loop:
            break
        time.sleep(86_400 - time.time() % 86_400 + 10 * 60)  # 00:10 UTC del día siguiente


def main():
    p = argparse.ArgumentParser(description="Bot de compras periódicas de BTC (DCA)")
    p.add_argument("--amount", type=float, default=50.0, help="USDT por compra")
    p.add_argument("--every", type=int, default=7, help="días entre compras")
    p.add_argument("--start", default="2018-01-01", help="inicio de la simulación")
    p.add_argument("--bot", action="store_true", help="ejecutar el bot en lugar de la simulación")
    p.add_argument("--loop", action="store_true", help="el bot revisa cada día")
    p.add_argument("--testnet", action="store_true", help="órdenes en la Testnet de Binance")
    p.add_argument("--state", default=STATE)
    p.add_argument("--test-buys", type=int, default=3, help="compras para dar la prueba por superada")
    p.add_argument("--synthetic", action="store_true", help="precios inventados (sin internet)")
    args = p.parse_args()

    if args.bot:
        run_bot(args)
        return
    if args.synthetic:
        close = universe.synthetic_universe()["BTC/USDT"]["close"]
    else:
        frames = universe.download(["BTC/USDT"])
        close = frames["BTC/USDT"]["close"]
    run_simulation(close, args.amount, args.every, args.start)


if __name__ == "__main__":
    main()
