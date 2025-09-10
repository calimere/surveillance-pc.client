import mss
import requests
import configparser

from const import CONFIG_FILE

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

DISCORD_WEBHOOK_URL = config.get("url", "discord_webhook_url", fallback=None)
DISCORD_SEND = config.getboolean("settings", "discord_send", fallback=False)

with mss.mss() as sct:
    # Capture le premier écran
    filenames = []  
    for i, monitor in enumerate(sct.monitors[1:], start=1):
        filename = f"capture_{monitor['left']}_{monitor['top']}.png"
        filenames.append(filename)
        sct.shot(mon=i, output=filename)
        print(f"Capture d'écran enregistrée sous '{filename}'")
        if DISCORD_SEND and DISCORD_WEBHOOK_URL:
            data = { "content": f"Capture d'écran enregistrée sous '{filename}'" }
            with open(filename, "rb") as f:
                files = { "file": f }
                requests.post(DISCORD_WEBHOOK_URL, data=data, files=files)
                print(f"Capture d'écran envoyée à Discord via le webhook.")

        with open(filename, "rb") as f:
            image_bytes = f.read()
            # Ici, vous pouvez publier image_bytes sur RabbitMQ
            # Exemple :
            # channel.basic_publish(exchange='', routing_key='your_queue', body=image_bytes)