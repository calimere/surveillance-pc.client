import configparser
import json
import pika

from enum import Enum
from business import ESyncType
from core.db import get_all_events, get_all_exe

config = configparser.ConfigParser()
config.read("config.ini")

RABBITMQ_HOST = config.get("messaging", "amqp_host", fallback="localhost")
RABBITMQ_PORT = config.getint("messaging", "amqp_port", fallback=5672)
RABBITMQ_USER = config.get("messaging", "amqp_user", fallback="guest")
RABBITMQ_PASSWORD = config.get("messaging", "amqp_password", fallback="guest")

def amqp_publish(message, channel_name='discover'):
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                port=RABBITMQ_PORT,
                credentials=pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
            )
        )
    except pika.exceptions.AMQPConnectionError as e:
        print(f"Erreur de connexion à RabbitMQ: {e}")
        exit(1)
    
    channel = connection.channel()
    channel.queue_declare(queue=channel_name)
    channel.basic_publish( exchange='', routing_key=channel_name, body=message)
    connection.close()
    pass

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

    amqp_publish(data, channel_name)

def sync(event_type):

    if event_type == ESyncType.EVENT:
        events = get_all_events()
        send_data(events, "event_queue")
    elif event_type == ESyncType.EXE_LIST:
        exes = get_all_exe()
        send_data(exes, "exe_queue")
    elif event_type == ESyncType.ALL:
        events = get_all_events()
        send_data(events, "event_queue")
        exes = get_all_exe()
        send_data(exes, "exe_queue")
    else:
        print("Type de synchronisation inconnu.")
        return