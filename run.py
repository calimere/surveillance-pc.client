import time
import psutil

# from core.authentication import init_authentication
from core.component.queue_manager import (
    get_queue_worker,
    stop_queue_worker,
    get_circuit_breaker_status,
    add_heartbeat,
)
from core.component.sync_worker import get_sync_worker, stop_sync_worker, get_sync_stats
from core.business.db import init_db
from core.business.running_processes import (
    compute_running_processes_scores,
    compute_scores,
    populate_instances,
    scan_running_processes,
)
from core.component.notification import send_discord_notification
from core.component.config import config, get_pc_alias
from core.component.mqtt_client import generate_client_id, init_mqtt, publish, subscribe
from core.business.mqtt_handlers import handle_surveillance_cmd, handle_surveillance_ack
from core.component.logger import get_logger
from core.component.memory_monitor import (
    start_memory_monitoring,
    stop_memory_monitoring,
    log_memory_report,
)
from core.component.memory_optimizer import MemoryOptimizer

logger = get_logger("main")

logger.info("Démarrage de la surveillance des exécutables...")
send_discord_notification(
    f"Démarrage de la surveillance des exécutables sur le pc {get_pc_alias()}..."
)
init_db()

# ------------- mise en attente de l'authentification client -------------
# # authenticate client and get token
# token = None
# while token is None:
#     # authenticate client and register if needed
#     token = init_authentication()
#     if not token:
#         print("Le client n'a pas pu être authentifié. Veuillez approuver ce client dans le panneau d'administration.")
#         time.sleep(30)

# # once authenticated
# print("Client authentifié avec succès.")


if config.getint("settings", "mqtt_enabled", fallback=500) == 1:
    init_mqtt()  # initialize mqtt client
    subscribe("surveillance/[client]/cmd", handle_surveillance_cmd)
    subscribe("surveillance/[client]/ack", handle_surveillance_ack)
    publish("surveillance/[client]/uptime")

# faire la synchro des exe avec le serveur distant
# stocker la dernière date de synchro sur le serveur distant
# ajouter une vérification de synchro et récupérer la sauvegarde depuis le serveur distant si besoin
# ajouter la possibilité de fermer un processus à distance via mqtt
# ajouter la possibilité de lancer un processus à distance via mqtt
# vérifier régulièrement si mqtt est disponible et republier les messages en attente dans la queue via API


# TODO : ajouter un système de queue pour les messages MQTT si MQTT n'est pas disponible, et republier ces messages en attente via MQTT dès que MQTT est disponible, ou via API si MQTT n'est pas disponible depuis trop longtemps
# TODO : le système de queue doit être asynchrone et ne pas bloquer la boucle principale, et doit stocker les messages en attente dans une base de données locale pour éviter de perdre des messages en cas de redémarrage du client
# TODO : la queue doit être un thread à part
# TODO : si le score est élevé, envoyer une notification via Discord et MQTT sans passer par la queue pour éviter les délais, et ajouter une logique de throttling pour éviter d'envoyer trop de notifications en cas de score élevé récurrent

# TODO : syncworker  => # synchro périodique # - flag dans les tables pour dire si c'est synchronisé ou pas, et une API pour forcer la synchro d'une instance ou d'un processus, et une logique de synchro régulière pour éviter les désynchronisations
# TODO : queueworker => # alerte temps réel  # - ajouter les messages dans la queue avec un type et des données, et un worker qui traite ces messages en fonction de leur type (ex: notification, mise à jour de processus, etc) et qui publie les messages via MQTT ou API en fonction de la disponibilité de MQTT, et qui gère les erreurs et les retries en cas d'échec de publication, et qui stocke les messages en attente dans une base de données locale pour éviter de perdre des messages en cas de redémarrage du client


# 🚀 Démarrage des workers asynchrones
queue_worker = get_queue_worker()  # Worker pour notifications temps réel
logger.info("Queue Worker activé pour notifications temps réel")

# 🔄 Démarrage du sync worker pour synchronisation périodique
sync_interval = config.getint(
    "settings", "tempo_sync", fallback=300
)  # 300s par défaut (comme dans config)
sync_worker = get_sync_worker(sync_interval)
logger.info(f"Sync Worker activé avec intervalle de {sync_interval}s")

# 🧠 Démarrage du monitoring mémoire
start_memory_monitoring()
logger.info("Monitoring mémoire activé")

# main loop

add_heartbeat(
    {
        "cpu_usage": psutil.cpu_percent(interval=None),
        "memory_usage": psutil.virtual_memory().percent,
    }
)

try:
    loop_count = 0
    while True:
        publish("surveillance/[client]/uptime")
        scan_running_processes()
        time.sleep(0.1)
        populate_instances()
        time.sleep(0.1)
        compute_running_processes_scores()
        time.sleep(0.1)
        compute_scores()

        # 🧠 Nettoyage mémoire périodique (toutes les 10 boucles)
        loop_count += 1
        if loop_count % 10 == 0:
            collected = MemoryOptimizer.force_garbage_collection()
            if collected > 0:
                logger.debug(f"🗑️ {collected} objets nettoyés par le GC")

            # 🛡️ Vérification circuit breaker MQTT
            cb_stats = get_circuit_breaker_status()
            if cb_stats["mqtt"]["state"] == "open":
                mqtt_retry = cb_stats["mqtt"]["time_until_retry"]
                logger.warning(f"🚫 MQTT down — retry in {mqtt_retry:.0f}s")

        # 📊 Rapport mémoire et sync périodique (toutes les 100 boucles, ~10 minutes)
        if loop_count % 100 == 0:
            log_memory_report()

            # 💓 Heartbeat système
            add_heartbeat(
                {
                    "cpu_usage": psutil.cpu_percent(interval=None),
                    "memory_usage": psutil.virtual_memory().percent,
                }
            )

            # 📈 Statistiques de synchronisation
            sync_stats = get_sync_stats()
            if sync_stats.get("status") != "not_running":
                logger.info(
                    f"📊 Sync stats: {sync_stats['total_synced']} synced, {sync_stats['unsync_records']} pending"
                )

            # 🛡️ Statistiques circuit breaker MQTT
            cb_stats = get_circuit_breaker_status()
            if cb_stats["mqtt"]["state"] != "closed":
                logger.info(
                    f"🛡️ MQTT circuit breaker: {cb_stats['mqtt']['state']} ({cb_stats['mqtt']['failure_count']} failures)"
                )
                if cb_stats["active_retry_threads"] > 0:
                    logger.info(
                        f"♻️ Active retry threads: {cb_stats['active_retry_threads']}/{cb_stats['max_retry_threads']}"
                    )

            loop_count = 0  # Reset pour éviter l'overflow

except KeyboardInterrupt:
    logger.info("Arrêt demandé...")
finally:
    # Arrêt propre
    logger.info("Arrêt du système...")
    log_memory_report()  # Rapport final

    # 🛑 Arrêt des workers dans l'ordre inverse de démarrage
    stop_sync_worker()
    stop_memory_monitoring()
    stop_queue_worker()

    logger.info("Système arrêté proprement")
