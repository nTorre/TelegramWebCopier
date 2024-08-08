import json
from datetime import datetime

from quart import Quart, jsonify, request, Response, render_template
from telethon import TelegramClient, events
import asyncio
from dotenv import load_dotenv
import os
import base64

from telethon.tl.functions.channels import GetForumTopicsRequest

load_dotenv()

app = Quart(__name__)

api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
phone_number = os.getenv('PHONE_NUMBER')

client = None
loop = asyncio.get_event_loop()

active_forwards = {}


async def init_client():
    global client
    client = TelegramClient('session', api_id, api_hash, loop=loop)
    await client.start(phone=phone_number)
    print("Client Telegram avviato e autenticato")

    @client.on(events.NewMessage)
    async def forward_handler(event):
        for key, forward in active_forwards.items():
            if event.chat_id == forward['source_id']:
                # https://stackoverflow.com/questions/77204189/how-to-work-with-topics-through-telethon
                if 'topic_id' not in forward or (
                        event.message.reply_to and event.message.reply_to.forum_topic and (event.message.reply_to.reply_to_top_id == forward['topic_id'] or event.message.reply_to.reply_to_msg_id == forward['topic_id'])):
                    await client.send_message(forward['destination_id'], event.message)


@app.before_serving
async def startup():
    await init_client()


async def get_profile_photo(entity):
    try:
        photo = await client.download_profile_photo(entity, bytes)
        if photo:
            return base64.b64encode(photo).decode('utf-8')

    except Exception as e:
        print(f"Errore nel recupero della foto del profilo: {e}")
    return None


def convert_to_datetime(chat):
    return datetime.strptime(chat['date'], "%m/%d/%Y, %H:%M:%S")


async def get_topics_by_dialog_id(dialog_id):
    try:
        # Ottieni l'entità dal dialog_id
        entity = await client.get_entity(int(dialog_id))

        # Verifica se l'entità è un forum (canale con topic)
        if hasattr(entity, 'forum') and entity.forum:
            # Ottieni i topic del forum
            topics = await client(GetForumTopicsRequest(
                channel=entity,
                offset_date=None,
                offset_id=0,
                offset_topic=0,
                limit=1000000  # Puoi aumentare questo numero se necessario
            ))

            # Estrai le informazioni rilevanti dai topic
            topic_list = [
                {
                    "id": topic.id,
                    "title": topic.title,
                    "top_message": topic.top_message,
                    "unread_count": topic.unread_count,
                    "unread_mentions_count": topic.unread_mentions_count
                }
                for topic in topics.topics
            ]

            return {
                "has_topics": True,
                "topics": topic_list
            }
        else:
            return {
                "has_topics": False,
                "message": "Questo dialog non è un forum e non contiene topic."
            }
    except Exception as e:
        print(f"Errore nel recupero dei topic per il dialog ID {dialog_id}: {e}")
        return {
            "has_topics": False,
            "error": str(e)
        }

@app.route('/api/v0/get_topic/<dialog_id>')
async def get_topics(dialog_id):
    result = await get_topics_by_dialog_id(dialog_id)
    return jsonify(result)


@app.route('/api/v0/dialog_list')
async def list_chats():
    async def get_chats():
        dialogs = await client.get_dialogs()
        chat_list = []

        for dialog in dialogs:
            message = dialog.message.message
            if message is not None:
                if len(message) > 30:
                    last_message = message[:30] + "..."
                else:
                    last_message = message
            else:
                last_message = ""

            if dialog.date is None:
                date = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            else:
                date = dialog.date.strftime("%m/%d/%Y, %H:%M:%S")

            chat_list.append({
                'name': dialog.name,
                'id': dialog.id,
                'last_message': last_message,
                'date': date
            })

            chat_list.sort(key=convert_to_datetime, reverse=True)

        return chat_list

    chat_list = await get_chats()
    json_data = json.dumps(chat_list, indent=2)

    return Response(json_data, mimetype='application/json')


@app.route('/api/v0/start_forward', methods=['POST'])
async def start_forward():
    data = await request.json
    source_id = int(data['source_id'])
    destination_id = int(data['destination_id'])

    key = f"{source_id}_{destination_id}"
    active_forwards[key] = {
        'source_id': source_id,
        'destination_id': destination_id
    }

    return jsonify({"message": f"Inoltro avviato da {source_id} a {destination_id}"})


@app.route('/api/v0/start_topic_forward', methods=['POST'])
async def start_topic_forward():
    data = await request.json
    source_id = int(data['source_id'])
    destination_id = int(data['destination_id'])
    topic_id = int(data['topic_id'])

    key = f"{source_id}_{destination_id}_{topic_id}"
    active_forwards[key] = {
        'source_id': source_id,
        'destination_id': destination_id,
        'topic_id': topic_id
    }

    return jsonify({"message": f"Inoltro avviato da {source_id} (topic {topic_id}) a {destination_id}"})


@app.route('/api/v0/stop_forward', methods=['POST'])
async def stop_forward():
    data = await request.json
    source_id = int(data['source_id'])
    destination_id = int(data['destination_id'])
    topic_id = data.get('topic_id')

    if topic_id:
        key = f"{source_id}_{destination_id}_{int(topic_id)}"
    else:
        key = f"{source_id}_{destination_id}"

    if key in active_forwards:
        del active_forwards[key]
        return jsonify({"message": f"Inoltro fermato per {key}"})
    else:
        return jsonify({"message": "Nessun inoltro attivo trovato con questi parametri"}), 404


@app.route('/api/v0/list_rules', methods=['GET'])
async def list_forwards():
    to_ret = []
    for key, values in active_forwards.items():
        to_ret.append(values)
    return jsonify(to_ret)


@app.route('/')
async def index():
    return await render_template('/index.html')


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
