# Bot de trading educativo (cripto, sin dinero real)

Bot sencillo para **aprender**: prueba una estrategia con precios históricos (backtest) y la
simula en vivo con dinero ficticio (paper trading). No usa API keys ni puede operar con dinero real.

> ⚠️ Ninguna estrategia garantiza ganancias. Un bot que gana en el backtest puede perder en la
> vida real. No pongas dinero real hasta entender bien los resultados.

## La estrategia: cruce de medias móviles

Una **media móvil** es el precio promedio de las últimas N velas (por ejemplo, las últimas 20 horas).

- **Media rápida** (20 velas): sigue al precio de cerca.
- **Media lenta** (50 velas): se mueve despacio y muestra la tendencia general.

Reglas:
- La rápida cruza **por encima** de la lenta → el precio sube → **comprar**.
- La rápida cruza **por debajo** de la lenta → el precio baja → **vender** y quedarse en USDT.

Funciona bien cuando hay tendencias largas y mal cuando el precio va de lado: ahí compra y vende
muchas veces y pierde en comisiones.

## Instalación

```bash
pip install -r trading_bot/requirements.txt
```

Ejecuta los comandos desde la raíz del repositorio.

## 1. Backtest (probar con el pasado)

```bash
python -m trading_bot.backtest --synthetic                     # precios inventados, sin internet
python -m trading_bot.backtest --symbol BTC/USDT --days 180    # precios reales de Binance
python -m trading_bot.backtest --fast 10 --slow 30 --timeframe 4h
python -m trading_bot.backtest --exchange kraken --symbol BTC/USDT   # si Binance está bloqueado en tu país
```

Cómo leer el resultado:
- **Retorno de la estrategia** frente a **comprar y mantener**: si la estrategia no supera a
  "comprar y no hacer nada", no aporta valor.
- **Máxima caída (drawdown)**: la peor pérdida desde un máximo. Indica cuánto dolor tendrías que aguantar.
- **% de operaciones ganadoras**: puede ser bajo y aun así ganar, si las ganadoras son grandes.

## 2. Paper trading (simular en vivo)

```bash
python -m trading_bot.paper_trade                              # revisa en cada cierre de vela
python -m trading_bot.paper_trade --synthetic --iterations 3   # prueba rápida
```

El saldo ficticio y las operaciones se guardan en `paper_<estrategia>_<velas>.json` (por ejemplo
`paper_sma_1h.json`). Borra ese archivo para empezar de cero.

## 3. Ver el gráfico

```bash
python -m trading_bot.report --symbol BTC/USDT --days 180 --out reporte.html
python -m trading_bot.report --synthetic --out reporte.html    # sin internet
```

Abre `reporte.html` con tu navegador. Verás el precio, las dos medias, dónde compró (▲) y vendió (▼)
el bot, cómo evolucionó el capital frente a "comprar y mantener" y la lista de operaciones.

## 4. Otras estrategias

Además del cruce de medias (`sma`) hay dos estrategias más. Se eligen con `--strategy` en
`backtest`, `report` y `paper_trade`:

| `--strategy` | Idea | Reglas (parámetros clásicos, fijos) |
|---|---|---|
| `sma` | Seguir la tendencia | Comprado mientras la media de 20 velas está sobre la de 50 |
| `donchian` | Seguir la tendencia, reaccionando antes | Compra al superar el máximo de las 20 velas anteriores; vende al perder el mínimo de las 10 anteriores |
| `rsi` | Comprar caídas dentro de una subida | Solo con el precio sobre su media de 200: compra con RSI(14) < 30; vende con RSI > 55 o al perder la media |

Para compararlas todas a la vez, en velas de 4h (1 y 2 años) y diarias (1, 2 y 4 años):

```bash
python -m trading_bot.compare --symbol BTC/USDT
```

Imprime una tabla, la guarda en `comparacion.txt` y da un veredicto. Una estrategia **pasa** solo si
en **todos** los periodos queda a menos de 10 puntos de comprar y mantener, o reduce la peor caída en
al menos un tercio sin perder más de la mitad del retorno. El criterio está fijado de antemano: si
ninguna pasa, no se ajustan los números hasta que alguna pase.

## Errores típicos por los que fallan los bots

1. **Mirar el futuro**: decidir con el cierre de una vela y comprar a ese mismo precio. Aquí la
   decisión se aplica en la vela siguiente (`shift(1)` en `strategy.py`).
2. **Ignorar comisiones**: con muchas operaciones, el 0.1 % por operación se come las ganancias.
3. **Sobreoptimizar**: probar cientos de combinaciones de medias hasta que el pasado se vea perfecto.
   Eso casi nunca funciona en el futuro. Prueba siempre en un periodo distinto del que usaste para ajustar.
4. **Usar la vela que aún no cerró**: su precio todavía cambia. `data.py` la descarta.
5. **Arriesgar todo**: empieza siempre con backtest y paper trading.

## Archivos

| Archivo | Qué hace |
|---|---|
| `config.py` | Valores por defecto (par, medias, capital, comisión) |
| `data.py` | Descarga precios del exchange, lee CSV o genera precios sintéticos |
| `strategy.py` | Las estrategias: calculan la señal de compra/venta |
| `backtest.py` | Simula una estrategia sobre el pasado y muestra métricas |
| `compare.py` | Compara todas las estrategias en varios periodos |
| `report.py` | Genera la página con gráficos del backtest |
| `paper_trade.py` | Simula la estrategia en vivo con dinero ficticio |
