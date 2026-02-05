import datetime
import psutil

from business.EExeEventType import EExeEventType
from core.db import add_event, add_events_batch, add_process, add_process_instance, get_non_populate_process_instance, get_not_compute_process_instance, get_process_by_id, get_process_by_name, get_process_instance_by_pid, get_running_instances, get_running_instances_without_score, set_process_instance_populated, stop_process_instance, update_process_instance_score
from core.mqtt_publish import publish_executable_add, publish_executable_event, publish_notification
from core.logger import get_logger
from core.process import get_file_signer, get_owner_for_pid, get_visible_window_pids, get_wmi_process_info, is_weird_path

logger = get_logger("running_processes")

def populate_instances():
    instances = get_non_populate_process_instance()
    for instance in instances:
        try:
            populate_instance(instance)
        except Exception as e:
            logger.error(f"Erreur lors de la population de l'instance ID={instance.id}: {e}")
    
def populate_instance(instance):
    process = get_process_by_id(instance.prc_id)
    if not process:
        logger.error(f"Processus introuvable pour l'instance ID={instance.id}")
        return
    
    owner = get_owner_for_pid(instance.pri_pid)      # WMI
    if not owner:
       owner = "system"

    signer = get_file_signer(instance.pri_pid)
    signed_by = signer["subject"] if signer else ""
    signed_thumbprint = signer["thumbprint"] if signer else ""
    signed_is_ev = signer["is_ev"] if signer else False
    
    set_process_instance_populated(instance.id, signed_by, signed_thumbprint, signed_is_ev, owner)

def handle_new_instance(proc, ppid, process, visible_pids):
    pid = proc.pid
    exe = proc.info['exe']
    weird_path = is_weird_path(exe)
    has_window = pid in visible_pids

    process_instance = add_process_instance(process.prc_id, datetime.datetime.now(), pid, ppid, proc.info['create_time'], has_window, weird_path)
    add_event(process_instance.pri_id, EExeEventType.START, datetime.datetime.now())
    
def scan_running_processes():

    logger.info("Scan des processus en cours...")
    
    seen_instances = set()
    
    # Appeler une seule fois les fonctions coûteuses
    visible_pids = get_visible_window_pids()
    
    # Cache des processus pour réduire les requêtes DB
    process_cache = {}  # (name, exe) -> process
    
    # Batch les nouveaux processus pour traitement groupé
    new_instances = []

    for proc in psutil.process_iter(['pid', 'name', 'exe', 'create_time']):
        try:
            pid = proc.info['pid']
            start_time = proc.info['create_time']
            name = proc.info['name']
            exe = proc.info['exe'] if proc.info['exe'] is not None else ""
            ppid = proc.ppid()

            key = (pid, start_time)
            seen_instances.add(key)

            # Utiliser le cache pour éviter les requêtes DB répétées
            cache_key = (name, exe)
            if cache_key not in process_cache:
                process = get_process_by_name(name, exe)
                if not process:
                    process = add_process(name, exe)
                    logger.info(f"Nouveau processus détecté : {name}")
                process_cache[cache_key] = process
            else:
                process = process_cache[cache_key]

            instance = get_process_instance_by_pid(pid, start_time)
            if not instance:
                new_instances.append((proc, ppid, process))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Le processus a disparu pendant l'itération
            continue
    
    # Traiter les nouvelles instances après avoir collecté toutes les infos
    for proc, ppid, process in new_instances:
        try:
            handle_new_instance(proc, ppid, process, visible_pids)
        except Exception as e:
            logger.error(f"Erreur lors du traitement de la nouvelle instance PID={proc.pid}: {e}")
            
    # Identifier et traiter les processus arrêtés en batch
    running_instances = get_running_instances()
    stopped_count = 0
    now = datetime.datetime.now()
    
    # Collecter les événements STOP à insérer en batch
    stop_events = []
    instances_to_stop = []
    
    for instance in running_instances:
        if (instance.pri_pid, instance.pri_start_time) not in seen_instances:
            stop_events.append({
                'pri_id': instance.pri_id,
                'pev_type': EExeEventType.STOP.value,
                'pev_timestamp': now
            })
            instances_to_stop.append(instance.pri_id)
            stopped_count += 1
    
    # Insérer tous les événements STOP en une seule transaction
    if stop_events:
        add_events_batch(stop_events)
        
        # Mettre à jour le statut des instances
        for pri_id in instances_to_stop:
            stop_process_instance(pri_id)
    
    if stopped_count > 0:
        logger.info(f"{stopped_count} processus arrêté(s) détecté(s)")
    
    logger.debug(f"Scan terminé. {len(new_instances)} nouvelles instances, {stopped_count} arrêtées.")

def compute_running_processes_scores():
    
    instances = get_running_instances_without_score()
    children = {}
    for instance in instances:
        children.setdefault(instance.pri_ppid, []).append(instance)
    
    for inst in instances:
        score = calculate_risk_score(inst, children.get(inst.pri_pid, []))
        update_process_instance_score(inst.id, score)
    
    pass

def compute_scores():
    instances = get_not_compute_process_instance()
    children = {}
    
    for instance in instances:
        children.setdefault(instance.pri_ppid, []).append(instance)
        
    for inst in instances:
        score = calculate_risk_score(inst, children.get(inst.pri_pid, []))
        update_process_instance_score(inst.id, score)     

def calculate_risk_score(instance, child_instances):
    
    #TODO : revoir la logique de calcul du score en fonction des événements liés à l'instance et à ses enfants
    #TODO : ajouter des événements liés à l'instance et à ses enfants (ex: si un enfant est arrêté brutalement, si un enfant a un score élevé, etc.) et en tenir compte dans le calcul du score de l'instance parente
    #TODO : ajouter un poids plus important aux événements récents (ex: un enfant qui a été lancé il y a 5 minutes aura plus d'impact sur le score de l'instance parente qu'un enfant qui a été lancé il y a 2 jours)
    #TODO : ajouter une vérification de la légitimité du parent (ex: si un processus système comme explorer.exe lance cmd.exe, c'est moins suspect que si c'est un processus inconnu qui lance cmd.exe)
    #TODO : ajouter une vérification de la légitimité du chemin d'accès (ex: si un processus est lancé depuis un chemin temporaire ou un chemin d'un utilisateur, c'est plus suspect que s'il est lancé depuis un chemin de programme files)
    #TODO : ajouter une vérification de la légitimité du signer (ex: si un processus est signé par une autorité de confiance, c'est moins suspect que s'il n'est pas signé ou s'il est signé par une autorité inconnue)
    
    score = 0
    process = get_process_by_id(instance.prc_id)

    if process.prc_is_unknown:
        score += 3
    if process.prc_is_dangerous:
        score += 5
    if process.prc_blocked:
        score += 5
    if instance.pri_weird_path:
        score += 2
    if not instance.pri_signed:
        score += 2
    if instance.pri_has_window:
        score -= 1
        
    return max(score, 0)

# def parent_based_score(instance, all_instances):
#     score = 0
    
#     # Processus inconnu ou weird path
#     if instance.exe.exe_is_unknown:
#         score += 3
#     if instance.exe.weird_path:
#         score += 2
#     if not instance.exe.signed:
#         score += 2

#     # Analyse parent
#     parent = all_instances.get(instance.ppid)
#     if parent:
#         if parent.exe.exe_is_unknown or parent.exe.weird_path:
#             score += 3
#         # cas où parent ne correspond pas au type attendu
#         if instance.name.lower() in ["cmd.exe", "powershell.exe"] and parent.name.lower() not in ["explorer.exe", "services.exe", "powershell.exe"]:
#             score += 5
#     else:
#         # Parent introuvable → suspicion
#         score += 1

#     return score

# def get_root_process(inst, all_instances):
#     current = inst
#     while current.ppid in all_instances:
#         current = all_instances[current.ppid]
#     return current  # le root
