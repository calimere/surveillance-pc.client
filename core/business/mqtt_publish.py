from datetime import datetime
from core.enum.EAlarmType import EQueueType
from core.enum.EExeEventType import EExeEventType
from core.business.db import Process, add_queue
from core.component.mqtt_client import MQTTStatus, get_mqtt_status, publish
import json
from core.component.logger import get_logger

logger = get_logger("mqtt_publish")


# notifications
def publish_notification(exe_id: int, message: str):
    payload = {
        "exe_id": exe_id,
        "message": message,
        "timestamp": serialize_date(datetime.now()),
    }
    base_publish(EQueueType.NOTIFICATION_ADD, "notification/[client]/add", payload)


# region processus events
def publish_process_event(exe_id: int, event_type: EExeEventType):
    payload = {
        "exe_id": exe_id,
        "event_type": event_type.value
        if hasattr(event_type, "value")
        else str(event_type),
        "timestamp": serialize_date(datetime.now()),
    }
    base_publish(EQueueType.EXE_EVENT_ADD, "processus/[client]/event", payload)


# endregion processus events

# region process


def publish_process_add(exe_list: Process):
    payload = {
        "exe_list": exe_list.__dict__,
        "timestamp": serialize_date(datetime.now()),
    }

    base_publish(EQueueType.EXE_LIST_ADD, "processus/[client]/add", payload)


def publish_process_update(exe_list: Process):
    payload = {
        "exe_list": exe_list.__dict__,
        "timestamp": serialize_date(datetime.now()),
    }
    base_publish(EQueueType.EXE_LIST_ADD, "processus/[client]/update", payload)


# endregion process

# region process instance


# endregion process instance

# ----------------------------------------------#


# publie des messages MQTT si MQTT disponible, sinon ajoute dans la queue
def base_publish(type, topic, payload):
    json_payload = json.dumps(payload, default=str)

    if get_mqtt_status() != MQTTStatus.CONNECTED:
        logger.warning("⚠️ MQTT non connecté, impossible de publier le message.")
        add_queue(type, json_payload)
    else:
        publish(topic, json_payload)


def serialize_date(obj):
    if isinstance(obj, datetime):
        return obj.strftime("%d-%m-%Y %H:%M:%S.0000000")
    raise TypeError("Type non sérialisable")
