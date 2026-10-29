"""Configuración por defecto del bot. Cambia estos valores para experimentar."""

EXCHANGE = "binance"       # exchange de donde se descargan los precios (datos públicos, sin API keys)
SYMBOL = "BTC/USDT"        # par a operar
TIMEFRAME = "1h"           # duración de cada vela: 1m, 5m, 15m, 1h, 4h, 1d...

FAST_PERIOD = 20           # media móvil rápida (número de velas)
SLOW_PERIOD = 50           # media móvil lenta (número de velas)

INITIAL_CAPITAL = 1000.0   # saldo inicial ficticio en USDT
FEE_RATE = 0.001           # comisión por operación (0.1 %)

PAPER_STATE_FILE = "paper_state.json"  # dónde guarda el paper trading su saldo y operaciones
