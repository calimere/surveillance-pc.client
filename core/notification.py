import requests
import configparser
import pika
import json

config = configparser.ConfigParser()
config.read("config.ini")
DISCORD_WEBHOOK_URL = config.get("url", "discord_webhook_url", fallback=None)
DISCORD_SEND = config.getboolean("settings", "discord_send", fallback=False)


def send_message(message, channel_name='chat'):
    if DISCORD_WEBHOOK_URL and DISCORD_SEND:
        send_discord_notification(message)
    mqtt_publish(message, channel_name)

def send_data(data, channel_name):

    # Vérifie si les données sont au format JSON (str ou dict)
    if isinstance(data, dict):
        data = json.dumps(data)
    elif isinstance(data, list):
        data = json.dumps(data)
    elif isinstance(data, str):
        try:
            json.loads(data)
        except (ValueError, TypeError):
            data = json.dumps({"message": data})

    mqtt_publish(data, channel_name)

def send_discord_notification_image(message, image):
    data = { "content": message }
    files = { "file": image }
    requests.post(DISCORD_WEBHOOK_URL, data=data, files=files)


def send_discord_notification(message):
    data = { "content": message }
    requests.post(DISCORD_WEBHOOK_URL, json=data)

def mqtt_publish(message, channel_name='discover'):
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='192.168.1.56',
                port=5672,
                credentials=pika.PlainCredentials('user', 'password')
            )
        )
    except pika.exceptions.AMQPConnectionError as e:
        print(f"Erreur de connexion à RabbitMQ: {e}")
        exit(1)
    
    channel = connection.channel()

    # On s'assure que la file "hello" existe
    channel.queue_declare(queue=channel_name)
    channel.basic_publish( exchange='', routing_key=channel_name, body=message)
    connection.close()
    pass