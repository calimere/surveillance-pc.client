import os
import datetime
from business.EExeEventType import EExeEventType
from core.config import get_app_data_dir, get_db_path
from peewee import *
from core.logger import get_logger

logger = get_logger("db")

# Configuration SQLite pour éviter les locks
db = SqliteDatabase(
    None,
    pragmas={
        'journal_mode': 'wal',  # Write-Ahead Logging pour meilleure concurrence
        'cache_size': -1 * 64000,  # 64MB de cache
        'foreign_keys': 1,
        'ignore_check_constraints': 0,
        'synchronous': 0  # Plus rapide mais moins sûr (acceptable pour logs)
    },
    timeout=30  # Timeout de 30 secondes au lieu de 5 par défaut
)

class BaseModel(Model):
    class Meta:
        database = db

class Process(BaseModel):
    prc_id = AutoField(primary_key=True)
    prc_name = TextField()
    prc_path = TextField()
    prc_program_name = TextField()
    prc_first_seen = DateTimeField()
    prc_is_unknown = BooleanField(default=False)
    prc_is_watched = BooleanField(default=False)
    prc_is_dangerous = BooleanField(default=False)
    prc_blocked = BooleanField(default=False)

    class Meta:
        table_name = 'process'

class ProcessInstance(BaseModel):
    pri_id = AutoField(primary_key=True)
    prc_id = ForeignKeyField(Process, column_name='prc_id')
    pri_timestamp = DateTimeField()
    pri_pid =IntegerField()
    pri_ppid = IntegerField()
    pri_start_time = DateTimeField()
    pri_owner = TextField()
    pri_has_window = BooleanField(default=False)
    pri_signed = BooleanField(default=False)
    pri_signed_by = TextField(null=True)
    pri_signed_thumbprint = TextField(null=True)
    pri_signed_is_ev = BooleanField(default=False)

    pri_weird_path = BooleanField(default=False)
    pri_is_running = BooleanField(default=True)
    pri_score = IntegerField(default=0) #100 = très suspect, 0 = pas de suspicion particulière
    pri_score_computed = BooleanField(default=False) #indique si le score a déjà été calculé pour cette instance ou s'il doit être recalculé (ex: après une mise à jour du processus en "watched" ou "dangerous")
    
    pri_populated = BooleanField(default=False) #indique si les données de cette instance ont déjà été utilisées pour le calcul du score de ses enfants (pour éviter de prendre en compte plusieurs fois la même instance dans le calcul du score des enfants)

    class Meta:
        table_name = 'process_instance'

class ProcessEvent(BaseModel):
    pev_id = AutoField(primary_key=True)
    pri_id = ForeignKeyField(ProcessInstance, column_name='pri_id')
    pev_type = TextField()
    pev_timestamp = DateTimeField()

    class Meta:
        table_name = 'process_event'

class Config(BaseModel):
    cfg_id = AutoField(primary_key=True)
    cfg_key = TextField()
    cfg_value = TextField()
    created = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = 'config'

class Queue(BaseModel):
    que_id = AutoField(primary_key=True)
    que_type = TextField() # type of item to process (e.g., "exe_event", "exe_list", "alarms", etc.)
    que_data = TextField() # JSON data related to the item
    created = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = 'queue'

#------------------------------------------------------------------#

def init_db():
    logger.info("Initialisation de la base de données...")
    logger.debug(f"Vérification de l'existence de la base de données à {get_db_path()}...")

    if os.path.exists(get_db_path()):
        logger.info("Base de données déjà initialisée.")
        db.init(get_db_path())
        return

    logger.info(f"Création de la base de données à {get_db_path()}...")
    os.makedirs(get_app_data_dir(), exist_ok=True)
    
    db.init(get_db_path())
    db.connect()
    db.create_tables([Process, ProcessInstance, ProcessEvent, Config, Queue])
    # Ne pas fermer la connexion ici - elle sera réutilisée
    
    logger.info(f"Base de données créée à {get_db_path()}.")

def add_queue(queue_type, queue_data):
    db.init(get_db_path())
    queue_item = Queue.create(
        que_type=queue_type,
        que_data=queue_data,
        created=datetime.datetime.now()
    )
    return queue_item

def get_running_processes():
    db.init(get_db_path())
    return Process.select().where(Process.prc_is_running == True)

def get_known_watched_processes():
    db.init(get_db_path())
    return Process.select().where((Process.prc_is_watched == True) & (Process.prc_is_unknown == False))

def get_known_blocked_processes():
    db.init(get_db_path())
    return Process.select().where((Process.prc_is_dangerous == True) & (Process.prc_is_unknown == False))

def get_unknown_processes():
    db.init(get_db_path())
    return Process.select().where(Process.prc_is_unknown == True)

def update_launched_status(exe_id, launched):
    db.init(get_db_path())
    if Process.update(prc_is_running=launched).where(Process.prc_id == exe_id).execute() == 1:
        return Process.get(Process.prc_id == exe_id)

def get_process_by_id(prc_id):
    db.init(get_db_path())
    try:
        prc = Process.get(Process.prc_id == prc_id)
        return prc
    except DoesNotExist:
        return None
    
def get_process_by_name(name, path):
    db.init(get_db_path())
    try:
        prc = Process.get((Process.prc_name == name) & (Process.prc_path == path))
        return prc
    except DoesNotExist:
        return None

def add_process(name, path):
    db.init(get_db_path())
    now = datetime.datetime.now()
    
    prc = Process.create(
        prc_name=name,
        prc_path=path,
        prc_program_name=name,
        prc_first_seen=now,
        prc_is_unknown=False,
        prc_is_watched=False,
        prc_is_running=False,
        prc_is_dangerous=False,
        prc_blocked=False,
    )
    
    return prc

def add_event(pri_id, pev_type, pev_timestamp):
    db.init(get_db_path())
    
    # Retry logic pour gérer les locks temporaires
    max_retries = 3
    for attempt in range(max_retries):
        try:
            event = ProcessEvent.create(
                pri_id=pri_id,
                pev_type=pev_type.value if hasattr(pev_type, 'value') else str(pev_type),
                pev_timestamp=pev_timestamp
            )
            return event
        except OperationalError as e:
            if attempt < max_retries - 1:
                logger.warning(f"Database locked, retry {attempt + 1}/{max_retries}")
                import time
                time.sleep(0.1 * (attempt + 1))  # Backoff exponentiel
            else:
                logger.error(f"Failed to add event after {max_retries} attempts: {e}")
                raise

def add_events_batch(events_data):
    """Ajoute plusieurs événements en une seule transaction pour de meilleures performances.
    
    Args:
        events_data: Liste de dicts avec les clés: pri_id, pev_type, pev_timestamp
    """
    db.init(get_db_path())
    
    if not events_data:
        return
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with db.atomic():
                ProcessEvent.insert_many(events_data).execute()
            return
        except OperationalError as e:
            if attempt < max_retries - 1:
                logger.warning(f"Database locked during batch insert, retry {attempt + 1}/{max_retries}")
                import time
                time.sleep(0.1 * (attempt + 1))
            else:
                logger.error(f"Failed to batch insert events after {max_retries} attempts: {e}")
                raise

def set_process_blocked(prc_id, blocked):
    db.init(get_db_path())
    Process.update(prc_blocked=blocked).where(Process.prc_id == prc_id).execute()

def set_process_dangerous(prc_id, dangerous):
    db.init(get_db_path())
    Process.update(prc_is_dangerous=dangerous).where(Process.prc_id == prc_id).execute()

def set_process_watched(prc_id, watched):
    db.init(get_db_path())
    Process.update(prc_is_watched=watched).where(Process.prc_id == prc_id).execute()

def set_process_watched_dangerous(prc_id):
    db.init(get_db_path())
    Process.update(prc_is_watched=True, prc_is_dangerous=True).where(Process.prc_id == prc_id).execute()
    return Process.get(Process.prc_id == prc_id)

def get_non_populate_process_instance():
    db.init(get_db_path())
    return ProcessInstance.select().where(ProcessInstance.pri_populated == False)

def set_process_instance_populated(instance_id, signed_by, signed_thumbprint, signed_is_ev, owner):
    db.init(get_db_path())
    ProcessInstance.update(
        pri_signed_by=signed_by,
        pri_signed_thumbprint=signed_thumbprint,
        pri_signed_is_ev=signed_is_ev,
        pri_owner=owner,
        pri_populated=True
    ).where(ProcessInstance.pri_id == instance_id).execute()
    
def add_process_instance(prc_id, pri_timestamp, pri_pid, pri_ppid, pri_start_time,  pri_has_window, pri_weird_path):
    pri = ProcessInstance.create(
        prc_id=prc_id,
        pri_timestamp=pri_timestamp,
        pri_pid=pri_pid,
        pri_ppid=pri_ppid,
        pri_start_time=pri_start_time,
        pri_owner="",
        pri_has_window=pri_has_window,
        pri_signed=False,
        pri_signed_by="",
        pri_signed_thumbprint="",
        pri_signed_is_ev=False,
        pri_weird_path=pri_weird_path,
        pri_is_running=True,
        pri_score=0,
        pri_score_computed=False,
        pri_populated=False
    )
    return pri

def get_not_compute_process_instance():
    db.init(get_db_path())
    return ProcessInstance.select().where(ProcessInstance.pri_score_computed == False)

def update_process_instance_score(pri_id, score):
    db.init(get_db_path())
    ProcessInstance.update(pri_score=score, pri_score_computed=True).where(ProcessInstance.pri_id == pri_id).execute()
    
def get_process_instance_by_pid(pid, start_time):
    db.init(get_db_path())
    try:
        return ProcessInstance.get((ProcessInstance.pri_pid == pid) & (ProcessInstance.pri_start_time == start_time))
    except DoesNotExist:
        return None
    
def stop_process_instance(pri_id):
    db.init(get_db_path())
    ProcessInstance.update(pri_is_running=False).where(ProcessInstance.pri_id == pri_id).execute()

def get_running_instances_without_score():
    db.init(get_db_path())
    return ProcessInstance.select().where((ProcessInstance.pri_is_running == True) & (ProcessInstance.pri_score_computed == False))

def get_running_instances():
    db.init(get_db_path())
    return ProcessInstance.select().where((ProcessInstance.pri_is_running == True))

def add_or_update_config(cfg_key, cfg_value):
    db.init(get_db_path())
    now = datetime.datetime.now()
    
    try:
        config = Config.get(Config.cfg_key == cfg_key)
        config.cfg_value = cfg_value
        config.created = now
        config.save()
        cfg_id = config.cfg_id
    except DoesNotExist:
        config = Config.create(
            cfg_key=cfg_key,
            cfg_value=cfg_value,
            created=now
        )
        cfg_id = config.cfg_id
    
    return cfg_id