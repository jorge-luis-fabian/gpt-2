"""Compara todas las estrategias en varios periodos con un solo comando.

Descarga los precios una vez por tipo de vela, calcula las señales con toda la
historia (así ninguna estrategia empieza "a ciegas") y mide cada periodo por
separado. Imprime una tabla y la guarda en comparacion.txt.

Ejemplos:
    python -m trading_bot.compare --symbol BTC/USDT
    python -m trading_bot.compare --synthetic
"""

import argparse

import pandas as pd

from . import config, data
from .backtest import simulate, summarize
from .strategy import STRATEGIES, describe, get_params, run_signals, warmup

# (tipo de vela, periodos en días)
PERIODS = [("4h", [365, 730]), ("1d", [365, 730, 1460])]


def passes(s):
    """Criterio fijado antes de ver resultados.

    Pasa si queda a menos de 10 puntos de comprar y mantener, o si reduce la
    peor caída en al menos un tercio sin perder más de la mitad del retorno.
    """
    bot, bh = s["retorno_estrategia"], s["retorno_comprar_y_mantener"]
    near = bot >= bh - 0.10
    safer = s["maxima_caida"] >= s["maxima_caida_comprar_y_mantener"] * 2 / 3
    keeps_return = bot >= bh / 2 if bh > 0 else bot >= bh
    return near or (safer and keeps_return)


def load(args, timeframe, days):
    step = data.timeframe_to_ms(timeframe)
    if args.synthetic:
        return data.synthetic_ohlcv(n=days * 86_400_000 // step, step_ms=step)
    return data.fetch_ohlcv(args.symbol, timeframe, days, args.exchange)


def main():
    p = argparse.ArgumentParser(description="Compara todas las estrategias")
    p.add_argument("--symbol", default=config.SYMBOL)
    p.add_argument("--exchange", default=config.EXCHANGE)
    p.add_argument("--capital", type=float, default=config.INITIAL_CAPITAL)
    p.add_argument("--fee", type=float, default=config.FEE_RATE)
    p.add_argument("--out", default="comparacion.txt")
    p.add_argument("--synthetic", action="store_true", help="usar precios inventados (sin internet)")
    args = p.parse_args()

    lines = []

    def out(text=""):
        print(text, flush=True)
        lines.append(text)

    source = "precios inventados" if args.synthetic else args.exchange
    out(f"Comparación de estrategias · {args.symbol} · {source} · comisión {args.fee:.2%}")
    params = {name: get_params(name) for name in STRATEGIES}
    verdicts = {}

    for timeframe, periods in PERIODS:
        step = data.timeframe_to_ms(timeframe)
        extra = max(warmup(p) for p in params.values()) * step // 86_400_000 + 2
        full = load(args, timeframe, max(periods) + extra)
        signals = {name: run_signals(full, name, params[name]) for name in STRATEGIES}

        for days in periods:
            cut = full.index[-1] - pd.Timedelta(days=days)
            out()
            results = {}
            for name in STRATEGIES:
                df, trades = simulate(signals[name][signals[name].index > cut], args.capital, args.fee)
                results[name] = summarize(df, trades, args.capital)
                verdicts.setdefault((name, timeframe), []).append(passes(results[name]))
            first = next(iter(results.values()))
            out(f"=== Velas de {timeframe} · últimos {days} días "
                f"({first['desde']:%Y-%m-%d} -> {first['hasta']:%Y-%m-%d}) ===")
            out(f"Comprar y mantener: {first['retorno_comprar_y_mantener']:+8.1%}"
                f"   peor caída {first['maxima_caida_comprar_y_mantener']:.1%}")
            out(f"{'Estrategia':<34}{'Bot':>9}{'Ops':>6}{'En mercado':>12}{'Peor caída':>12}")
            for name, s in results.items():
                out(f"{describe(name, params[name])['name']:<34}{s['retorno_estrategia']:>+9.1%}"
                    f"{s['operaciones_cerradas']:>6}{s['tiempo_en_mercado']:>12.0%}{s['maxima_caida']:>12.1%}")

    out()
    out("=== Veredicto (debe cumplir el criterio en todos los periodos) ===")
    for (name, timeframe), ok in verdicts.items():
        mark = "PASA" if all(ok) else "no pasa"
        out(f"{describe(name, params[name])['name']:<34} velas {timeframe:<3}  {mark}  ({sum(ok)}/{len(ok)} periodos)")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nResultados guardados en {args.out}")


if __name__ == "__main__":
    main()
