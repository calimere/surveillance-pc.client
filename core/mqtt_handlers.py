from core.notification import send_discord_notification
from core.mqtt_client import publish
import json
    
def handle_surveillance_cmd(payload):

    payload_obj = None

    try:
        if isinstance(payload, (bytes, bytearray)):
            payload = payload.decode('utf-8')
        payload_obj = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as e:
        send_discord_notification(f"Échec de conversion du payload en JSON: {e}")
        return

    match payload_obj.get("command"):
        case "set_watched":
            send_discord_notification(f"Commande reçue: démarrer la surveillance du processus { payload_obj.get('process_name', 'inconnu')}")
        case "unset_watched":
            send_discord_notification(f"Commande reçue: arrêter la surveillance du processus { payload_obj.get('process_name', 'inconnu')}")
        case "set_blocked":
            send_discord_notification(f"Commande reçue: bloquer le processus { payload_obj.get('process_name', 'inconnu')}")
        case "unset_blocked":
            send_discord_notification(f"Commande reçue: débloquer le processus { payload_obj.get('process_name', 'inconnu')}")
        case _:
            send_discord_notification(f"Commande de surveillance inconnue reçue via MQTT: {payload}")

    publish("surveillance/[client]/ack", json.dumps({"status": "accepted", "original_command": payload_obj}))
    pass

def handle_surveillance_ack(payload):
    send_discord_notification(f"Accusé de réception reçu via MQTT: {payload}")