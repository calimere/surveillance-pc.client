import psutil
import requests

from db import add_event, add_or_update_unknown_executable, get_process_by_name, update_launched_status
from notification import send_discord_notification

def scan_running_processes(watched_processes,unknown_processes):
    #Parcourt tous les processus actifs et met à jour la base.
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            name = proc.info['name']
            path = proc.info['exe'] or ""
            if not name:
                continue

            # Vérifie si le processus est dans la base de données des exécutables connus
            exe_id = get_process_by_name(name, path)

            # vérifier si le processus est dans la liste des inconnus
            if not exe_id:
                add_or_update_unknown_executable(name, path)
            else:
                # Le processus est connu, vérifie s'il est dans la liste des inconnus
                for uproc in unknown_processes:
                    if name == uproc[0] and path == uproc[1] and uproc[3]:
                        
                        print(f"Processus inconnu en cours d'exécution : {name} (PID: {proc.info['pid']})")
                        send_discord_notification(f"Processus inconnu en cours d'exécution : {name} (PID: {proc.info['pid']})")
                        
                        if uproc[5]:  # dangereux
                            try:
                                p = psutil.Process(proc.info['pid'])
                                p.terminate()  # ou p.kill()
                                print(f"Processus dangereux {name} (PID: {proc.info['pid']}) a été arrêté.")
                                send_discord_notification(f"Processus dangereux {name} (PID: {proc.info['pid']}) a été arrêté.")
                                add_event(uproc[2], 2)
                            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                                print(f"Impossible d'arrêter le processus {name} (PID: {proc.info['pid']}): {e}")
                                send_discord_notification(f"Impossible d'arrêter le processus {name} (PID: {proc.info['pid']}): {e}")

            # Utilise une recherche avec next et une lambda pour éviter la boucle imbriquée
            item = next((x for x in watched_processes if name == x[0]), None)
            if item:
                if not item[3]:
                    msg = f"Processus surveillé en cours d'exécution : {name} (PID: {proc.info['pid']})"
                    print(msg)
                    send_discord_notification(msg)
                    update_launched_status(item[2], 1)
                    add_event(item[2], 1)
                else:
                    print(f"Processus surveillé déjà en cours d'exécution : {name} (PID: {proc.info['pid']})")

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    for item in watched_processes:
        still_running = any(proc.info['name'] == item[0] for proc in psutil.process_iter(['name']))
        if not still_running and item[3]:
            msg = f"Processus surveillé arrêté : {item[0]}"
            print(msg)
            send_discord_notification(msg)
            update_launched_status(item[2], 0)
            add_event(item[2], 0)
    
    