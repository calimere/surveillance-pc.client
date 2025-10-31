import requests
import configparser

config = configparser.ConfigParser()
config.read("config.ini")
DISCORD_WEBHOOK_URL = config.get("url", "discord_webhook_url", fallback="")
DISCORD_SEND = config.getboolean("settings", "discord_send", fallback=False)

def send_message(message, channel_name='chat'):
    if DISCORD_WEBHOOK_URL and DISCORD_SEND:
        send_discord_notification(message)

def send_discord_notification_image(message, image):
    data = { "content": message }
    files = { "file": image }
    requests.post(DISCORD_WEBHOOK_URL, data=data, files=files)

def send_discord_notification(message):
    data = { "content": message }
    requests.post(DISCORD_WEBHOOK_URL, json=data)