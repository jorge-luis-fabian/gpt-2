"""Backtest: simula una estrategia sobre datos históricos y muestra los resultados.

Ejemplos:
    python -m trading_bot.backtest --synthetic
    python -m trading_bot.backtest --symbol BTC/USDT --days 180
    python -m trading_bot.backtest --strategy donchian --timeframe 1d --days 1460
    python -m trading_bot.backtest --csv precios.csv
"""

import argparse

from . import config, data
from .strategy import STRATEGIES, describe, get_params, run_signals


def simulate(df, capital=config.INITIAL_CAPITAL, fee=config.FEE_RATE):
    """Recorre las velas una a una y ejecuta compras/ventas al precio de apertura.

    `df` debe tener ya la columna `position`. Devuelve (DataFrame con la curva
    de capital, lista de operaciones cerradas).
    """
    df = df.copy()
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


def run_backtest(df, strategy="sma", params=None,
                 capital=config.INITIAL_CAPITAL, fee=config.FEE_RATE):
    """Calcula las señales de la estrategia y simula las operaciones."""
    return simulate(run_signals(df, strategy, params), capital, fee)


def max_drawdown(series):
    peak = series.cummax()
    return ((series - peak) / peak).min()


def summarize(df, trades, capital=config.INITIAL_CAPITAL):
    final = df["equity"].iloc[-1]
    wins = sum(1 for t in trades if t["pnl"] > 0)
    return {
        "desde": df.index[0],
        "hasta": df.index[-1],
        "velas": len(df),
        "capital_inicial": capital,
        "capital_final": final,
        "retorno_estrategia": final / capital - 1,
        "retorno_comprar_y_mantener": df["close"].iloc[-1] / df["close"].iloc[0] - 1,
        "operaciones_cerradas": len(trades),
        "porcentaje_aciertos": wins / len(trades) if trades else 0.0,
        "maxima_caida": max_drawdown(df["equity"]),
        "maxima_caida_comprar_y_mantener": max_drawdown(df["close"]),
        "tiempo_en_mercado": df["position"].mean(),
        "posicion_abierta_al_final": bool(df["position"].iloc[-1]),
    }


def print_summary(s, name=""):
    print("=" * 50)
    if name:
        print(f"Estrategia:                {name}")
    print(f"Periodo:                   {s['desde']:%Y-%m-%d} -> {s['hasta']:%Y-%m-%d} ({s['velas']} velas)")
    print(f"Capital inicial:           {s['capital_inicial']:,.2f} USDT")
    print(f"Capital final:             {s['capital_final']:,.2f} USDT")
    print(f"Retorno de la estrategia:  {s['retorno_estrategia']:+.2%}")
    print(f"Retorno comprar y mantener:{s['retorno_comprar_y_mantener']:+.2%}")
    print(f"Operaciones cerradas:      {s['operaciones_cerradas']}")
    print(f"% de operaciones ganadoras:{s['porcentaje_aciertos']:.1%}")
    print(f"Tiempo dentro del mercado: {s['tiempo_en_mercado']:.0%}")
    print(f"Máxima caída (drawdown):   {s['maxima_caida']:.2%}")
    print(f"Máxima caída comprar y m.: {s['maxima_caida_comprar_y_mantener']:.2%}")
    print(f"Posición abierta al final: {'sí' if s['posicion_abierta_al_final'] else 'no'}")
    print("=" * 50)


def add_common_args(p, days=180):
    """Opciones compartidas por backtest, report y paper_trade."""
    p.add_argument("--strategy", choices=sorted(STRATEGIES), default="sma")
    p.add_argument("--symbol", default=config.SYMBOL)
    p.add_argument("--timeframe", default=config.TIMEFRAME)
    p.add_argument("--exchange", default=config.EXCHANGE)
    p.add_argument("--days", type=int, default=days)
    p.add_argument("--fast", type=int, help=f"solo sma (por defecto {config.FAST_PERIOD})")
    p.add_argument("--slow", type=int, help=f"solo sma (por defecto {config.SLOW_PERIOD})")
    p.add_argument("--capital", type=float, default=config.INITIAL_CAPITAL)
    p.add_argument("--fee", type=float, default=config.FEE_RATE)
    p.add_argument("--csv", help="usar un CSV en lugar de descargar datos")
    p.add_argument("--synthetic", action="store_true", help="usar precios inventados (sin internet)")


def params_from_args(args):
    return get_params(args.strategy, fast=args.fast, slow=args.slow)


def load_data(args):
    if args.synthetic:
        step = data.timeframe_to_ms(args.timeframe)
        return data.synthetic_ohlcv(n=args.days * 86_400_000 // step, step_ms=step)
    if args.csv:
        return data.load_csv(args.csv)
    return data.fetch_ohlcv(args.symbol, args.timeframe, args.days, args.exchange)


def main():
    p = argparse.ArgumentParser(description="Backtest de una estrategia")
    add_common_args(p)
    args = p.parse_args()

    params = params_from_args(args)
    df = load_data(args)
    result, trades = run_backtest(df, args.strategy, params, args.capital, args.fee)
    print_summary(summarize(result, trades, args.capital), describe(args.strategy, params)["name"])


if __name__ == "__main__":
    main()
