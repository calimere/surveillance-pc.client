import requests
import configparser

from const import CONFIG_FILE
from core.messaging import amqp_publish

config = configparser.ConfigParser()
config.read(CONFIG_FILE)
DISCORD_WEBHOOK_URL = config.get("url", "discord_webhook_url", fallback="")
DISCORD_SEND = config.getboolean("settings", "discord_send", fallback=False)

def send_message(message, channel_name='chat'):
    if DISCORD_WEBHOOK_URL and DISCORD_SEND:
        send_discord_notification(message)
    amqp_publish(message, channel_name)

def send_discord_notification_image(message, image):
    data = { "content": message }
    files = { "file": image }
    requests.post(DISCORD_WEBHOOK_URL, data=data, files=files)

def send_discord_notification(message):
    data = { "content": message }
    requests.post(DISCORD_WEBHOOK_URL, json=data)