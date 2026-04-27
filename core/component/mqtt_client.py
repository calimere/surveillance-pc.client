from core.enum.EMQTTStatus import MQTTStatus
from core.component.authentication import generate_client_id
import paho.mqtt.client as mqtt
import threading
import time
from core.component.config import config
import json
from core.component.logger import get_logger

logger = get_logger("mqtt_client")

mqtt_host = config.get("mqtt", "host", fallback="localhost")
mqtt_port = config.getint("mqtt", "port", fallback=1884)
mqtt_user = config.get("mqtt", "user", fallback=None)
mqtt_pass = config.get("mqtt", "password", fallback=None)
mqtt_keepalive = config.getint("mqtt", "keepalive", fallback=60)

# Singleton du client
_client = None
_handlers = {}  # Dictionnaire topic -> fonction callback


def ping():
    """Vérifie la connectivité MQTT"""
    if _client is not None:
        try:
            _client.publish("surveillance/[client]/ping", "ping", qos=1)
            return True
        except Exception as e:
            logger.error(f"Erreur lors du ping MQTT: {e}")
            return False
    else:
        logger.warning("Client MQTT non initialisé pour le ping")
        return False


def get_mqtt_status():
    """Retourne le statut de la connexion MQTT."""
    global _client
    if _client is None:
        return MQTTStatus.DISCONNECTED
    else:
        return (
            MQTTStatus.CONNECTED if _client.is_connected() else MQTTStatus.DISCONNECTED
        )


def _on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("✅ Connecté au broker MQTT")
        # Auto-subscribe aux topics déjà enregistrés avec handler
        for topic in _handlers.keys():
            client.subscribe(topic)
            logger.debug(f"📡 Auto-subscribe: {topic}")
    else:
        logger.error(f"⚠️ Erreur de connexion MQTT (code {rc})")


def _on_message(client, userdata, msg):
    payload = msg.payload.decode()
    logger.debug(f"📩 Reçu sur {msg.topic}: {payload}")

    # Appelle le handler correspondant si défini
    if msg.topic in _handlers:
        try:
            _handlers[msg.topic](payload)
        except Exception as e:
            logger.error(f"❌ Erreur dans le handler du topic {msg.topic}: {e}")
    else:
        logger.warning(f"⚠️ Aucun handler défini pour {msg.topic}")


def _mqtt_loop():
    """Boucle MQTT dans un thread séparé."""
    global _client
    _client.loop_forever()


def init_mqtt():
    """Initialise et connecte le client MQTT (à appeler au démarrage)."""
    global _client
    if _client is not None:
        return _client  # déjà initialisé

    client_id = generate_client_id()

    _client = mqtt.Client()
    _client.on_connect = _on_connect
    _client.on_message = _on_message
    _client._client_id = client_id.encode("utf-8")

    if mqtt_user:
        _client.username_pw_set(mqtt_user, mqtt_pass)
    _client.connect(mqtt_host, mqtt_port, mqtt_keepalive)

    # Démarrage du thread MQTT
    thread = threading.Thread(target=_mqtt_loop, daemon=True)
    thread.start()

    # Attendre la connexion
    time.sleep(1)
    return _client


def publish(topic: str, payload: str = None, qos: int = 0, retain: bool = False):
    """Publication via le client global."""
    if _client is not None:
        if "[client]" in topic:
            topic = topic.replace("[client]", _client._client_id.decode("utf-8"))

        # si payload est un objet (pas str/bytes), le sérialiser en JSON
        if not isinstance(payload, (str, bytes)):
            try:
                payload = json.dumps(payload, ensure_ascii=False)
            except (TypeError, ValueError):
                # fallback pour objets non sérialisables : utiliser __dict__ ou str()
                try:
                    payload = json.dumps(
                        payload,
                        default=lambda o: (
                            o.__dict__ if hasattr(o, "__dict__") else str(o)
                        ),
                        ensure_ascii=False,
                    )
                except Exception:
                    payload = str(payload)

        _client.publish(topic, payload, qos=qos, retain=retain)
        return True
    else:
        logger.error("❌ Client MQTT non initialisé !")
        return None


def subscribe(topic: str, handler=None, qos: int = 0):
    """Souscription à un topic et enregistrement d'un handler optionnel."""
    if _client is not None:
        if "[client]" in topic:
            topic = topic.replace("[client]", _client._client_id.decode("utf-8"))

        _client.subscribe(topic, qos)
        logger.info(f"📡 Abonné à {topic}")
        if handler:
            _handlers[topic] = handler
    else:
        logger.error("❌ Client MQTT non initialisé !")


def register_handler(topic: str, handler):
    """Enregistre un handler pour un topic sans s'abonner."""
    _handlers[topic] = handler
