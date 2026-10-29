"""Página HTML con los resultados de la investigación (research.py)."""

import html
import json

import numpy as np

CHART_JS = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"

STYLE = """
/* Layout: informe de una columna; veredicto arriba, luego curvas, tablas y detalle. */
:root {
  --bg: #f4f6f7; --surface: #ffffff; --fg: #17202a; --muted: #5b6875; --line: #dde3e8;
  --bot: #1b8a5a; --btc: #c27c0e; --all: #7a4fa3; --up: #1b8a5a; --down: #c0392b; --pick: #e8f3ee;
  --display: "Archivo", "Helvetica Neue", Arial, sans-serif;
  --body: "Public Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "JetBrains Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #11161b; --surface: #182029; --fg: #e4e9ee; --muted: #93a1ae; --line: #2a3541;
  --bot: #3fbf85; --btc: #e3a43c; --all: #b08ad6; --up: #3fbf85; --down: #ef6f60; --pick: #1d3329;
  color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #11161b; --surface: #182029; --fg: #e4e9ee; --muted: #93a1ae; --line: #2a3541;
  --bot: #3fbf85; --btc: #e3a43c; --all: #b08ad6; --up: #3fbf85; --down: #ef6f60; --pick: #1d3329;
  color-scheme: dark; }
body { background: var(--bg); color: var(--fg); font: 15px/1.55 var(--body); margin: 0; }
main { max-width: 1080px; margin: 0 auto; display: grid; gap: 28px; padding-block: 32px 48px;
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px)); }
header { display: grid; gap: 6px; }
.eyebrow { font: 600 12px/1.3 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
h1 { font: 700 clamp(26px, 5vw, 38px)/1.1 var(--display); margin: 0; text-wrap: balance; }
h2 { font: 700 19px/1.2 var(--display); margin: 0; }
p { margin: 0; max-width: 75ch; }
.muted { color: var(--muted); }
.verdict { border: 1px solid var(--line); border-left: 4px solid var(--v); border-radius: 10px;
  background: var(--surface); padding: 16px 18px; display: grid; gap: 8px; }
.verdict b.big { font: 700 22px/1.2 var(--display); color: var(--v); }
.checks { margin: 0; padding: 0; list-style: none; display: grid; gap: 4px; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1px;
  background: var(--line); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
.stat { background: var(--surface); padding: 14px 16px; display: grid; gap: 4px; align-content: start; }
.stat span { font-size: 12px; color: var(--muted); }
.stat b { font: 600 22px/1.15 var(--mono); font-variant-numeric: tabular-nums; }
@media (max-width: 600px) { .stat:last-child:nth-child(odd) { grid-column: 1 / -1; } }
.pos { color: var(--up); } .neg { color: var(--down); }
section { display: grid; gap: 10px; min-width: 0; }
.panel { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 12px; }
.chart { position: relative; height: 320px; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 13px; color: var(--muted); margin: 0; padding: 0; list-style: none; }
.legend i { display: inline-block; width: 14px; height: 3px; border-radius: 2px; vertical-align: middle; margin-right: 6px; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font: 13px var(--mono); font-variant-numeric: tabular-nums; }
th, td { text-align: right; padding: 7px 10px; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { font: 600 12px var(--body); color: var(--muted); }
th:first-child, td:first-child { text-align: left; }
tr.pick td { background: var(--pick); font-weight: 600; }
tr.bench td { color: var(--muted); }
"""

SCRIPT = """
const D = JSON.parse(document.getElementById('data').textContent);
const charts = [];
function tok(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
function draw() {
  charts.splice(0).forEach(c => c.destroy());
  if (!window.Chart) return;
  const muted = tok('--muted'), grid = tok('--line');
  const opts = (log) => ({ responsive: true, maintainAspectRatio: false, animation: false,
    interaction: { mode: 'index', intersect: false }, plugins: { legend: { display: false } },
    elements: { point: { radius: 0 } },
    scales: { x: { ticks: { color: muted, maxTicksLimit: 7, maxRotation: 0 }, grid: { display: false } },
              y: { type: log ? 'logarithmic' : 'linear', ticks: { color: muted, maxTicksLimit: 8 }, grid: { color: grid } } } });
  const ds = (data, color, width, label) => ({ label, data, borderColor: color, backgroundColor: color, borderWidth: width });
  for (const [id, key, log] of [['test', 'test', false], ['full', 'full', true]]) {
    const c = D[key];
    charts.push(new Chart(document.getElementById(id), { type: 'line',
      data: { labels: c.labels, datasets: [ds(c.bot, tok('--bot'), 2, 'Bot'), ds(c.btc, tok('--btc'), 1.5, 'BTC'),
        ds(c.all, tok('--all'), 1.2, 'Todas')] }, options: opts(log) }));
  }
}
draw();
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', draw);
new MutationObserver(draw).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
"""


def _curve(results, start=None):
    sel, btc, all_ = results
    out = {"labels": None}
    for key, r in (("bot", sel), ("btc", btc), ("all", all_)):
        e = r["equity"] if start is None else r["equity"][r["equity"].index >= start]
        e = e / e.iloc[0] * 1000
        out["labels"] = [d.strftime("%Y-%m-%d") for d in e.index]
        out[key] = [round(float(v), 2) for v in e]
    return out


def _cls(x):
    return "pos" if x >= 0 else "neg"


def write_report(path, source, results, sel, btc, assets, hold, split, ok, checks, criterio):
    all_ = next(r for r in results if r["name"] == "hold_all")
    esc = html.escape
    t, b = sel["test"], btc["test"]

    strat_rows = []
    for r in results:
        cls = "pick" if r is sel else "bench" if r["benchmark"] else ""
        tr, te = r["train"], r["test"]
        strat_rows.append(
            f'<tr class="{cls}"><td>{esc(r["label"])}</td><td>{tr["anual"]:+.0%}</td><td>{tr["sharpe"]:.2f}</td>'
            f'<td>{tr["caida"]:.0%}</td><td class="{_cls(te["anual"])}">{te["anual"]:+.0%}</td><td>{te["sharpe"]:.2f}</td>'
            f'<td>{te["caida"]:.0%}</td><td>{te["invertido"]:.0%}</td></tr>')
    asset_rows = [
        f'<tr><td>{esc(a["moneda"])}</td><td>{a["desde"]:%Y-%m}</td><td>{a["hasta"]:%Y-%m}</td>'
        f'<td>{a["volumen"] / 1e6:,.0f} M</td><td>{a["volatilidad"]:.0%}</td><td>{a["corr_btc"]:.2f}</td>'
        f'<td>{"" if np.isnan(a["prueba"]) else format(a["prueba"], "+.0%")}</td><td>{a["operable"]:.0%}</td></tr>'
        for _, a in assets.iterrows()]
    hold_rows = [f'<tr><td>{esc(c)}</td><td>{h["tiempo"]:.0%}</td><td class="{_cls(h["aporte"])}">{h["aporte"]:+.1%}</td></tr>'
                 for c, h in hold.head(15).iterrows()]
    check_items = "".join(f'<li>{"✅" if v else "❌"} {esc(k)}</li>' for k, v in checks.items())
    color = "var(--up)" if ok else "var(--down)"
    data = {"test": _curve((sel, btc, all_), split), "full": _curve((sel, btc, all_))}
    synthetic = source.startswith("monedas inventadas")

    page = f"""<title>Investigación bot de cartera</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;700&family=Public+Sans:wght@400;600&family=JetBrains+Mono:wght@400;600&display=swap">
<style>{STYLE}</style>
<script src="{CHART_JS}"></script>
<main>
  <header>
    <div class="eyebrow">{esc(source)} · velas diarias · {len(assets)} monedas · prueba desde {split:%d/%m/%Y}</div>
    <h1>Bot de cartera: {esc(sel["label"])}</h1>
    <p class="muted">Se probaron {len(results) - 2} estrategias. La elegida fue la mejor con los datos de entrenamiento;
    los números de prueba son de años que no se usaron para elegirla.{" <strong>Datos inventados: no dicen nada del mercado real.</strong>" if synthetic else ""}</p>
  </header>
  <div class="verdict" style="--v:{color}">
    <b class="big">{"El bot sirve con el criterio fijado" if ok else "El bot no sirve con el criterio fijado"}</b>
    <p class="muted">{esc(criterio)}</p>
    <ul class="checks">{check_items}</ul>
  </div>
  <div class="stats">
    <div class="stat"><span>Retorno anual (prueba)</span><b class="{_cls(t["anual"])}">{t["anual"]:+.1%}</b><span>BTC {b["anual"]:+.1%}</span></div>
    <div class="stat"><span>Sharpe (prueba)</span><b>{t["sharpe"]:.2f}</b><span>BTC {b["sharpe"]:.2f}</span></div>
    <div class="stat"><span>Peor caída (prueba)</span><b class="neg">{t["caida"]:.1%}</b><span>BTC {b["caida"]:.1%}</span></div>
    <div class="stat"><span>Tiempo invertido</span><b>{t["invertido"]:.0%}</b><span>el resto en USDT</span></div>
    <div class="stat"><span>Rotación anual</span><b>{t["rotacion"]:.0f}×</b><span>del capital</span></div>
  </div>
  <section>
    <h2>Periodo de prueba: 1 000 USDT invertidos</h2>
    <ul class="legend"><li><i style="background:var(--bot)"></i>Bot</li><li><i style="background:var(--btc)"></i>Comprar y mantener BTC</li><li><i style="background:var(--all)"></i>Comprar y mantener todas</li></ul>
    <div class="panel"><div class="chart"><canvas id="test" aria-label="Capital en el periodo de prueba"></canvas></div></div>
  </section>
  <section>
    <h2>Toda la historia (escala logarítmica)</h2>
    <div class="panel"><div class="chart"><canvas id="full" aria-label="Capital en toda la historia"></canvas></div></div>
  </section>
  <section>
    <h2>Estrategias probadas</h2>
    <div class="panel table-wrap"><table>
      <thead><tr><th>Estrategia</th><th>Anual entren.</th><th>Sharpe</th><th>Caída</th><th>Anual prueba</th><th>Sharpe</th><th>Caída</th><th>Invertido</th></tr></thead>
      <tbody>{"".join(strat_rows)}</tbody></table></div>
  </section>
  <section>
    <h2>Monedas que usó el bot en la prueba</h2>
    <div class="panel table-wrap"><table>
      <thead><tr><th>Moneda</th><th>Tiempo en cartera</th><th>Aporte a la ganancia</th></tr></thead>
      <tbody>{"".join(hold_rows) or '<tr><td colspan="3">No compró ninguna moneda.</td></tr>'}</tbody></table></div>
  </section>
  <section>
    <h2>Monedas analizadas</h2>
    <div class="panel table-wrap"><table>
      <thead><tr><th>Moneda</th><th>Desde</th><th>Hasta</th><th>Volumen diario</th><th>Volatilidad</th><th>Corr. BTC</th><th>Retorno prueba</th><th>Operable</th></tr></thead>
      <tbody>{"".join(asset_rows)}</tbody></table></div>
  </section>
</main>
<script type="application/json" id="data">{json.dumps(data, separators=(",", ":"))}</script>
<script>{SCRIPT}</script>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write('<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                + page + "\n</html>\n")
