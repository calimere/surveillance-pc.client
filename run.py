import configparser
import time
from business.ESyncType import ESyncType
from const import CONFIG_FILE
from core.db import get_known_blocked_processes, get_unknown_processes, get_known_watched_processes, init_db
from core.running_processes import scan_running_processes
from core.scan_exe import scan_exe
from core.notification import send_discord_notification
from core.messaging import sync

print("Démarrage de la surveillance des exécutables...")
send_discord_notification("Démarrage de la surveillance des exécutables...")
init_db()

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

avoid_scan = config.getboolean("settings", "avoid_scan", fallback=False)
avoid_windows_scan = config.getboolean("settings", "avoid_windows_scan", fallback=True)

# tempo_sync can't be more than tempo_scan
tempo_scan = config.getint("settings", "tempo_scan", fallback=600)
tempo_sync = config.getint("settings", "tempo_sync", fallback=300)
iterator = 0

while(True):

    if (iterator == 0 or iterator == tempo_scan) and not avoid_scan:
        iterator = 0
        scan_exe(avoid_scan_windows_folder=avoid_windows_scan)

    if iterator == 0 or iterator == tempo_sync:
        sync(ESyncType.ALL)

    watched_processes = get_known_watched_processes()
    unknown_processes = get_unknown_processes()
    blocked_processes = get_known_blocked_processes()
    scan_running_processes(watched_processes, unknown_processes, blocked_processes)

    iterator += 1
    print(f"Prochaine analyse dans {tempo_scan - iterator} secondes...")
    time.sleep(1)