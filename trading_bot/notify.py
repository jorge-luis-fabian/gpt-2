"""Avisos por Telegram.

Configura en el archivo .env de la carpeta del bot:
    TELEGRAM_TOKEN=...      (te lo da @BotFather al crear tu bot)
    TELEGRAM_CHAT_ID=...    (lo obtienes con: python -m trading_bot.notify --chat-id)

Sin esas dos líneas, los avisos simplemente no se envían.

Ejemplos:
    python -m trading_bot.notify --chat-id   # muestra tu chat id (antes escríbele algo a tu bot)
    python -m trading_bot.notify --test      # envía un mensaje de prueba
"""

import argparse
import os

API = "https://api.telegram.org/bot{token}/{method}"


def load_env(path=".env"):
    """Lee las líneas CLAVE=valor del archivo .env (si existe)."""
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                key, sep, value = line.strip().partition("=")
                if sep and not key.startswith("#"):
                    os.environ.setdefault(key.strip(), value.strip())


def configured():
    load_env()
    return bool(os.environ.get("TELEGRAM_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def send(text):
    """Envía un mensaje. Devuelve True si se envió; nunca detiene al bot si falla."""
    if not configured():
        return False
    import requests

    try:
        r = requests.post(API.format(token=os.environ["TELEGRAM_TOKEN"], method="sendMessage"),
                          json={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text}, timeout=15)
        return r.ok
    except Exception as e:  # sin internet o Telegram caído: el bot sigue
        print(f"(no se pudo enviar el aviso de Telegram: {type(e).__name__})")
        return False


def main():
    p = argparse.ArgumentParser(description="Avisos por Telegram")
    p.add_argument("--chat-id", action="store_true", help="mostrar los chats que le escribieron a tu bot")
    p.add_argument("--test", action="store_true", help="enviar un mensaje de prueba")
    args = p.parse_args()
    load_env()
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise SystemExit("Falta TELEGRAM_TOKEN en el archivo .env")

    if args.chat_id:
        import requests

        updates = requests.get(API.format(token=token, method="getUpdates"), timeout=15).json()
        chats = {u["message"]["chat"]["id"]: u["message"]["chat"].get("first_name", "")
                 for u in updates.get("result", []) if "message" in u}
        if not chats:
            raise SystemExit("No hay mensajes. Escríbele cualquier cosa a tu bot en Telegram y repite.")
        for chat, name in chats.items():
            print(f"TELEGRAM_CHAT_ID={chat}   ({name})")
    if args.test:
        ok = send(f"✅ Prueba de avisos del bot.\n📁 {os.getcwd()}")
        print("Mensaje enviado." if ok else "No se pudo enviar: revisa TELEGRAM_TOKEN y TELEGRAM_CHAT_ID.")


if __name__ == "__main__":
    main()
