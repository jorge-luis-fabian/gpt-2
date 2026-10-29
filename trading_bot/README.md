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

## 5. Bot de cartera: varias monedas a la vez

La investigación descarga la historia diaria de unas 30 monedas de Binance desde 2017 (incluye varias
que se hundieron, para no engañarse mirando solo a las ganadoras), prueba 14 estrategias de cartera y
elige una con los datos **hasta 2022**. Después la juzga con **2023 en adelante**, años que no se
usaron para elegirla.

```bash
python -m trading_bot.research      # unos minutos la primera vez; guarda los precios en datos/
python -m trading_bot.bot           # aplica el bot elegido con dinero ficticio (una revisión)
python -m trading_bot.bot --loop    # lo mismo, cada día después del cierre (00:10 UTC)
```

La investigación imprime los resultados, los guarda en `investigacion.txt`, crea `investigacion.html`
con los gráficos y deja el bot elegido en `bot_config.json`.

Estrategias de cartera (`portfolio.py`), con costos de 0,15 % por operación (comisión + deslizamiento):

| Estrategia | Idea |
|---|---|
| Tendencia N días | Cada moneda se compra si su precio está sobre su media de N días (50, 100, 200), opcionalmente solo si BTC está sobre su media de 200 |
| Rotación top K | Cada semana compra las K monedas que más subieron en 30, 60 o 90 días, solo si BTC está en tendencia alcista |
| Donchian | Cada moneda entra al romper su máximo y sale al perder su mínimo |

Solo se operan monedas con al menos 200 días de historia y 5 millones de USDT de volumen diario.

**Criterio, fijado antes de ver resultados:** el bot sirve si en el periodo de prueba tiene un Sharpe
igual o mejor que comprar y mantener BTC, una peor caída al menos un tercio menor y un retorno anual
positivo. Si no lo cumple, no se usa con dinero real.

## 6. Bot de compras periódicas (DCA)

Ninguna estrategia de entrar y salir le ganó a mantener BTC en las pruebas con datos reales. Por eso
este bot no intenta adivinar el momento: compra una cantidad fija de BTC cada semana.

```bash
python -m trading_bot.dca                          # simulación con precios reales desde 2018
python -m trading_bot.dca --amount 25 --every 14   # 25 USDT cada 2 semanas
python -m trading_bot.dca --bot --loop             # bot con dinero ficticio, revisa cada día
python -m trading_bot.dca --bot --loop --testnet   # órdenes en la Testnet de Binance (dinero de prueba)
```

Para la Testnet, crea las claves en https://testnet.binance.vision (no son las de tu cuenta real) y
guárdalas en un archivo `.env` en la carpeta del bot:

```
BINANCE_TESTNET_KEY=...
BINANCE_TESTNET_SECRET=...
```

### Avisos por Telegram

El bot DCA puede avisarte por Telegram de cada compra, de cualquier error y de cuando supera la prueba
(3 compras sin errores; se cambia con `--test-buys`). Cada mensaje incluye la carpeta del bot.

1. En Telegram, habla con @BotFather, envía `/newbot` y copia el token que te da.
2. Escríbele cualquier mensaje a tu bot nuevo.
3. En el archivo `.env` de la carpeta del bot pon `TELEGRAM_TOKEN=...`, ejecuta
   `python -m trading_bot.notify --chat-id` y añade la línea `TELEGRAM_CHAT_ID=...` que muestra.
4. Comprueba con `python -m trading_bot.notify --test`.

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
| `universe.py` | Lista de monedas y descarga de su historia diaria |
| `portfolio.py` | Estrategias y motor del bot de cartera |
| `research.py` | Investigación completa: elige monedas y estrategia |
| `research_report.py` | Página con los gráficos de la investigación |
| `bot.py` | Bot de cartera en paper trading |
| `dca.py` | Simulación y bot de compras periódicas de BTC |
| `notify.py` | Avisos por Telegram |
| `report.py` | Genera la página con gráficos del backtest |
| `paper_trade.py` | Simula la estrategia en vivo con dinero ficticio |
