"""Backtest: simula la estrategia sobre datos históricos y muestra los resultados.

Ejemplos:
    python -m trading_bot.backtest --synthetic
    python -m trading_bot.backtest --symbol BTC/USDT --days 180
    python -m trading_bot.backtest --csv precios.csv
"""

import argparse

from . import config, data
from .strategy import generate_signals


def run_backtest(df, fast=config.FAST_PERIOD, slow=config.SLOW_PERIOD,
                 capital=config.INITIAL_CAPITAL, fee=config.FEE_RATE):
    """Recorre las velas una a una y ejecuta compras/ventas al precio de apertura.

    Devuelve (curva de capital, lista de operaciones cerradas).
    """
    df = generate_signals(df, fast, slow)
    cash, coins = capital, 0.0
    entry_value = None
    trades, equity = [], []

    for ts, row in df.iterrows():
        if row["position"] == 1 and coins == 0:      # comprar con todo el saldo
            entry_value = cash
            coins = cash * (1 - fee) / row["open"]
            cash = 0.0
        elif row["position"] == 0 and coins > 0:     # vender todo
            cash = coins * row["open"] * (1 - fee)
            coins = 0.0
            trades.append({"exit_time": ts, "pnl": cash - entry_value,
                           "return": cash / entry_value - 1})
        equity.append(cash + coins * row["close"])

    df["equity"] = equity
    return df, trades


def summarize(df, trades, capital=config.INITIAL_CAPITAL):
    final = df["equity"].iloc[-1]
    peak = df["equity"].cummax()
    max_drawdown = ((df["equity"] - peak) / peak).min()
    buy_hold = df["close"].iloc[-1] / df["close"].iloc[0] - 1
    wins = sum(1 for t in trades if t["pnl"] > 0)
    return {
        "desde": df.index[0],
        "hasta": df.index[-1],
        "velas": len(df),
        "capital_inicial": capital,
        "capital_final": final,
        "retorno_estrategia": final / capital - 1,
        "retorno_comprar_y_mantener": buy_hold,
        "operaciones_cerradas": len(trades),
        "porcentaje_aciertos": wins / len(trades) if trades else 0.0,
        "maxima_caida": max_drawdown,
        "posicion_abierta_al_final": bool(df["position"].iloc[-1]),
    }


def print_summary(s):
    print("=" * 50)
    print(f"Periodo:                   {s['desde']:%Y-%m-%d} -> {s['hasta']:%Y-%m-%d} ({s['velas']} velas)")
    print(f"Capital inicial:           {s['capital_inicial']:,.2f} USDT")
    print(f"Capital final:             {s['capital_final']:,.2f} USDT")
    print(f"Retorno de la estrategia:  {s['retorno_estrategia']:+.2%}")
    print(f"Retorno comprar y mantener:{s['retorno_comprar_y_mantener']:+.2%}")
    print(f"Operaciones cerradas:      {s['operaciones_cerradas']}")
    print(f"% de operaciones ganadoras:{s['porcentaje_aciertos']:.1%}")
    print(f"Máxima caída (drawdown):   {s['maxima_caida']:.2%}")
    print(f"Posición abierta al final: {'sí' if s['posicion_abierta_al_final'] else 'no'}")
    print("=" * 50)


def load_data(args):
    if args.synthetic:
        return data.synthetic_ohlcv()
    if args.csv:
        return data.load_csv(args.csv)
    return data.fetch_ohlcv(args.symbol, args.timeframe, args.days, args.exchange)


def main():
    p = argparse.ArgumentParser(description="Backtest de cruce de medias móviles")
    p.add_argument("--symbol", default=config.SYMBOL)
    p.add_argument("--timeframe", default=config.TIMEFRAME)
    p.add_argument("--exchange", default=config.EXCHANGE)
    p.add_argument("--days", type=int, default=180)
    p.add_argument("--fast", type=int, default=config.FAST_PERIOD)
    p.add_argument("--slow", type=int, default=config.SLOW_PERIOD)
    p.add_argument("--capital", type=float, default=config.INITIAL_CAPITAL)
    p.add_argument("--fee", type=float, default=config.FEE_RATE)
    p.add_argument("--csv", help="usar un CSV en lugar de descargar datos")
    p.add_argument("--synthetic", action="store_true", help="usar precios inventados (sin internet)")
    args = p.parse_args()

    df = load_data(args)
    result, trades = run_backtest(df, args.fast, args.slow, args.capital, args.fee)
    print_summary(summarize(result, trades, args.capital))


if __name__ == "__main__":
    main()
