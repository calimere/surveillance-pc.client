import datetime
import psutil

from core.component.queue_manager import (
    add_notification,
    add_process_instance_created,
    add_process_event_started,
    add_process_event_stopped,
)
from core.enum.EExeEventType import EExeEventType
from core.business.db import (
    add_event,
    add_events_batch,
    add_process,
    add_process_instance,
    get_non_populate_process_instance,
    get_not_compute_process_instance,
    get_process_by_id,
    get_process_by_name,
    get_process_instance_by_pid,
    get_recent_process_instances,
    get_running_instances,
    get_running_instances_without_score,
    set_process_instance_populated,
    stop_process_instance,
    update_process_instance_score,
)
from core.component.logger import get_logger
from core.business.process import (
    get_visible_window_pids,
    is_weird_path,
    get_file_signer_with_timeout,
)
from core.enum.EQueueType import EQueueType
from core.business.process import get_owner_for_pid_cached

logger = get_logger("running_processes")


def populate_instances():

    logger.info("Population des instances de processus...")

    try:
        instances = get_non_populate_process_instance()
        total = len(instances)

        if total == 0:
            logger.info("Aucune instance à populer")
            return

        logger.info(f"{total} instances à populer")
        processed = 0

        for instance in instances:
            try:
                populate_instance(instance)
                processed += 1

                # Log de progression tous les 10
                if processed % 10 == 0:
                    logger.info(f"Population: {processed}/{total} instances traitées")

            except Exception as e:
                logger.error(
                    f"Erreur lors de la population de l'instance ID={instance.pri_id}: {e}"
                )

                # Forcer comme populated pour éviter boucles infinies
                try:
                    set_process_instance_populated(
                        instance.pri_id, "", "", False, "system"
                    )
                except:
                    pass

        logger.info(f"Population terminée: {processed}/{total} instances traitées")

    except Exception as e:
        logger.error(f"Erreur critique dans populate_instances: {e}")

    logger.info("Population des instances de processus terminée.")


def populate_instance(instance):

    logger.debug(f"Population de l'instance de processus ID={instance.pri_id}...")

    try:
        process = get_process_by_id(instance.prc_id)
        if not process:
            logger.error(f"Processus introuvable pour l'instance ID={instance.pri_id}")
            return

        # ⚡ Version ultra-rapide sans WMI
        owner = "system"  # Valeur par défaut
        try:
            owner = get_owner_for_pid_cached(instance.pri_pid) or "system"
        except Exception as e:
            logger.debug(f"Erreur owner PID {instance.pri_pid}: {e}")
            owner = "system"

        # 🛡️ Signature avec timeout
        signed_by = ""
        signed_thumbprint = ""
        signed_is_ev = False

        try:
            signer = get_file_signer_with_timeout(process.prc_path, timeout=5)
            if signer:
                signed_by = signer.get("subject", "")
                signed_thumbprint = signer.get("thumbprint", "")
                signed_is_ev = signer.get("is_ev", False)
        except Exception as e:
            logger.warning(
                f"Impossible de vérifier la signature pour {process.prc_path}: {e}"
            )

        # 🏃‍♂️ Sauvegarde finale
        set_process_instance_populated(
            instance.pri_id, signed_by, signed_thumbprint, signed_is_ev, owner
        )

        logger.debug(f"Instance {instance.pri_id} populated avec succès")

    except Exception as e:
        logger.error(
            f"Erreur critique lors de la population de l'instance {instance.pri_id}: {e}"
        )
        # Marquer comme populated même en cas d'erreur pour éviter les loops infinies
        try:
            set_process_instance_populated(instance.pri_id, "", "", False, "system")
        except:
            pass


def handle_new_instances(new_instances, visible_pids):

    logger.info(f"{len(new_instances)} nouvelles instances de processus détectées.")

    for proc, ppid, process in new_instances:
        try:
            pid = proc.pid
            exe = proc.info["exe"]
            weird_path = is_weird_path(exe)
            has_window = pid in visible_pids

            # 🚫 Processus bloqué — tuer immédiatement
            if getattr(process, "prc_blocked", False):
                logger.warning(
                    f"🚫 Processus bloqué détecté : {proc.info['name']} (PID {proc.pid}) — kill forcé"
                )
                try:
                    psutil.Process(proc.pid).kill()
                except Exception as kill_err:
                    logger.error(f"❌ Impossible de tuer PID {proc.pid}: {kill_err}")
                add_notification(
                    {
                        "message": f"Processus bloqué tué : {proc.info['name']} (PID {proc.pid})",
                        "level": "warning",
                    }
                )
                # Créer quand même l'instance + événement pour l'historique

            # 1️⃣ Création de l'instance en BDD
            process_instance = add_process_instance(
                process.prc_id,
                datetime.datetime.now(),
                pid,
                ppid,
                proc.info["create_time"],
                has_window,
                weird_path,
            )

            # 📊 Notification instance créée
            add_process_instance_created(
                {
                    "instance_id": process_instance.pri_id,
                    "process_name": proc.info["name"],
                    "pid": proc.pid,
                    "ppid": ppid,
                    "exe": proc.info["exe"],
                    "has_window": has_window,
                    "timestamp": datetime.datetime.now(),
                }
            )

            # 2️⃣ Création de l'événement START
            add_event(
                process_instance.pri_id, EExeEventType.START, datetime.datetime.now()
            )

            # 📊 Notification événement démarré
            add_process_event_started(
                {
                    "instance_id": process_instance.pri_id,
                    "process_name": proc.info["name"],
                    "pid": proc.pid,
                    "ppid": ppid,
                    "exe": proc.info["exe"],
                    "has_window": has_window,
                    "timestamp": datetime.datetime.now(),
                }
            )

        except Exception as e:
            logger.error(
                f"Erreur lors du traitement de la nouvelle instance PID={proc.pid}: {e}"
            )

    logger.info(f"Traitement des nouvelles instances terminé.")


def scan_running_processes():

    logger.info("Scan des processus en cours...")

    seen_instances = set()
    processed_count = 0
    max_processes_per_scan = 500  # Limite pour éviter surcharge

    # Appeler une seule fois les fonctions coûteuses avec timeout
    visible_pids = get_visible_window_pids()

    # Cache des processus pour réduire les requêtes DB
    process_cache = {}  # (name, exe) -> process

    # Batch les nouveaux processus pour traitement groupé
    new_processes = []
    new_instances = []

    # 🛡️ psutil avec protection contre blocage
    for proc in psutil.process_iter(["pid", "name", "exe", "create_time"]):
        try:
            processed_count += 1
            if processed_count > max_processes_per_scan:
                logger.warning(
                    f"Limite de {max_processes_per_scan} processus atteinte, arrêt du scan"
                )
                break

            # Timeout sur les infos processus
            proc_info = None
            try:
                # Forcer refresh des infos avec timeout implicite
                proc_info = proc.as_dict(attrs=["pid", "name", "exe", "create_time"])
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception as e:
                logger.debug(f"Erreur accès processus {proc.pid}: {e}")
                continue

            if not proc_info:
                continue

            pid = proc_info["pid"]
            start_time = proc_info["create_time"]
            name = proc_info["name"] or "unknown"
            exe = proc_info["exe"] if proc_info["exe"] is not None else ""

            # Récupérer ppid avec protection
            ppid = 0
            try:
                ppid = proc.ppid()
            except:
                ppid = 0

            key = (pid, start_time)
            seen_instances.add(key)

            # Utiliser le cache pour éviter les requêtes DB répétées
            cache_key = (name, exe)
            if cache_key not in process_cache:
                process = get_process_by_name(name, exe)

                if process is None:
                    if exe == "":
                        logger.warning(
                            f"Processus '{name}' sans chemin d'accès, impossible de l'ajouter à la base de données."
                        )
                        continue
                    else:
                        process = add_process(name, exe)
                        logger.info(f"Nouveau processus détecté : {name}")
                        new_processes.append(process)
                        process_cache[cache_key] = process
            else:
                process = process_cache[cache_key]

            instance = get_process_instance_by_pid(pid, start_time)
            if not instance and process:
                new_instances.append((proc, ppid, process))

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Le processus a disparu pendant l'itération
            continue

    logger.info(f"{len(new_processes)} nouveaux processus détectés.")

    # Traiter les nouvelles instances après avoir collecté toutes les infos
    handle_new_instances(new_instances, visible_pids)

    stopped_count = handle_stopped_instances(seen_instances)

    logger.debug(
        f"Scan terminé. {len(new_instances)} nouvelles instances, {stopped_count} arrêtées."
    )


def handle_stopped_instances(seen_instances):

    # Identifier et traiter les processus arrêtés en batch
    running_instances = get_running_instances()
    stopped_count = 0
    now = datetime.datetime.now()

    # Collecter les événements STOP à insérer en batch
    stop_events = []
    instances_to_stop = []
    stopped_notifications = []  # Pour les notifications

    for instance in running_instances:
        if (instance.pri_pid, instance.pri_start_time) not in seen_instances:
            # 3️⃣ Préparer l'événement STOP
            stop_events.append(
                {
                    "pri_id": instance.pri_id,
                    "pev_type": EExeEventType.STOP.value,
                    "pev_timestamp": now,
                }
            )
            instances_to_stop.append(instance.pri_id)

            # Récupérer les infos du processus pour la notification
            process = get_process_by_id(instance.prc_id)
            if process:
                stopped_notifications.append(
                    {
                        "instance_id": instance.pri_id,
                        "process_name": process.prc_name,
                        "pid": instance.pri_pid,
                        "ppid": instance.pri_ppid,
                        "exe": process.prc_path,
                        "has_window": instance.pri_has_window,
                        "timestamp": now,
                    }
                )

            stopped_count += 1

    # Insérer tous les événements STOP en une seule transaction
    if stop_events:
        add_events_batch(stop_events)

        # Mettre à jour le statut des instances
        for pri_id in instances_to_stop:
            stop_process_instance(pri_id)

        # 📊 Envoyer toutes les notifications STOP
        for notification_data in stopped_notifications:
            add_process_event_stopped(notification_data)

    if stopped_count > 0:
        logger.info(f"{stopped_count} processus arrêté(s) détecté(s)")

    return stopped_count


def base_compute(instances):

    all_instances = get_recent_process_instances()  # Fonction à créer
    pid_to_instance = {instance.pri_pid: instance for instance in all_instances}

    parents = {}
    children = {}

    # Construire la structure parents pour les instances à traiter
    for instance in instances:
        if instance.pri_ppid in pid_to_instance:
            parents[instance.pri_pid] = pid_to_instance[instance.pri_ppid]

    # Construire la structure children avec toutes les instances récentes
    for instance in all_instances:
        children.setdefault(instance.pri_ppid, []).append(instance)

    for instance in instances:
        score = calculate_risk_score(instance, children, parents)

        # ALARME IMMEDIATE SI SCORE TRES ELEVE
        if score > 10:  # seuil à ajuster
            logger.warning(
                f"Instance de processus suspecte détectée: PID={instance.pri_pid}, Score={score}"
            )
            add_notification(
                EQueueType.NOTIFICATION,
                {
                    "instance_id": instance.id,
                    "score": score,
                    "process_name": instance.name,
                    "timestamp": datetime.datetime.now(),
                },
            )

        # ALARME IMMEDIATE SI SCORE TRES ELEVE
        if score > 20:  # seuil à ajuster
            logger.error(
                f"Instance de processus très suspecte détectée: PID={instance.pri_pid}, Score={score}"
            )
            add_notification(
                EQueueType.SECURITY_ALERT,
                {
                    "instance_id": instance.id,
                    "score": score,
                    "process_name": instance.name,
                    "timestamp": datetime.datetime.now(),
                },
            )

        update_process_instance_score(instance.pri_id, score)


def compute_running_processes_scores():

    instances = get_running_instances_without_score()
    base_compute(instances)  # pour construire les structures parents/enfants


def compute_scores():

    instances = get_not_compute_process_instance()
    base_compute(instances)


def calculate_risk_score(instance, child_instances, parent_instances):

    # TODO : revoir la logique de calcul du score en fonction des événements liés à l'instance et à ses enfants
    # TODO : ajouter des événements liés à l'instance et à ses enfants (ex: si un enfant est arrêté brutalement, si un enfant a un score élevé, etc.) et en tenir compte dans le calcul du score de l'instance parente
    # TODO : ajouter un poids plus important aux événements récents (ex: un enfant qui a été lancé il y a 5 minutes aura plus d'impact sur le score de l'instance parente qu'un enfant qui a été lancé il y a 2 jours)
    # TODO : ajouter une vérification de la légitimité du parent (ex: si un processus système comme explorer.exe lance cmd.exe, c'est moins suspect que si c'est un processus inconnu qui lance cmd.exe)
    # TODO : ajouter une vérification de la légitimité du chemin d'accès (ex: si un processus est lancé depuis un chemin temporaire ou un chemin d'un utilisateur, c'est plus suspect que s'il est lancé depuis un chemin de programme files)
    # TODO : ajouter une vérification de la légitimité du signer (ex: si un processus est signé par une autorité de confiance, c'est moins suspect que s'il n'est pas signé ou s'il est signé par une autorité inconnue)

    score = 0
    process = get_process_by_id(instance.prc_id)

    # Score basé sur les caractéristiques de l'instance
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

    # score basé sur le parent
    parent = parent_instances.get(instance.pri_pid)
    if parent:
        if parent.pri_weird_path:
            score += 3
        parent_process = get_process_by_id(parent.prc_id)
        if parent_process and (
            parent_process.prc_is_unknown or parent_process.prc_is_dangerous
        ):
            score += 3
        if (
            process.prc_name.lower() in ["cmd.exe", "powershell.exe"]
            and parent_process
            and parent_process.prc_name.lower()
            not in ["explorer.exe", "services.exe", "powershell.exe"]
        ):
            score += 5

    # score basé sur les enfants
    children = child_instances.get(instance.pri_pid, [])
    for child in children:
        if child.pri_weird_path:
            score += 2
        child_process = get_process_by_id(child.prc_id)
        if child_process and (
            child_process.prc_is_unknown or child_process.prc_is_dangerous
        ):
            score += 3

    # score basé sur la correspondance entre les signatures et le nom de l'exe (ex: si un processus s'appelle svchost.exe mais n'est pas signé ou est signé par une autorité inconnue, c'est plus suspect que s'il est signé par une autorité de confiance)
    # TODO : en vrac : ajouter une correspondance signature exe, thumbprint exe, vérifier les chemins d'accès, vérifier les processus enfants, vérifier les événements liés à l'instance et à ses enfants, ajouter une pondération en fonction de la récence des événements, etc.
    # TODO : revoir la logique de calcul du score en fonction des événements liés à l'instance et à ses enfants
    # TODO : Pourquoi tu dois rescorrer le parent quand un enfant STOP
    # TODO : Pondération temporelle (très bonne idée) - Un enfant lancé il y a 5 min compte plus que celui d’hier.
    # TODO : Ajouter pri_score_dirty pour éviter de devoir rescorrer tous les parents à chaque fois qu’un enfant est mis à jour, et ne rescorrer que les parents directs d’un enfant quand celui-ci est mis à jour (ex: quand un enfant est STOP, on met à jour son score et on met à jour le score de son parent direct en fonction du nouveau score de l’enfant, sans devoir rescorrer tous les autres enfants du parent)
    # TODO : ne rescorer que les instances qui paraissent louche (ajouter un score_dirty pour ne rescorer que les instances qui ont un score élevé ou qui ont des événements suspects, et ne pas rescorer les instances qui ont un score bas et qui n'ont pas d'événements suspects)

    # TODO : modifier l'objet de retour pour ajouter un message d'alerte et un niveau de criticité (ex: low, medium, high) en fonction du score, pour faciliter la prise de décision dans les clients (ex: si score > 10 => high risk, si score > 5 => medium risk, sinon low risk)

    return max(score, 0)
