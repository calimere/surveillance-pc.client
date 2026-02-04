import enum

class EQueueType(enum.Enum):
    NOTIFICATION_ADD = "notification_add"
    EXE_EVENT_ADD = "exe_event_add"
    EXE_LIST_ADD = "exe_list_add"
    CONFIG_ADD = "config_add"
    