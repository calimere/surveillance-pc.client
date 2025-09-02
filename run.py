import configparser
import time
from core.db import get_known_blocked_processes, get_unknown_processes, get_known_watched_processes, init_db
from core.running_processes import scan_running_processes
from core.scan_exe import scan_exe
from core.notification import send_discord_notification

print("Démarrage de la surveillance des exécutables...")
send_discord_notification("Démarrage de la surveillance des exécutables...")
init_db()

config = configparser.ConfigParser()
config.read("config.ini")

avoid_scan = config.getboolean("settings", "avoid_scan", fallback=False)
avoid_windows_scan = config.getboolean("settings", "avoid_windows_scan", fallback=True)

iterator = 0
while(True):

    if (iterator == 0 or iterator == 300) and not avoid_scan:
        iterator = 0
        scan_exe(avoid_scan_windows_folder=avoid_windows_scan)

    watched_processes = get_known_watched_processes()
    unknown_processes = get_unknown_processes()
    blocked_processes = get_known_blocked_processes()
    scan_running_processes(watched_processes, unknown_processes, blocked_processes)

    iterator += 1
    print(f"Prochaine analyse dans {300 - iterator} secondes...")
    time.sleep(1)