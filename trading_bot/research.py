"""Investigación completa: qué monedas y qué estrategia usar para el bot de cartera.

Pasos:
1. Descarga la historia diaria de ~30 monedas (incluye varias que se hundieron).
2. Analiza cada moneda: historia, liquidez, volatilidad y relación con BTC.
3. Prueba 14 combinaciones de estrategias de cartera más 2 referencias.
4. Elige UNA con los datos hasta 2022 (entrenamiento) y la juzga con 2023 en
   adelante (prueba), años que no se usaron para elegirla.
5. Guarda el bot elegido en bot_config.json, los resultados en investigacion.txt
   y un reporte con gráficos en investigacion.html.

Ejemplos:
    python -m trading_bot.research
    python -m trading_bot.research --synthetic
"""

import argparse
import json

import numpy as np
import pandas as pd

from . import portfolio as pf
from . import universe

CRITERIO = ("El bot sirve si en el periodo de prueba (años no usados para elegirlo) tiene un Sharpe "
            "igual o mejor que comprar y mantener BTC, una peor caída al menos un tercio menor y "
            "un retorno anual positivo.")


def pct(x, sign=True):
    return f"{x:+.1%}" if sign else f"{x:.1%}"


def asset_table(closes, volume, elig, split):
    """Una fila por moneda con datos que no dependen de ninguna estrategia."""
    rets = closes.pct_change(fill_method=None)
    btc = rets[pf.REGIME]
    rows = []
    for s in closes.columns:
        c = closes[s].dropna()
        r = rets[s].dropna()
        train = c[c.index < split]
        test = c[c.index >= split]
        rows.append({
            "moneda": s.replace("/USDT", ""),
            "desde": c.index[0],
            "hasta": c.index[-1],
            "volumen": volume[s].tail(90).mean(),
            "volatilidad": r.std() * np.sqrt(365),
            "corr_btc": r.corr(btc),
            "entrenamiento": train.iloc[-1] / train.iloc[0] - 1 if len(train) > 1 else np.nan,
            "prueba": test.iloc[-1] / test.iloc[0] - 1 if len(test) > 1 else np.nan,
            "operable": elig[s].mean(),
        })
    return pd.DataFrame(rows).sort_values("volumen", ascending=False)


def holdings(closes, real, start):
    """Cuánto tiempo tuvo el bot cada moneda y cuánto aportó a la ganancia."""
    rets = (closes / closes.shift(1) - 1).fillna(0)
    contrib = (real.shift(1).fillna(0) * rets).loc[start:]
    held = (real.loc[start:] > 0).mean()
    table = pd.DataFrame({"tiempo": held, "aporte": contrib.sum()})
    table = table[table["tiempo"] > 0].sort_values("aporte", ascending=False)
    table.index = [s.replace("/USDT", "") for s in table.index]
    return table


def yearly(equity):
    e = equity.resample("YE").last()
    first = equity.iloc[0]
    return e.pct_change().fillna(e.iloc[0] / first - 1)


def run_all(closes, elig, split, start):
    results = []
    for name, params in pf.BENCHMARKS + pf.GRID:
        w = pf.weights(name, params, closes, elig)
        equity, real, turnover = pf.run(closes, w)
        equity = equity.loc[start:]
        results.append({
            "name": name, "params": params, "label": pf.label(name, params),
            "benchmark": (name, params) in pf.BENCHMARKS,
            "equity": equity, "real": real,
            "train": pf.metrics(equity[equity.index < split], real, turnover),
            "test": pf.metrics(equity[equity.index >= split], real, turnover),
            "full": pf.metrics(equity, real, turnover),
        })
    return results


def verdict(sel, btc):
    t, b = sel["test"], btc["test"]
    checks = {
        "Sharpe igual o mejor que BTC": t["sharpe"] >= b["sharpe"],
        "peor caída al menos 1/3 menor que BTC": t["caida"] >= b["caida"] * 2 / 3,
        "retorno anual positivo": t["anual"] > 0,
    }
    return all(checks.values()), checks


def main():
    p = argparse.ArgumentParser(description="Investigación de monedas y estrategias para el bot de cartera")
    p.add_argument("--split", default="2023-01-01", help="inicio del periodo de prueba")
    p.add_argument("--exchange", default="binance")
    p.add_argument("--refresh", action="store_true", help="volver a descargar aunque haya caché")
    p.add_argument("--synthetic", action="store_true", help="usar monedas inventadas (sin internet)")
    p.add_argument("--out", default="investigacion")
    args = p.parse_args()

    lines = []

    def out(text=""):
        print(text, flush=True)
        lines.append(text)

    split = pd.Timestamp(args.split, tz="UTC")
    if args.synthetic:
        frames = universe.synthetic_universe()
        source = "monedas inventadas"
    else:
        print("Descargando historia diaria (la primera vez tarda unos minutos)...")
        frames = universe.download(exchange_id=args.exchange, refresh=args.refresh)
        source = args.exchange
    if pf.REGIME not in frames:
        raise SystemExit("No se pudo descargar BTC/USDT; sin él no se puede hacer la investigación.")

    closes, volume = universe.panel(frames)
    elig = pf.eligible(closes, volume)
    start = elig[pf.REGIME].idxmax()  # todas las estrategias empiezan el mismo día

    out(f"INVESTIGACIÓN DEL BOT DE CARTERA · {source} · velas diarias")
    out(f"Monedas descargadas: {len(frames)} · datos {closes.index[0]:%Y-%m-%d} -> {closes.index[-1]:%Y-%m-%d}")
    out(f"Entrenamiento: {start:%Y-%m-%d} -> {split - pd.Timedelta(days=1):%Y-%m-%d} · "
        f"Prueba: {split:%Y-%m-%d} -> {closes.index[-1]:%Y-%m-%d}")
    out(f"Costos: {pf.COST:.2%} por operación (comisión + deslizamiento)")

    # 1. monedas
    assets = asset_table(closes, volume, elig, split)
    out()
    out("=== 1. Monedas (ordenadas por volumen de los últimos 90 días) ===")
    out(f"{'Moneda':<7}{'Desde':>11}{'Hasta':>11}{'Vol. diario':>13}{'Volat.':>8}{'Corr BTC':>9}"
        f"{'Entren.':>10}{'Prueba':>10}{'Operable':>9}")
    for _, a in assets.iterrows():
        out(f"{a['moneda']:<7}{a['desde']:%Y-%m-%d} {a['hasta']:%Y-%m-%d}"
            f"{a['volumen'] / 1e6:>10,.0f} M{a['volatilidad']:>8.0%}{a['corr_btc']:>9.2f}"
            f"{a['entrenamiento']:>+10.0%}{a['prueba']:>+10.0%}{a['operable']:>9.0%}")

    # 2. estrategias
    results = run_all(closes, elig, split, start)
    btc = next(r for r in results if r["name"] == "hold_btc")
    candidates = [r for r in results if not r["benchmark"]]
    sel = max(candidates, key=lambda r: r["train"]["sharpe"])
    test_rank = sorted(candidates, key=lambda r: -r["test"]["sharpe"]).index(sel) + 1
    beat = sum(r["test"]["sharpe"] >= btc["test"]["sharpe"] for r in candidates)

    out()
    out("=== 2. Estrategias (Sharpe = ganancia por unidad de riesgo; más alto es mejor) ===")
    out(f"{'':<36}{'---- Entrenamiento ----':>26}{'-------- Prueba --------':>34}")
    out(f"{'Estrategia':<36}{'Anual':>9}{'Sharpe':>8}{'Caída':>9}{'Anual':>11}{'Sharpe':>8}"
        f"{'Caída':>9}{'Invert.':>9}")
    for r in results:
        tr, te = r["train"], r["test"]
        mark = " <- elegida" if r is sel else ""
        out(f"{r['label']:<36}{tr['anual']:>+9.0%}{tr['sharpe']:>8.2f}{tr['caida']:>9.0%}"
            f"{te['anual']:>+11.0%}{te['sharpe']:>8.2f}{te['caida']:>9.0%}{te['invertido']:>9.0%}{mark}")

    # 3. elegida
    ok, checks = verdict(sel, btc)
    out()
    out(f"=== 3. Estrategia elegida con el entrenamiento: {sel['label']} ===")
    out(f"En la prueba quedó en el puesto {test_rank} de {len(candidates)}; "
        f"{beat} de {len(candidates)} estrategias igualaron o superaron el Sharpe de BTC.")
    out(f"{'':<26}{'Bot':>10}{'BTC':>10}")
    for key, name in [("retorno", "Retorno total prueba"), ("anual", "Retorno anual"),
                      ("caida", "Peor caída"), ("sharpe", "Sharpe")]:
        fmt = (lambda x: f"{x:.2f}") if key == "sharpe" else (lambda x: f"{x:+.0%}")
        out(f"{name:<26}{fmt(sel['test'][key]):>10}{fmt(btc['test'][key]):>10}")
    out()
    out("Año a año (bot vs BTC):")
    yb, yt = yearly(sel["equity"]), yearly(btc["equity"])
    for d in yb.index:
        out(f"  {d.year}: {yb[d]:>+7.0%}   {yt[d]:>+7.0%}")

    hold = holdings(closes, sel["real"], split)
    out()
    out("Monedas que usó el bot en la prueba (tiempo en cartera y aporte a la ganancia):")
    for coin, h in hold.head(15).iterrows():
        out(f"  {coin:<6} {h['tiempo']:>5.0%} del tiempo   aporte {h['aporte']:>+7.1%}")

    now = sel["real"].iloc[-1]
    now = now[now > 0].sort_values(ascending=False)
    out()
    out(f"Cartera que tendría hoy ({closes.index[-1]:%Y-%m-%d}): "
        + (", ".join(f"{s.replace('/USDT', '')} {w:.0%}" for s, w in now.items()) or "100 % en USDT"))

    out()
    out("=== 4. Veredicto ===")
    out(CRITERIO)
    for text, passed in checks.items():
        out(f"  [{'sí' if passed else 'no'}] {text}")
    out("RESULTADO: " + ("EL BOT SIRVE con este criterio. Siguiente paso: paper trading."
                         if ok else "EL BOT NO SIRVE con este criterio. No usar con dinero real."))

    config = {
        "strategy": sel["name"], "params": sel["params"], "label": sel["label"],
        "universe": list(closes.columns), "split": args.split, "passes": ok,
        "test": {k: float(v) for k, v in sel["test"].items()},
        "btc_test": {k: float(v) for k, v in btc["test"].items()},
    }
    if not args.synthetic:
        with open("bot_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    with open(args.out + ".txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    from .research_report import write_report
    write_report(args.out + ".html", source, results, sel, btc, assets, hold, split, ok, checks, CRITERIO)
    print(f"\nGuardado: {args.out}.txt, {args.out}.html" + ("" if args.synthetic else ", bot_config.json"))


if __name__ == "__main__":
    main()
