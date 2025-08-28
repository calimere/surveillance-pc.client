import psutil
import requests

from db import add_event, add_or_update_unknown_executable, get_process_by_name, update_launched_status

def scan_running_processes(watched_processes):
    """Parcourt tous les processus actifs et met à jour la base."""
    for proc in psutil.process_iter(['pid', 'name', 'exe']):
        try:
            name = proc.info['name']
            path = proc.info['exe'] or ""
            if not name:
                continue

            exe_id = get_process_by_name(name, path)
            if not exe_id:
                add_or_update_unknown_executable(name, path)

            # Utilise une recherche avec next et une lambda pour éviter la boucle imbriquée
            item = next((x for x in watched_processes if name == x[0]), None)
            if item:
                if not item[3]:
                    msg = f"Processus surveillé en cours d'exécution : {name} (PID: {proc.info['pid']})"
                    print(msg)
                    webhook_url = 'https://discord.com/api/webhooks/1385605345992380466/qJkZq1OVapB8E2NeWTf-ncHUA_nkpxpuK8E1jOjdTk8xGekhBjSoEf-rd6nEv9gyWO5s'
                    requests.post(webhook_url, json={"content": msg})
                    update_launched_status(item[2], 1)
                    add_event(item[2], 1)
                else:
                    print(f"Processus surveillé déjà en cours d'exécution : {name} (PID: {proc.info['pid']})")
   
            # Ancienne version avec boucle imbriquée
            #     if not item[3]:
            #         print(f"Processus surveillé en cours d'exécution : {name} (PID: {proc.info['pid']})")
            #         webhook_url = 'https://discord.com/api/webhooks/1385605345992380466/qJkZq1OVapB8E2NeWTf-ncHUA_nkpxpuK8E1jOjdTk8xGekhBjSoEf-rd6nEv9gyWO5s'
            #         data = {
            #             "content": f"Processus surveillé en cours d'exécution : {name} (PID: {proc.info['pid']})"
            #         }
            #         requests.post(webhook_url, json=data)
            #         print(f"Nouveau Processus surveillé en cours d'exécution : {name} (PID: {proc.info['pid']})") 
            #         update_launched_status(item[2])
            #     else:
            #         print(f"Processus surveillé déjà en cours d'exécution : {name} (PID: {proc.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    # Vérifie les processus surveillés qui ne sont plus en cours d'exécution
    for item in watched_processes:
        still_running = any(proc.info['name'] == item[0] for proc in psutil.process_iter(['name']))
        if not still_running and item[3]:
            msg = f"Processus surveillé arrêté : {item[0]}"
            print(msg)
            webhook_url = 'https://discord.com/api/webhooks/1385605345992380466/qJkZq1OVapB8E2NeWTf-ncHUA_nkpxpuK8E1jOjdTk8xGekhBjSoEf-rd6nEv9gyWO5s'
            requests.post(webhook_url, json={"content": msg})
            update_launched_status(item[2], 0)
            add_event(item[2], 0)
