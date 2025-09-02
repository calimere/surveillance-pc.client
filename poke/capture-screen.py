import mss
import requests
import configparser

config = configparser.ConfigParser()
config.read("../config.ini")

DISCORD_WEBHOOK_URL = config.get("url", "discord_webhook_url", fallback=None)
DISCORD_SEND = config.getboolean("settings", "discord_send", fallback=False)

with mss.mss() as sct:
    # Capture le premier écran
    sct.shot(output="capture.png")
    print("Capture d'écran enregistrée sous 'capture.png'")
    data = { "content": "Capture d'écran enregistrée sous 'capture.png'" }
    files = { "file": open("capture.png", "rb") }
    requests.post(DISCORD_WEBHOOK_URL, data=data, files=files)

