import time
#from core.authentication import init_authentication
from core.db import init_db
from core.running_processes import compute_running_processes_scores, compute_scores, populate_instances, scan_running_processes
from core.notification import send_discord_notification
from core.config import config, get_pc_alias
from core.mqtt_client import generate_client_id, init_mqtt, publish, subscribe
from core.mqtt_handlers import handle_surveillance_cmd, handle_surveillance_ack
from core.logger import get_logger

logger = get_logger("main")

logger.info("Démarrage de la surveillance des exécutables...")
send_discord_notification(f"Démarrage de la surveillance des exécutables sur le pc {get_pc_alias()}...")
init_db()

avoid_scan = config.getboolean("settings", "avoid_scan", fallback=False)
avoid_windows_scan = config.getboolean("settings", "avoid_windows_scan", fallback=True)

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
    init_mqtt() # initialize mqtt client
    subscribe("surveillance/[client]/cmd", handle_surveillance_cmd)
    subscribe("surveillance/[client]/ack", handle_surveillance_ack)
    publish("surveillance/[client]/uptime")

#finir la gestion des insertions en base des informations des exe
#faire la synchro des exe avec le serveur distant
#stocker la dernière date de synchro sur le serveur distant
#ajouter une vérification de synchro et récupérer la sauvegarde depuis le serveur distant si besoin
#ajouter la possibilité de fermer un processus à distance via mqtt
#ajouter la possibilité de lancer un processus à distance via mqtt
#vérifier régulièrement si mqtt est disponible et republier les messages en attente dans la queue via API

# main loop
while(True):

    publish("surveillance/[client]/uptime")
    scan_running_processes()
    time.sleep(1)
    populate_instances()
    
    time.sleep(5)
    compute_running_processes_scores()
    time.sleep(1)
    compute_scores()