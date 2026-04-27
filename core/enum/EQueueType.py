import enum


class EQueueType(enum.Enum):
    SECURITY_ALERT = "security_alert"
    NOTIFICATION = "notification"
    HEARTBEAT = "heartbeat"
    PROCESS_EVENT = "process_event"
    PROCESS = "process"
    PROCESS_INSTANCE = "process_instance"
