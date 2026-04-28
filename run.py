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
from core.component.bidirectional_sync_worker import (
    get_bidirectional_sync_worker,
    stop_bidirectional_sync_worker,
    get_bidirectional_sync_stats,
)
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
from core.business.mqtt_handlers import (
    handle_surveillance_cmd,
    handle_surveillance_ack,
    handle_server_changes,
    handle_sync_request,
)
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

    # Abonnements pour synchronisation bidirectionnelle
    subscribe("surveillance/[client]/server_changes", handle_server_changes)
    subscribe("surveillance/[client]/sync_request", handle_sync_request)
    logger.info("📡 MQTT topics sync bidirectionnel configurés")

# faire la synchro des exe avec le serveur distant
# stocker la dernière date de synchro sur le serveur distant
# ajouter une vérification de synchro et récupérer la sauvegarde depuis le serveur distant si besoin
# ajouter la possibilité de fermer un processus à distance via mqtt
# ajouter la possibilité de lancer un processus à distance via mqtt
# vérifier régulièrement si mqtt est disponible et republier les messages en attente dans la queue via API

# 🚀 Démarrage des workers asynchrones
queue_worker = get_queue_worker()  # Worker pour notifications temps réel
logger.info("Queue Worker activé pour notifications temps réel")

# 🔄 Démarrage du sync worker pour synchronisation périodique
sync_interval = config.getint(
    "settings", "tempo_sync", fallback=300
)  # 300s par défaut (comme dans config)
sync_worker = get_sync_worker(sync_interval)
logger.info(f"Sync Worker activé avec intervalle de {sync_interval}s")

# 🔄 Démarrage du sync bidirectionnel (serveur → client)
bidirectional_sync_interval = config.getint(
    "settings", "bidirectional_sync_interval", fallback=600
)  # 10 minutes par défaut
bidirectional_sync_worker = get_bidirectional_sync_worker(bidirectional_sync_interval)
bidirectional_sync_worker.start()
logger.info(
    f"🔄 Sync Bidirectionnel activé avec intervalle de {bidirectional_sync_interval}s"
)

# 🧠 Démarrage du monitoring mémoire
start_memory_monitoring()
logger.info("Monitoring mémoire activé")

# main loop

start_time = time.time()
add_heartbeat(
    {
        "cpu_usage": psutil.cpu_percent(interval=None),
        "memory_usage": psutil.virtual_memory().percent,
    }
)

try:
    loop_count = 0
    while True:
        uptime_seconds = int(time.time() - start_time)
        uptime_str = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s"
        publish("surveillance/[client]/uptime", uptime_str)
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
            uptime_seconds = int(time.time() - start_time)
            uptime_str = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s"
            log_memory_report(uptime_str)

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

            # 📊 Statistiques sync bidirectionnel
            bidirectional_stats = get_bidirectional_sync_stats()
            if bidirectional_stats.get("is_running"):
                logger.info(
                    f"🔄 Bidirectional sync: {bidirectional_stats.get('server_changes_applied', 0)} applied, "
                    f"{bidirectional_stats.get('conflicts_resolved', 0)} conflicts resolved"
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
    stop_bidirectional_sync_worker()
    stop_sync_worker()
    stop_memory_monitoring()
    stop_queue_worker()

    logger.info("Système arrêté proprement")
