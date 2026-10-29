"""Reporte visual del backtest: genera una página HTML con gráficos.

Muestra el precio, las dos medias, dónde compró y vendió el bot, y cómo
evolucionó el capital frente a "comprar y mantener".

Ejemplos:
    python -m trading_bot.report --synthetic --out reporte.html
    python -m trading_bot.report --symbol BTC/USDT --days 180 --out reporte.html
"""

import argparse
import html
import json

from . import config
from .backtest import load_data, run_backtest, summarize

CHART_JS = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"


def trade_list(df):
    """Reconstruye compras y ventas a partir de los cambios de `position`."""
    trades, entry = [], None
    prev = 0
    for ts, row in df.iterrows():
        pos = int(row["position"])
        if pos == 1 and prev == 0:
            entry = (ts, row["open"])
        elif pos == 0 and prev == 1 and entry:
            trades.append({"entrada": entry[0], "precio_entrada": entry[1],
                           "salida": ts, "precio_salida": row["open"]})
            entry = None
        prev = pos
    return trades, entry


def _series(s):
    return [None if v != v else round(float(v), 2) for v in s]  # NaN -> null


def build_payload(df, trades, open_trade, capital):
    labels = [ts.strftime("%Y-%m-%d %H:%M") for ts in df.index]
    buys = [None] * len(df)
    sells = [None] * len(df)
    pos = {ts: i for i, ts in enumerate(df.index)}
    for t in trades:
        buys[pos[t["entrada"]]] = round(t["precio_entrada"], 2)
        sells[pos[t["salida"]]] = round(t["precio_salida"], 2)
    if open_trade:
        buys[pos[open_trade[0]]] = round(open_trade[1], 2)
    buy_hold = capital * df["close"] / df["open"].iloc[0]
    return {
        "labels": labels,
        "close": _series(df["close"]),
        "fast": _series(df["sma_fast"]),
        "slow": _series(df["sma_slow"]),
        "buys": buys,
        "sells": sells,
        "equity": _series(df["equity"]),
        "buyHold": _series(buy_hold),
    }


def _pct(x):
    return f"{x:+.2%}".replace(".", ",")


def _money(x):
    return f"{x:,.2f}".replace(",", " ").replace(".", ",")


def render_html(df, trades, open_trade, summary, meta, full=True):
    payload = build_payload(df, trades, open_trade, summary["capital_inicial"])
    beat = summary["retorno_estrategia"] - summary["retorno_comprar_y_mantener"]
    rows = []
    for i, t in enumerate(trades, 1):
        r = t["precio_salida"] / t["precio_entrada"] * (1 - meta["fee"]) ** 2 - 1
        rows.append(
            f'<tr><td>{i}</td><td>{t["entrada"]:%d/%m %H:%M}</td><td>{_money(t["precio_entrada"])}</td>'
            f'<td>{t["salida"]:%d/%m %H:%M}</td><td>{_money(t["precio_salida"])}</td>'
            f'<td class="{"pos" if r > 0 else "neg"}">{_pct(r)}</td></tr>')
    if open_trade:
        rows.append(f'<tr><td>{len(trades) + 1}</td><td>{open_trade[0]:%d/%m %H:%M}</td>'
                    f'<td>{_money(open_trade[1])}</td><td colspan="3">abierta</td></tr>')
    notice = ""
    if meta["synthetic"]:
        notice = ('<p class="notice"><strong>Precios inventados.</strong> Esta página usa un paseo '
                  'aleatorio para mostrar cómo funciona el bot. No dice nada sobre el mercado real. '
                  'Genera la tuya con precios reales: <code>python -m trading_bot.report --symbol '
                  'BTC/USDT --days 180</code></p>')

    body = TEMPLATE.format(
        chart_js=CHART_JS,
        title=html.escape(f"Bot {meta['symbol']} {meta['fast']}/{meta['slow']}"),
        symbol=html.escape(meta["symbol"]),
        source=html.escape(meta["source"]),
        timeframe=html.escape(meta["timeframe"]),
        fast=meta["fast"], slow=meta["slow"],
        desde=f"{summary['desde']:%d/%m/%Y}", hasta=f"{summary['hasta']:%d/%m/%Y}",
        velas=summary["velas"],
        notice=notice,
        capital_inicial=_money(summary["capital_inicial"]),
        capital_final=_money(summary["capital_final"]),
        ret=_pct(summary["retorno_estrategia"]),
        ret_cls="pos" if summary["retorno_estrategia"] >= 0 else "neg",
        bh=_pct(summary["retorno_comprar_y_mantener"]),
        beat=("superó a" if beat >= 0 else "quedó por debajo de") + f" comprar y mantener por {abs(beat) * 100:.1f} puntos".replace(".", ","),
        ops=summary["operaciones_cerradas"],
        wins=f"{summary['porcentaje_aciertos']:.0%}",
        dd=f"{summary['maxima_caida']:.1%}".replace(".", ","),
        fee=f"{meta['fee']:.2%}".replace(".", ","),
        rows="\n".join(rows) or '<tr><td colspan="6">El bot no cerró ninguna operación.</td></tr>',
        data=json.dumps(payload, separators=(",", ":")),
    )
    if not full:
        return body
    return ('<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f'{body}\n</html>\n')


TEMPLATE = """<title>{title}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;700&family=Public+Sans:wght@400;600&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
/* Layout: una columna tipo libro de operaciones; resumen arriba, gráficos, luego el detalle. */
:root {{
  --bg: #f4f6f7; --surface: #ffffff; --fg: #17202a; --muted: #5b6875; --line: #dde3e8;
  --price: #2c5f8a; --fast: #c27c0e; --slow: #7a4fa3; --up: #1b8a5a; --down: #c0392b; --hold: #8a96a3;
  --display: "Archivo", "Helvetica Neue", Arial, sans-serif;
  --body: "Public Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "JetBrains Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #11161b; --surface: #182029; --fg: #e4e9ee; --muted: #93a1ae; --line: #2a3541;
  --price: #79a9d6; --fast: #e3a43c; --slow: #b08ad6; --up: #3fbf85; --down: #ef6f60; --hold: #6f7d8a;
  color-scheme: dark; }} }}
:root[data-theme="dark"] {{
  --bg: #11161b; --surface: #182029; --fg: #e4e9ee; --muted: #93a1ae; --line: #2a3541;
  --price: #79a9d6; --fast: #e3a43c; --slow: #b08ad6; --up: #3fbf85; --down: #ef6f60; --hold: #6f7d8a;
  color-scheme: dark; }}
body {{ background: var(--bg); color: var(--fg); font: 15px/1.55 var(--body); margin: 0; }}
main {{ max-width: 1040px; margin: 0 auto; display: grid; gap: 28px;
  padding-block: 32px 48px;
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px)); }}
header {{ display: grid; gap: 6px; }}
.eyebrow {{ font: 600 12px/1 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }}
h1 {{ font: 700 clamp(26px, 5vw, 38px)/1.1 var(--display); margin: 0; text-wrap: balance; }}
h2 {{ font: 700 19px/1.2 var(--display); margin: 0; }}
.sub {{ color: var(--muted); margin: 0; }}
.notice {{ margin: 0; padding: 12px 14px; border: 1px solid var(--fast); border-radius: 8px;
  background: color-mix(in srgb, var(--fast) 10%, var(--surface)); }}
code {{ font: 13px var(--mono); overflow-wrap: anywhere; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1px;
  background: var(--line); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }}
.stat {{ background: var(--surface); padding: 14px 16px; display: grid; gap: 4px; align-content: start; }}
.stat span {{ font-size: 12px; color: var(--muted); }}
.stat b {{ font: 600 22px/1.15 var(--mono); font-variant-numeric: tabular-nums; }}
@media (max-width: 600px) {{ .stat:last-child:nth-child(odd) {{ grid-column: 1 / -1; }} }}
.verdict {{ margin: 0; font-size: 16px; }}
.pos {{ color: var(--up); }} .neg {{ color: var(--down); }}
section {{ display: grid; gap: 10px; min-width: 0; }}
.panel {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 12px; }}
.chart {{ position: relative; height: 340px; }}
.chart.small {{ height: 240px; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 13px; color: var(--muted); margin: 0; padding: 0; list-style: none; }}
.legend i {{ display: inline-block; width: 14px; height: 3px; border-radius: 2px; vertical-align: middle; margin-right: 6px; }}
.legend .tri {{ width: 0; height: 0; border-radius: 0; background: none; border-left: 6px solid transparent; border-right: 6px solid transparent; }}
.how {{ margin: 0; padding-left: 20px; display: grid; gap: 6px; max-width: 70ch; }}
.table-wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font: 13px var(--mono); font-variant-numeric: tabular-nums; }}
th, td {{ text-align: right; padding: 7px 10px; border-bottom: 1px solid var(--line); white-space: nowrap; }}
th {{ font: 600 12px var(--body); color: var(--muted); }}
th:first-child, td:first-child {{ text-align: left; }}
</style>
<script src="{chart_js}"></script>
<main>
  <header>
    <div class="eyebrow">{source} · velas de {timeframe} · {desde} → {hasta}</div>
    <h1>{symbol}: cruce de medias {fast}/{slow}</h1>
    <p class="sub">El bot compra cuando la media de {fast} velas cruza por encima de la de {slow}, y vende cuando cruza por debajo. Comisión de {fee} por operación.</p>
  </header>
  {notice}
  <div class="stats">
    <div class="stat"><span>Capital final</span><b>{capital_final}</b><span>de {capital_inicial} USDT</span></div>
    <div class="stat"><span>Retorno del bot</span><b class="{ret_cls}">{ret}</b></div>
    <div class="stat"><span>Comprar y mantener</span><b>{bh}</b></div>
    <div class="stat"><span>Operaciones cerradas</span><b>{ops}</b><span>{wins} ganadoras</span></div>
    <div class="stat"><span>Peor caída</span><b class="neg">{dd}</b><span>desde un máximo</span></div>
  </div>
  <p class="verdict">En {velas} velas, el bot {beat}.</p>

  <section>
    <h2>Precio y señales</h2>
    <ul class="legend">
      <li><i style="background:var(--price)"></i>Precio de cierre</li>
      <li><i style="background:var(--fast)"></i>Media rápida ({fast})</li>
      <li><i style="background:var(--slow)"></i>Media lenta ({slow})</li>
      <li><i class="tri" style="border-bottom:10px solid var(--up)"></i>Compra</li>
      <li><i class="tri" style="border-top:10px solid var(--down)"></i>Venta</li>
    </ul>
    <div class="panel"><div class="chart"><canvas id="price" aria-label="Precio, medias y operaciones"></canvas></div></div>
  </section>

  <section>
    <h2>Capital</h2>
    <ul class="legend">
      <li><i style="background:var(--up)"></i>Bot</li>
      <li><i style="background:var(--hold)"></i>Comprar y mantener</li>
    </ul>
    <div class="panel"><div class="chart small"><canvas id="equity" aria-label="Capital del bot frente a comprar y mantener"></canvas></div></div>
  </section>

  <section>
    <h2>Cómo leerlo</h2>
    <ul class="how">
      <li>Mientras la línea naranja (rápida) está por encima de la morada (lenta), el bot está comprado.</li>
      <li>Si el precio va de lado, las medias se cruzan muchas veces y el bot pierde en comisiones.</li>
      <li>Si la línea verde del capital termina por encima de la gris, el bot fue mejor que no hacer nada.</li>
    </ul>
  </section>

  <section>
    <h2>Operaciones</h2>
    <div class="panel table-wrap">
      <table>
        <thead><tr><th>#</th><th>Compra</th><th>Precio</th><th>Venta</th><th>Precio</th><th>Resultado</th></tr></thead>
        <tbody>
{rows}
        </tbody>
      </table>
    </div>
  </section>
</main>
<script>
const D = {data};
const charts = [];
function tok(name) {{ return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }}
function draw() {{
  charts.splice(0).forEach(c => c.destroy());
  if (!window.Chart) return;
  const grid = tok('--line'), muted = tok('--muted');
  const scales = () => ({{
    x: {{ ticks: {{ color: muted, maxTicksLimit: 6, maxRotation: 0, callback(v) {{ return D.labels[v].slice(5, 10); }} }}, grid: {{ display: false }} }},
    y: {{ ticks: {{ color: muted }}, grid: {{ color: grid }} }},
  }});
  const base = () => ({{ scales: scales(), responsive: true, maintainAspectRatio: false, animation: false,
    interaction: {{ mode: 'index', intersect: false }},
    plugins: {{ legend: {{ display: false }} }}, elements: {{ point: {{ radius: 0 }} }} }});
  const line = (data, color, width) => ({{ data, borderColor: color, backgroundColor: color, borderWidth: width, spanGaps: true }});
  const marks = (data, color, rot, label) => ({{ label, data, showLine: false, pointStyle: 'triangle', rotation: rot,
    pointRadius: 7, pointHoverRadius: 8, borderColor: color, backgroundColor: color }});
  charts.push(new Chart(document.getElementById('price'), {{
    type: 'line',
    data: {{ labels: D.labels, datasets: [
      marks(D.buys, tok('--up'), 0, 'Compra'), marks(D.sells, tok('--down'), 180, 'Venta'),
      {{ ...line(D.fast, tok('--fast'), 1.5), label: 'Media rápida' }},
      {{ ...line(D.slow, tok('--slow'), 1.5), label: 'Media lenta' }},
      {{ ...line(D.close, tok('--price'), 1), label: 'Precio' }},
    ] }},
    options: base(),
  }}));
  charts.push(new Chart(document.getElementById('equity'), {{
    type: 'line',
    data: {{ labels: D.labels, datasets: [
      {{ ...line(D.equity, tok('--up'), 2), label: 'Bot', fill: {{ target: 'origin' }},
        backgroundColor: tok('--up') + '22' }},
      {{ ...line(D.buyHold, tok('--hold'), 1.5), label: 'Comprar y mantener' }},
    ] }},
    options: base(),
  }}));
}}
draw();
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', draw);
new MutationObserver(draw).observe(document.documentElement, {{ attributes: true, attributeFilter: ['data-theme'] }});
</script>"""


def main():
    p = argparse.ArgumentParser(description="Reporte visual (HTML) del backtest")
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
    p.add_argument("--out", default="reporte.html")
    p.add_argument("--fragment", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args()

    df = load_data(args)
    result, closed = run_backtest(df, args.fast, args.slow, args.capital, args.fee)
    summary = summarize(result, closed, args.capital)
    trades, open_trade = trade_list(result)
    source = ("Precios inventados" if args.synthetic
              else f"CSV {args.csv}" if args.csv else args.exchange.capitalize())
    meta = {"symbol": args.symbol, "timeframe": args.timeframe, "fast": args.fast,
            "slow": args.slow, "fee": args.fee, "source": source, "synthetic": args.synthetic}
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render_html(result, trades, open_trade, summary, meta, full=not args.fragment))
    print(f"Reporte guardado en {args.out}. Ábrelo con tu navegador.")


if __name__ == "__main__":
    main()
