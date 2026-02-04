import psutil

from business.EExeEventType import EExeEventType
from core.db import add_event, add_or_update_unknown_executable, get_process_by_name, get_running_processes, update_launched_status
from core.mqtt_publish import publish_executable_add, publish_executable_event, publish_notification
from core.logger import get_logger

logger = get_logger("running_processes")

def scan_running_processes():
    
    running_processes = get_running_processes()
    
    # Récupère la liste des processus une seule fois pour optimiser
    current_processes = list(psutil.process_iter(['pid', 'name', 'exe']))
    
    # Crée un set des noms de processus actuellement en cours d'exécution
    current_process_names = {(proc.info['name'], proc.info['exe'] or "") for proc in current_processes}

    # Identifie les processus qui étaient lancés mais ne sont plus en cours d'exécution
    for running_proc in running_processes:
        if running_proc.exe_launched and (running_proc.exe_name, running_proc.exe_path) not in current_process_names:
            logger.info(f"Processus arrêté détecté : {running_proc.exe_name}")
            update_launched_status(running_proc.exe_id, False)
            add_event(running_proc.exe_id, EExeEventType.STOP)
            
            if running_proc.exe_is_watched:
                publish_executable_event(running_proc.exe_id, EExeEventType.STOP)
    
    #Parcourt tous les processus actifs et met à jour la base.
    for proc in current_processes:
        
        try:
            
            #si pas de nom, on passe
            name = proc.info['name']
            path = proc.info['exe'] or ""
            if not name:
                continue

            # Vérifie si le processus est dans la base de données des exécutables connus
            exe = get_process_by_name(name, path)
                       
            #si le processus n'est pas connu
            if not exe:
                logger.info(f"Nouveau Processus inconnu détecté : {name} (PID: {proc.info['pid']})")
                exe = add_or_update_unknown_executable(name, path)
                add_event(exe.exe_id, EExeEventType.START)
                publish_executable_add(exe)
                publish_notification(exe.exe_id, f"Nouveau processus inconnu en cours d'exécution : {name} (PID: {proc.info['pid']})")
                publish_executable_event(exe.exe_id, EExeEventType.START)
            else: #sinon, le processus est connu
                
                # Si le processus vient de démarrer
                if not exe.exe_launched :
                    logger.info(f"Processus connu démarré : {name} (PID: {proc.info['pid']})")
                    exe = update_launched_status(exe.exe_id, True)
                    add_event(exe.exe_id, EExeEventType.START)
                    
                    if exe.exe_is_watched:
                        logger.info(f"Processus surveillé en cours d'exécution : {name} (PID: {proc.info['pid']})")
                        publish_executable_event(exe.exe_id, EExeEventType.START)
                    
                    # Construire une notification unique avec tous les flags
                    notifications_flags = []
                    if exe.exe_is_dangerous:
                        notifications_flags.append("dangereux")
                    if exe.exe_blocked:
                        notifications_flags.append("bloqué")
                    if exe.exe_is_unknown:
                        notifications_flags.append("inconnu")
                    
                    # Publier une seule notification si des flags sont présents
                    if notifications_flags:
                        flags_str = " + ".join(notifications_flags)
                        logger.warning(f"⚠️ Processus {flags_str} en cours d'exécution : {name} (PID: {proc.info['pid']})")
                        publish_notification(exe.exe_id, f"⚠️ Processus {flags_str} en cours d'exécution : {name} (PID: {proc.info['pid']})")
                else:
                    # Processus déjà en cours - log debug seulement
                    logger.debug(f"Processus déjà en cours : {name} (PID: {proc.info['pid']})")
                
                # Terminer les processus bloqués (indépendamment de exe_is_dangerous)
                if exe.exe_blocked:
                    try:
                        p = psutil.Process(proc.info['pid'])
                        p.terminate()
                        logger.warning(f"🛑 Processus bloqué terminé : {name} (PID: {proc.info['pid']})")
                        add_event(exe.exe_id, EExeEventType.STOP)
                        publish_notification(exe.exe_id, f"🛑 Processus bloqué terminé : {name} (PID: {proc.info['pid']})")
                    except psutil.AccessDenied:
                        logger.error(f"❌ Permission refusée pour terminer le processus : {name} (PID: {proc.info['pid']})")
                    except (psutil.NoSuchProcess, psutil.ZombieProcess):
                        logger.debug(f"Processus déjà terminé : {name} (PID: {proc.info['pid']})")
                    except Exception as e:
                        logger.error(f"Erreur lors de la terminaison du processus : {name} (PID: {proc.info['pid']}), erreur : {e}")
                

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass