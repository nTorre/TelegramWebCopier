from flask import Flask, jsonify
from telethon import TelegramClient
import asyncio
import threading

app = Flask(__name__)

# Sostituisci questi valori con i tuoi
api_id = 'YOUR_API_ID'
api_hash = 'YOUR_API_HASH'
phone_number = 'YOUR_PHONE_NUMBER'

# Variabile globale per il client Telegram
client = None


def login_telegram():
    global client
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    client = TelegramClient('session', api_id, api_hash)

    async def start_client():
        await client.start(phone=phone_number)
        print("Client Telegram avviato e autenticato")

    loop.run_until_complete(start_client())


@app.route('/list')
def list_chats():
    global client

    async def get_chats():
        dialogs = await client.get_dialogs()
        chat_list = [{"id": dialog.id, "type": dialog.entity.type, "name": dialog.name} for dialog in dialogs]
        return chat_list

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    chat_list = loop.run_until_complete(get_chats())

    return jsonify(chat_list)


if __name__ == '__main__':
    # Avvia il login di Telegram in un thread separato
    login_thread = threading.Thread(target=login_telegram)
    login_thread.start()
    login_thread.join()  # Aspetta che il login sia completato

    # Avvia il server Flask
    app.run(debug=True)