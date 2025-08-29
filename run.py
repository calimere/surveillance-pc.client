import time
from db import get_unknown_processes, get_watch_processes, init_db
from running_processes import scan_running_processes
from scan_exe import scan_exe

print("Démarrage de la surveillance des exécutables...")
init_db()

avoid_scan = False
avoid_windows_scan = True

iterator = 0

while(True):

    if (iterator == 0 or iterator == 300) and not avoid_scan:
        iterator = 0
        scan_exe(avoid_scan_windows_folder=avoid_windows_scan)

    watched_processes = get_watch_processes()
    unknown_processes = get_unknown_processes()
    scan_running_processes(watched_processes, unknown_processes)

    iterator += 1
    print(f"Prochaine analyse dans {300 - iterator} secondes...")
    time.sleep(1)

