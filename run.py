import os
import time
from business.ESyncType import ESyncType
from core.authentication import init_authentication
from core.db import get_known_blocked_processes, get_unknown_processes, get_known_watched_processes, init_db
from core.running_processes import scan_running_processes
from core.scan_exe import scan_exe
from core.notification import send_discord_notification
from core.config import config, get_pc_alias
from core.mqtt_client import _generate_client_id, init_mqtt, publish, subscribe
from core.mqtt_handlers import handle_surveillance_cmd, handle_surveillance_ack

print("Démarrage de la surveillance des exécutables...")
send_discord_notification(f"Démarrage de la surveillance des exécutables sur le pc {get_pc_alias()}...")
init_db()

avoid_scan = config.getboolean("settings", "avoid_scan", fallback=False)
avoid_windows_scan = config.getboolean("settings", "avoid_windows_scan", fallback=True)

# tempo_sync can't be more than tempo_scan
tempo_scan = config.getint("settings", "tempo_scan", fallback=500)
tempo_sync = config.getint("settings", "tempo_sync", fallback=250)
iterator = 0

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

# initialize mqtt client
init_mqtt()

# subscribe to command and ack topics
subscribe("surveillance/[client]/cmd", handle_surveillance_cmd)
subscribe("surveillance/[client]/ack", handle_surveillance_ack)
publish("surveillance/[client]/uptime")

# main loop
while(True):

    if (iterator == 0 or iterator == tempo_scan) and not avoid_scan:
        iterator = 0
        scan_exe(avoid_scan_windows_folder=avoid_windows_scan)

    watched_processes = get_known_watched_processes()
    unknown_processes = get_unknown_processes()
    blocked_processes = get_known_blocked_processes()
    scan_running_processes(watched_processes, unknown_processes, blocked_processes)

    iterator += 1
    print(f"Prochaine analyse dans {tempo_scan - iterator} secondes...")
    publish("surveillance/[client]/uptime")
    time.sleep(1)