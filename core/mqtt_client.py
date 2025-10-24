import hashlib
from socket import socket
import uuid
import paho.mqtt.client as mqtt
import threading
import time
from core.config import config, get_pc_alias
import json

mqtt_host = config.get("mqtt", "host", fallback="localhost")
mqtt_port = config.getint("mqtt", "port", fallback=1884)
mqtt_user = config.get("mqtt", "user", fallback=None)
mqtt_pass = config.get("mqtt", "password", fallback=None)
mqtt_keepalive = config.getint("mqtt", "keepalive", fallback=60)

# Singleton du client
_client = None
_handlers = {}  # Dictionnaire topic -> fonction callback


def _on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connecté au broker MQTT")
        # Auto-subscribe aux topics déjà enregistrés avec handler
        for topic in _handlers.keys():
            client.subscribe(topic)
            print(f"📡 Auto-subscribe: {topic}")
    else:
        print(f"⚠️ Erreur de connexion MQTT (code {rc})")


def _on_message(client, userdata, msg):
    payload = msg.payload.decode()
    print(f"📩 Reçu sur {msg.topic}: {payload}")

    # Appelle le handler correspondant si défini
    if msg.topic in _handlers:
        try:
            _handlers[msg.topic](payload)
        except Exception as e:
            print(f"❌ Erreur dans le handler du topic {msg.topic}: {e}")
    else:
        print(f"⚠️ Aucun handler défini pour {msg.topic}")


def _mqtt_loop():
    """Boucle MQTT dans un thread séparé."""
    global _client
    _client.loop_forever()


def init_mqtt():
    """Initialise et connecte le client MQTT (à appeler au démarrage)."""
    global _client
    if _client is not None:
        return _client  # déjà initialisé

    client_id = _generate_client_id("mon_app")

    _client = mqtt.Client()
    _client.on_connect = _on_connect
    _client.on_message = _on_message
    _client._client_id = client_id.encode('utf-8')

    if mqtt_user:
        _client.username_pw_set(mqtt_user, mqtt_pass)
    _client.connect(mqtt_host, mqtt_port, mqtt_keepalive)

    # Démarrage du thread MQTT
    thread = threading.Thread(target=_mqtt_loop, daemon=True)
    thread.start()

    # Attendre la connexion
    time.sleep(1)
    return _client


def publish(topic: str, payload: str, qos: int = 0, retain: bool = False):
    """Publication via le client global."""
    if _client is not None:

        if "[client]" in topic:
            topic = topic.replace("[client]", _client._client_id.decode('utf-8'))

        # si payload est un objet (pas str/bytes), le sérialiser en JSON
        if not isinstance(payload, (str, bytes)):
            try:
                payload = json.dumps(payload, ensure_ascii=False)
            except (TypeError, ValueError):
                # fallback pour objets non sérialisables : utiliser __dict__ ou str()
                try:
                    payload = json.dumps(payload, default=lambda o: o.__dict__ if hasattr(o, "__dict__") else str(o), ensure_ascii=False)
                except Exception:
                    payload = str(payload)

        _client.publish(topic, payload, qos=qos, retain=retain)
    else:
        print("❌ Client MQTT non initialisé !")


def subscribe(topic: str, handler=None, qos: int = 0):
    """Souscription à un topic et enregistrement d'un handler optionnel."""
    if _client is not None:

        if "[client]" in topic:
            topic = topic.replace("[client]", _client._client_id.decode('utf-8'))

        _client.subscribe(topic, qos)
        print(f"📡 Abonné à {topic}")
        if handler:
            _handlers[topic] = handler
    else:
        print("❌ Client MQTT non initialisé !")


def register_handler(topic: str, handler):
    """Enregistre un handler pour un topic sans s'abonner."""
    _handlers[topic] = handler

def _generate_client_id(prefix="client"):
    """
    Génère un identifiant MQTT unique et stable pour ce poste.
    Basé sur la MAC + hostname.
    """
    mac = uuid.getnode()
    hostname = get_pc_alias()
    raw_id = f"{prefix}-{hostname}-{mac}"
    # Hash court pour éviter les caractères spéciaux et la longueur excessive
    return hashlib.sha1(raw_id.encode()).hexdigest()[:16]

# def send_data(data, channel_name):

#     # Vérifie si les données sont au format JSON (str ou dict)
#     if isinstance(data, dict):
#         data = json.dumps(data)
#     elif isinstance(data, list):
#         data = json.dumps(data)
#     elif isinstance(data, str):
#         try:
#             json.loads(data)
#         except (ValueError, TypeError):
#             data = json.dumps({"message": data})

#     publish(channel_name, data)

# def sync(event_type):

#     if event_type == ESyncType.EVENT:
#         events = get_all_events()
#         send_data(events, "event_queue")
#     elif event_type == ESyncType.EXE_LIST:
#         exes = get_all_exe()
#         send_data(exes, "exe_queue")
#     elif event_type == ESyncType.ALL:
#         events = get_all_events()
#         send_data(events, "event_queue")
#         exes = get_all_exe()
#         send_data(exes, "exe_queue")
#     else:
#         print("Type de synchronisation inconnu.")
#         return