import time
from business.ESyncType import ESyncType
from core.db import get_known_blocked_processes, get_unknown_processes, get_known_watched_processes, init_db
from core.running_processes import scan_running_processes
from core.scan_exe import scan_exe
from core.notification import send_discord_notification
from core.messaging import sync
from core.config import config, get_pc_alias
from core.mqtt_client import init_mqtt, publish, subscribe
from core.mqtt_handlers import handle_surveillance_cmd


print("Démarrage de la surveillance des exécutables...")
send_discord_notification(f"Démarrage de la surveillance des exécutables sur le pc {get_pc_alias()}...")
init_db()

avoid_scan = config.getboolean("settings", "avoid_scan", fallback=False)
avoid_windows_scan = config.getboolean("settings", "avoid_windows_scan", fallback=True)

# tempo_sync can't be more than tempo_scan
tempo_scan = config.getint("settings", "tempo_scan", fallback=500)
tempo_sync = config.getint("settings", "tempo_sync", fallback=250)
iterator = 0


init_mqtt()
subscribe("surveillance/[client]/cmd", handle_surveillance_cmd)
publish("surveillance/uptime",{"pc_alias": get_pc_alias()})

while(True):

    if (iterator == 0 or iterator == tempo_scan) and not avoid_scan:
        iterator = 0
        scan_exe(avoid_scan_windows_folder=avoid_windows_scan)

    # if iterator == 0 or iterator == tempo_sync:
    #     sync(ESyncType.ALL)

    watched_processes = get_known_watched_processes()
    unknown_processes = get_unknown_processes()
    blocked_processes = get_known_blocked_processes()
    scan_running_processes(watched_processes, unknown_processes, blocked_processes)

    iterator += 1
    print(f"Prochaine analyse dans {tempo_scan - iterator} secondes...")
    publish("surveillance/uptime",{"pc_alias": get_pc_alias()})
    time.sleep(1)

    # # one-time setup: register console/signal handlers and initialise last-check timestamp
    # if 'pp_last_check_time' not in globals():
    #     pp_last_check_time = time.time()

    # if 'pp_ctrl_handler_registered' not in globals():
    #     pp_ctrl_handler_registered = True
    #     # Windows console control handler (CTRL_CLOSE_EVENT / CTRL_LOGOFF_EVENT / CTRL_SHUTDOWN_EVENT)
    #     try:
    #         kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    #         HandlerRoutine = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)
    #         def _ctrl_handler(ctrl_type):
    #             try:
    #                 # 2 = CTRL_CLOSE_EVENT, 5 = CTRL_LOGOFF_EVENT, 6 = CTRL_SHUTDOWN_EVENT
    #                 if ctrl_type in (2, 5, 6):
    #                     send_discord_notification(f"Arrêt/fermeture détecté (code {ctrl_type}) sur le pc {get_pc_alias()}")
    #                 else:
    #                     send_discord_notification(f"Événement console {ctrl_type} reçu sur le pc {get_pc_alias()}")
    #             except Exception:
    #                 pass
    #             # return False to allow default handling as well
    #             return False
    #         kernel32.SetConsoleCtrlHandler(HandlerRoutine(_ctrl_handler), True)
    #     except Exception:
    #         # non-Windows or ctypes issue: ignore
    #         pass

    #     # POSIX-style signals (SIGTERM/SIGINT)
    #     try:
    #         def _sig_handler(signum, frame):
    #             try:
    #                 send_discord_notification(f"Signal {signum} reçu; arrêt du processus sur le pc {get_pc_alias()}")
    #             finally:
    #                 os._exit(0)
    #         signal.signal(signal.SIGTERM, _sig_handler)
    #         signal.signal(signal.SIGINT, _sig_handler)
    #     except Exception:
    #         pass

    # # detect suspend / resume by measuring real elapsed time between iterations
    # now = time.time()
    # gap = now - pp_last_check_time
    # # if gap is much larger than the expected 1s sleep, likely the PC was suspended
    # if gap > max(5, tempo_scan + 5):
    #     try:
    #         send_discord_notification(f"Reprise après mise en veille/suspension (écart {int(gap)}s) sur le pc {get_pc_alias()}")
    #     except Exception:
    #         pass

    # pp_last_check_time = now