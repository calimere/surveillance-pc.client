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