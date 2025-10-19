#!/usr/bin/env python3
import argparse
import sys
import logging
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
    args = argparse.Namespace(topic="test/topic", message="-", qos=0)

    payload = "Message de test depuis mosquitto-pub.py ccc"

    client = mqtt.Client()
    client.username_pw_set(USERNAME, PASSWORD)

    try:
        client.connect(HOST, PORT)
    except Exception as e:
        logging.error("Impossible de se connecter: %s", e)
        sys.exit(2)

    client.loop_start()
    try:
        info = client.publish(args.topic, payload, qos=args.qos)
        if not info.wait_for_publish(timeout=5):
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

if __name__ == "__main__":
    main()
