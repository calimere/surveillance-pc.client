#!/usr/bin/env python3
import argparse
import json
import sys
import logging
import threading
import paho.mqtt.client as mqtt

# try:
#     import paho.mqtt.client as mqtt
# except Exception:
#     sys.exit("Le paquet 'paho-mqtt' est requis. Installez-le: pip install paho-mqtt")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# --- CONFIGURATION EN DUR (modifier) ---
HOST = "192.168.1.56"
PORT = 1884
USERNAME = "calimere"
PASSWORD = "<Gtibhj13>"

# ----------------------------------------
def main():
    # Arguments codés en dur
    args = argparse.Namespace(topic="surveillance/f4d0e623087eb41b/cmd", message="-", qos=0)

    payload_obj = {"command": "set_watched", "process_name": "example.exe"}
    payload = json.dumps(payload_obj)

    client = mqtt.Client()
    client.username_pw_set(USERNAME, PASSWORD)

    connected = threading.Event()

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            logging.info("Connecté au broker %s:%s (rc=%s)", HOST, PORT, rc)
            connected.set()
        else:
            logging.error("Échec de la connexion au broker (rc=%s)", rc)

    client.on_connect = on_connect

    try:
        client.connect(HOST, PORT)
    except Exception as e:
        logging.error("Impossible de se connecter: %s", e)
        sys.exit(2)

    client.loop_start()

    # Attendre que la connexion soit établie avant de publier
    if not connected.wait(timeout=5):
        logging.error("Timeout lors de la connexion au broker")
        client.loop_stop()
        try:
            client.disconnect()
        except Exception:
            pass
        sys.exit(2)

    try:
        info = client.publish(args.topic, payload, qos=args.qos)
        if not info.wait_for_publish(timeout=10):
            logging.error("Timeout lors de la publication")
            sys.exit(3)
        if info.rc != 0:
            logging.error("Publication échouée (rc=%s)", info.rc)
            sys.exit(3)
        logging.info("Message publié sur %s", args.topic)
    finally:
        client.loop_stop()
        try:
            client.disconnect()
        except Exception:
            pass
            pass

if __name__ == "__main__":
    main()
