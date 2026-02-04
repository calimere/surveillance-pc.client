from enum import Enum


class EExeEventType(Enum):
    START = "start"
    STOP = "stop"
    HASH_CHANGE = "hash_change"
    SIGNATURE_CHANGE = "signature_change"