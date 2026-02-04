import os
import datetime
from business.EExeEventType import EExeEventType
from core.config import get_app_data_dir, get_db_path
from peewee import *
from core.logger import get_logger

logger = get_logger("db")

db = SqliteDatabase(None)

class BaseModel(Model):
    class Meta:
        database = db

class ExeList(BaseModel):
    exe_id = AutoField(primary_key=True)
    exe_name = TextField()
    exe_path = TextField()
    exe_program_name = TextField()
    exe_first_seen = DateTimeField()
    exe_last_seen = DateTimeField()
    exe_is_unknown = BooleanField(default=False)
    exe_is_watched = BooleanField(default=False)
    exe_launched = BooleanField(default=False)
    exe_is_dangerous = BooleanField(default=False)
    exe_blocked = BooleanField(default=False)
    exe_icon = BlobField(null=True)
    exe_is_system = BooleanField(default=False)
    exe_hash = TextField(null=True)
    exe_signed_by = TextField(null=True)

    class Meta:
        table_name = 'exe_list'

class ExeEvent(BaseModel):
    eev_id = AutoField(primary_key=True)
    exe = ForeignKeyField(ExeList, backref='events', column_name='exe_id')
    eev_type = TextField()
    eev_timestamp = DateTimeField()

    class Meta:
        table_name = 'exe_event'

class Config(BaseModel):
    cfg_id = AutoField(primary_key=True)
    cfg_key = TextField()
    cfg_value = TextField()
    created = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = 'config'

class Notification(BaseModel):
    ntf_id = AutoField(primary_key=True)
    ntf_type = TextField() # type of alarm (e.g., "exe_launched", "exe_blocked", "hash_changed", etc.)
    ntf_message = TextField() # JSON data related to the alarm
    created = DateTimeField(default=datetime.datetime.now)
    exe_id = IntegerField(null=True)

    class Meta:
        table_name = 'notification'

class Queue(BaseModel):
    que_id = AutoField(primary_key=True)
    que_type = TextField() # type of item to process (e.g., "exe_event", "exe_list", "alarms", etc.)
    que_data = TextField() # JSON data related to the item
    created = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = 'queue'

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
    db.create_tables([ExeList, ExeEvent, Config, Notification, Queue])
    db.close()
    
    logger.info(f"Base de données créée à {get_db_path()}.")

def add_notification(alarm_type, message, exe_id=None):
    db.init(get_db_path())
    notification = Notification.create(
        ntf_type=alarm_type,
        ntf_message=message,
        exe_id=exe_id,
        created=datetime.datetime.now()
    )
    return notification

def add_queue(queue_type, queue_data):
    db.init(get_db_path())
    queue_item = Queue.create(
        que_type=queue_type,
        que_data=queue_data,
        created=datetime.datetime.now()
    )
    return queue_item

def get_all_exe():
    db.init(get_db_path())
    query = ExeList.select(ExeList.exe_name, ExeList.exe_path, ExeList.exe_id, 
                            ExeList.exe_launched, ExeList.exe_is_unknown, 
                            ExeList.exe_is_dangerous, ExeList.exe_blocked)
    
    return [{
        "exe_name": exe.exe_name,
        "exe_path": exe.exe_path,
        "exe_id": exe.exe_id,
        "exe_launched": exe.exe_launched,
        "exe_is_unknown": exe.exe_is_unknown,
        "exe_is_dangerous": exe.exe_is_dangerous,
        "exe_blocked": exe.exe_blocked,
    } for exe in query]

def get_all_events():
    db.init(get_db_path())
    query = ExeEvent.select()
    
    return [{
        "eev_id": event.eev_id,
        "exe_id": event.exe_id,
        "eev_type": event.eev_type,
        "eev_timestamp": event.eev_timestamp
    } for event in query]

def get_known_watched_processes():
    db.init(get_db_path())
    return ExeList.select().where((ExeList.exe_is_watched == True) & (ExeList.exe_is_unknown == False))

def get_known_blocked_processes():
    db.init(get_db_path())
    return ExeList.select().where((ExeList.exe_blocked == True) & (ExeList.exe_is_unknown == False))

def get_unknown_processes():
    db.init(get_db_path())
    return ExeList.select().where(ExeList.exe_is_unknown == True)

def update_launched_status(exe_id, launched):
    db.init(get_db_path())
    ExeList.update(exe_launched=launched).where(ExeList.exe_id == exe_id).execute()

def get_process_by_name(name, path):
    db.init(get_db_path())
    try:
        exe = ExeList.get((ExeList.exe_name == name) & (ExeList.exe_path == path))
        return exe.exe_id
    except DoesNotExist:
        return None

def add_or_update_unknown_executable(name, path):
    db.init(get_db_path())
    now = datetime.datetime.now()
    
    try:
        exe = ExeList.get((ExeList.exe_name == name) & (ExeList.exe_path == path))
        exe.exe_last_seen = now
        exe.save()
        exe_id = exe.exe_id
    except DoesNotExist:
        logger.info(f"Nouvel exécutable inconnu détecté : {name}")
        exe = ExeList.create(
            exe_name=name,
            exe_path=path,
            exe_program_name=name,
            exe_first_seen=now,
            exe_last_seen=now,
            exe_is_unknown=True,
            exe_is_watched=True,
            exe_launched=False,
            exe_is_dangerous=False,
            exe_blocked=False
        )
        exe_id = exe.exe_id
    
    return exe_id

def get_exe_by_name_path(name, path):
    db.init(get_db_path())
    try:
        return ExeList.get((ExeList.exe_name == name) & (ExeList.exe_path == path))
    except DoesNotExist:
        return None

def add_executable(name, path, exe_hash, exe_signed_by, exe_icon, exe_is_system):
    db.init(get_db_path())
    now = datetime.datetime.now()
    
    logger.info(f"Nouvel exécutable détecté : {name}")
    exe = ExeList.create(
        exe_name=name,
        exe_path=path,
        exe_program_name=name,
        exe_first_seen=now,
        exe_last_seen=now,
        exe_is_unknown=False,
        exe_is_watched=False,
        exe_launched=False,
        exe_is_dangerous=False,
        exe_blocked=False,
        exe_hash=exe_hash,
        exe_signed_by=exe_signed_by,
        exe_icon=exe_icon,
        exe_is_system=exe_is_system
    )
    
    return exe

def update_executable(exe_id, name, path, exe_hash, exe_signed_by, exe_icon, exe_is_system):
    db.init(get_db_path())
    now = datetime.datetime.now()
    
    ExeList.update(
        exe_name=name,
        exe_path=path,
        exe_last_seen=now,
        exe_hash=exe_hash,
        exe_signed_by=exe_signed_by,
        exe_icon=exe_icon,
        exe_is_system=exe_is_system
    ).where(ExeList.exe_id == exe_id).execute()

def add_or_update_executable(name, path, exe_hash, exe_signed_by, exe_icon, exe_is_system):
    db.init(get_db_path())
    now = datetime.datetime.now()
    
    try:
        exe = ExeList.get((ExeList.exe_name == name) & (ExeList.exe_path == path))
        exe.exe_last_seen = now
        exe.exe_hash = exe_hash
        exe.exe_signed_by = exe_signed_by
        exe.exe_icon = exe_icon
        exe.exe_is_system = exe_is_system
        exe.save()
        exe_id = exe.exe_id
    except DoesNotExist:
        logger.info(f"Nouvel exécutable détecté : {name}")
        exe = ExeList.create(
            exe_name=name,
            exe_path=path,
            exe_program_name=name,
            exe_first_seen=now,
            exe_last_seen=now,
            exe_is_unknown=False,
            exe_is_watched=False,
            exe_launched=False,
            exe_is_dangerous=False,
            exe_blocked=False,
            exe_hash=exe_hash,
            exe_signed_by=exe_signed_by,
            exe_icon=exe_icon,
            exe_is_system=exe_is_system
        )
        exe_id = exe.exe_id
    
    return exe_id

def add_event(exe_id, event_type):
    db.init(get_db_path())
    event = ExeEvent.create(
        exe=exe_id,
        eev_type=event_type,
        eev_timestamp=datetime.datetime.now()
    )
    return event

def set_executable_blocked(exe_id, blocked):
    db.init(get_db_path())
    ExeList.update(exe_blocked=blocked).where(ExeList.exe_id == exe_id).execute()

def set_executable_dangerous(exe_id, dangerous):
    db.init(get_db_path())
    ExeList.update(exe_is_dangerous=dangerous).where(ExeList.exe_id == exe_id).execute()

def set_executable_watched(exe_id, watched):
    db.init(get_db_path())
    ExeList.update(exe_is_watched=watched).where(ExeList.exe_id == exe_id).execute()

def set_executable_watched_dangerous(exe_id):
    db.init(get_db_path())
    ExeList.update(exe_is_watched=True,exe_is_dangerous=True).where(ExeList.exe_id == exe_id).execute()
    return ExeList.get(ExeList.exe_id == exe_id)

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