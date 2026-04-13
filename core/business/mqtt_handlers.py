import json
import psutil

from core.component.mqtt_client import publish
from core.component.logger import get_logger
from core.business.db import (
    get_process_by_id,
    get_process_by_name,
    get_running_instances,
    set_process_blocked,
    set_process_watched,
)

logger = get_logger("mqtt_handlers")


def _ack(payload_obj: dict, status: str, message: str):
    """Envoyer un accusé de réception sur le topic ack."""
    publish(
        "surveillance/[client]/ack",
        json.dumps(
            {
                "status": status,
                "message": message,
                "original_command": payload_obj,
            }
        ),
    )


def _resolve_process(payload_obj: dict):
    """
    Résoudre le processus cible depuis prc_id ou process_name.
    Retourne (process, error_message).
    """
    prc_id = payload_obj.get("prc_id")
    process_name = payload_obj.get("process_name")

    if prc_id:
        process = get_process_by_id(prc_id)
        if not process:
            return None, f"Processus prc_id={prc_id} introuvable en base"
        return process, None

    if process_name:
        # Recherche par nom uniquement (path optionnel)
        process = get_process_by_name(process_name, payload_obj.get("process_path", ""))
        if not process:
            return None, f"Processus '{process_name}' introuvable en base"
        return process, None

    return None, "Commande invalide : prc_id ou process_name requis"


def _kill_running_instances(prc_id: int) -> int:
    """
    Tuer toutes les instances en cours d'exécution pour un prc_id.
    Retourne le nombre de processus tués.
    """
    killed = 0
    try:
        running = [i for i in get_running_instances() if i.prc_id_id == prc_id]
        for instance in running:
            try:
                proc = psutil.Process(instance.pri_pid)
                proc.kill()
                killed += 1
                logger.info(f"🔴 Processus PID={instance.pri_pid} tué")
            except psutil.NoSuchProcess:
                pass  # Déjà terminé
            except psutil.AccessDenied:
                logger.warning(
                    f"⛔ Accès refusé pour tuer PID={instance.pri_pid} (privilèges insuffisants)"
                )
            except Exception as e:
                logger.error(f"Erreur kill PID={instance.pri_pid}: {e}")
    except Exception as e:
        logger.error(f"Erreur lors du kill des instances prc_id={prc_id}: {e}")
    return killed


# --------------------------------------------------------------------------- #


def handle_surveillance_cmd(payload):
    """Handler principal pour les commandes reçues sur surveillance/[client]/cmd"""

    payload_obj = None
    try:
        if isinstance(payload, (bytes, bytearray)):
            payload = payload.decode("utf-8")
        payload_obj = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as e:
        logger.error(f"Payload MQTT invalide: {e}")
        return

    command = payload_obj.get("command")
    logger.info(f"📩 Commande MQTT reçue: {command} | payload={payload_obj}")

    match command:
        case "set_blocked":
            process, error = _resolve_process(payload_obj)
            if error:
                logger.warning(error)
                _ack(payload_obj, "error", error)
                return

            set_process_blocked(process.prc_id, True)
            killed = _kill_running_instances(process.prc_id)
            msg = (
                f"Processus '{process.prc_name}' bloqué. {killed} instance(s) tuée(s)."
            )
            logger.info(f"🔒 {msg}")
            _ack(payload_obj, "ok", msg)

        case "unset_blocked":
            process, error = _resolve_process(payload_obj)
            if error:
                logger.warning(error)
                _ack(payload_obj, "error", error)
                return

            set_process_blocked(process.prc_id, False)
            msg = f"Processus '{process.prc_name}' débloqué."
            logger.info(f"🔓 {msg}")
            _ack(payload_obj, "ok", msg)

        case "set_watched":
            process, error = _resolve_process(payload_obj)
            if error:
                logger.warning(error)
                _ack(payload_obj, "error", error)
                return

            set_process_watched(process.prc_id, True)
            msg = f"Processus '{process.prc_name}' mis sous surveillance."
            logger.info(f"👁️ {msg}")
            _ack(payload_obj, "ok", msg)

        case "unset_watched":
            process, error = _resolve_process(payload_obj)
            if error:
                logger.warning(error)
                _ack(payload_obj, "error", error)
                return

            set_process_watched(process.prc_id, False)
            msg = f"Processus '{process.prc_name}' retiré de la surveillance."
            logger.info(f"👁️ {msg}")
            _ack(payload_obj, "ok", msg)

        case _:
            msg = f"Commande inconnue: '{command}'"
            logger.warning(msg)
            _ack(payload_obj, "error", msg)


def handle_surveillance_ack(payload):
    """Handler pour les accusés de réception (surveillance/[client]/ack)"""
    logger.debug(f"ACK reçu: {payload}")
