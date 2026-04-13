"""
🎯 Gestionnaire global de la queue intelligente
Singleton pattern pour accès depuis tout le projet
"""

from core.component.queue_worker import IntelligentQueueWorker
from core.component.logger import get_logger
from core.enum.EQueueType import EQueueType
from core.business.db import Queue

logger = get_logger("queue_manager")

# Instance globale unique
_queue_worker_instance = None


def get_queue_worker() -> IntelligentQueueWorker:
    """
    Récupérer l'instance unique du queue worker
    Crée l'instance si elle n'existe pas encore
    """
    global _queue_worker_instance

    if _queue_worker_instance is None:
        logger.info("Initialisation du Queue Worker...")
        _queue_worker_instance = IntelligentQueueWorker()
        _queue_worker_instance.start()
        logger.info("Queue Worker démarré avec succès")

    return _queue_worker_instance


def add_notification(message_type: EQueueType, data: dict, priority: int = 5):
    """
    🎯 Fonction helper pour ajouter une notification

    Args:
        message_type: Type du message (EQueueType.SECURITY_ALERT, EQueueType.NOTIFICATION, etc.)
        data: Données du message
        priority: Priorité (1=urgent, 9=faible, 5=normal)
    """
    worker = get_queue_worker()

    item = {
        "type": message_type.value,  # Utiliser la valeur de l'enum
        **data,  # Merge des données
    }

    worker.add_item(item, priority)
    logger.debug(f"Message ajouté en queue: {message_type.value}")


def add_security_alert(process_name: str, score: int, details: dict = None):
    """🚨 Helper pour alertes de sécurité"""
    data = {"process_name": process_name, "risk_score": score, "details": details or {}}
    add_notification(EQueueType.SECURITY_ALERT, data, priority=1)


def add_process_instance_created(instance_data: dict):
    """🆕 Helper pour nouvelle instance de processus créée en BDD"""
    data = {
        "action": "instance_created",
        "instance": instance_data,
    }
    add_notification(EQueueType.PROCESS_EVENT, data, priority=4)


def add_process_event_started(instance_data: dict):
    """▶️ Helper pour événement START d'une instance"""
    data = {
        "action": "process_started",
        "instance": instance_data,
    }
    add_notification(EQueueType.PROCESS_EVENT, data, priority=3)


def add_process_event_stopped(instance_data: dict):
    """⏹️ Helper pour événement STOP d'une instance"""
    data = {
        "action": "process_stopped",
        "instance": instance_data,
    }
    add_notification(EQueueType.PROCESS_EVENT, data, priority=3)


def add_heartbeat(system_status: dict):
    """💓 Helper pour heartbeat système"""
    add_notification(EQueueType.HEARTBEAT, system_status, priority=9)


def stop_queue_worker():
    """🛑 Arrêter proprement le worker"""
    global _queue_worker_instance

    if _queue_worker_instance is not None:
        logger.info("Arrêt du Queue Worker...")
        _queue_worker_instance.running = False
        _queue_worker_instance.join(timeout=5)
        _queue_worker_instance = None
        logger.info("Queue Worker arrêté")


def get_queue_stats() -> dict:
    """
    🔍 Diagnostic complet de la queue — mémoire + base de données

    Retourne:
        - Taille de la queue en mémoire
        - Comptage des messages par statut en DB (pending/processing/sent/failed)
        - État des circuit breakers
        - Threads de retry actifs
    """
    worker = get_queue_worker()

    # --- Queue en mémoire ---
    memory_size = worker.queue.qsize()

    # --- Messages en DB par statut ---
    db_stats = {"pending": 0, "processing": 0, "sent": 0, "failed": 0}
    try:
        for status in db_stats:
            db_stats[status] = Queue.select().where(Queue.que_status == status).count()
    except Exception as e:
        logger.warning(f"Impossible de lire les stats DB: {e}")

    # --- Derniers messages échoués ---
    recent_failures = []
    try:
        rows = (
            Queue.select()
            .where(Queue.que_status == "failed")
            .order_by(Queue.created.desc())
            .limit(5)
        )
        for row in rows:
            recent_failures.append(
                {
                    "id": row.que_id,
                    "type": row.que_type,
                    "created": str(row.created),
                    "priority": row.que_priority,
                }
            )
    except Exception as e:
        logger.warning(f"Impossible de lire les échecs récents: {e}")

    # --- Circuit breakers + threads ---
    cb = worker.get_circuit_breaker_status()

    stats = {
        "memory_queue_size": memory_size,
        "db": db_stats,
        "recent_failures": recent_failures,
        "circuit_breakers": cb,
        "worker_running": worker.running,
    }

    logger.info(
        f"📊 Queue stats — mémoire: {memory_size} | "
        f"DB: pending={db_stats['pending']} processing={db_stats['processing']} "
        f"failed={db_stats['failed']} sent={db_stats['sent']} | "
        f"MQTT={cb['mqtt']['state']}"
    )

    return stats


def get_circuit_breaker_status():
    """📊 Obtenir le statut des circuit breakers"""
    worker = get_queue_worker()
    return worker.get_circuit_breaker_status()


def reset_circuit_breakers():
    """🔄 Reset force des circuit breakers (pour dépannage)"""
    worker = get_queue_worker()

    # Reset MQTT circuit breaker
    worker.mqtt_circuit_breaker = {
        "state": "closed",
        "failure_count": 0,
        "last_failure": None,
        "timeout": 15,
        "failure_threshold": 3,
        "next_retry": 0,
    }

    logger.info("🔄 Circuit breakers manually reset")
    return True
