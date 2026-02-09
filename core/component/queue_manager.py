"""
🎯 Gestionnaire global de la queue intelligente
Singleton pattern pour accès depuis tout le projet
"""

from core.component.queue_worker import IntelligentQueueWorker
from core.component.logger import get_logger

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


def add_notification(message_type: str, data: dict, priority: int = 5):
    """
    🎯 Fonction helper pour ajouter une notification

    Args:
        message_type: Type du message (security_alert, process_update, etc.)
        data: Données du message
        priority: Priorité (1=urgent, 9=faible, 5=normal)
    """
    worker = get_queue_worker()

    item = {
        "type": message_type,
        **data,  # Merge des données
    }

    worker.add_item(item, priority)
    logger.debug(f"Message ajouté en queue: {message_type}")


def add_security_alert(process_name: str, score: int, details: dict = None):
    """🚨 Helper pour alertes de sécurité"""
    data = {"process_name": process_name, "risk_score": score, "details": details or {}}
    add_notification("security_alert", data, priority=1)


def add_process_update(action: str, process_data: dict):
    """📊 Helper pour mises à jour de processus"""
    data = {
        "action": action,  # "started", "stopped", "updated"
        "process": process_data,
    }
    add_notification("process_update", data, priority=3)


def add_heartbeat(system_status: dict):
    """💓 Helper pour heartbeat système"""
    add_notification("heartbeat", system_status, priority=9)


def stop_queue_worker():
    """🛑 Arrêter proprement le worker"""
    global _queue_worker_instance

    if _queue_worker_instance is not None:
        logger.info("Arrêt du Queue Worker...")
        _queue_worker_instance.running = False
        _queue_worker_instance.join(timeout=5)
        _queue_worker_instance = None
        logger.info("Queue Worker arrêté")
