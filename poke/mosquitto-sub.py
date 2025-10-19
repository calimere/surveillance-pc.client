#!/usr/bin/env python3
import sys
import time
import paho.mqtt.client as mqtt

MOSQUITTO_HOST = "192.168.1.56"
MOSQUITTO_PORT = 1884
TOPIC = "test/topic"
CLIENT_ID = "calimere"

# Credentials créés sur le serveur Mosquitto
MQTT_USER = "calimere"
MQTT_PASS = "<Gtibhj13>"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connecté à {MOSQUITTO_HOST}:{MOSQUITTO_PORT}")
        client.subscribe(TOPIC)
        print(f"Abonné au topic '{TOPIC}'")
    elif rc == 4:
        print("Échec d'authentification (bad username or password)")
        sys.exit(1)
    elif rc == 5:
        print("Non autorisé (not authorized)")
        sys.exit(1)
    else:
        print(f"La connexion a échoué (rc={rc})")
        sys.exit(1)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
    except Exception:
        payload = repr(msg.payload)
    print(f"[{msg.topic}] {payload}")

def on_disconnect(client, userdata, rc):
    print(f"Déconnecté (rc={rc})")

def main():
    client = mqtt.Client(client_id=CLIENT_ID, clean_session=True)
    # définir les credentials avant la connexion
    client.username_pw_set(MQTT_USER, MQTT_PASS)

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    try:
        client.connect(MOSQUITTO_HOST, MOSQUITTO_PORT, keepalive=60)
    except Exception as e:
        print("Impossible de se connecter :", e)
        sys.exit(1)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("Interrompu, déconnexion...")
        client.disconnect()
        time.sleep(0.1)

if __name__ == "__main__":
    main()