import time
from peewee import SqliteDatabase

# from core.authentication import init_authentication
from core.component.queue_worker import IntelligentQueueWorker
from core.business.db import init_db
from core.business.running_processes import (
    compute_running_processes_scores,
    compute_scores,
    populate_instances,
    scan_running_processes,
)
from core.component.notification import send_discord_notification
from core.component.config import config, get_db_path, get_pc_alias
from core.component.mqtt_client import generate_client_id, init_mqtt, publish, subscribe
from core.business.mqtt_handlers import handle_surveillance_cmd, handle_surveillance_ack
from core.component.logger import get_logger
from core.database.services.process_repository import ProcessRepository

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


# run.py - Initialisation
# worker = IntelligentQueueWorker()
# worker.start()


# # Utilisation simple mais puissante
# def on_high_risk_detected(instance, score):
#     worker.add_item(
#         {
#             "type": "security_alert",
#             "data": instance,
#             "score": score,
#             "timestamp": time.time(),
#         },
#         priority=1,
#     )  # Priorité maximale


# def on_process_batch_ready(processes):
#     worker.add_item(
#         {"type": "process_update", "data": processes, "batch_size": len(processes)},
#         priority=3,
#     )


# main loop
while True:
    publish("surveillance/[client]/uptime")
    scan_running_processes()
    time.sleep(1)
    populate_instances()

    time.sleep(5)
    compute_running_processes_scores()
    time.sleep(1)
    compute_scores()
