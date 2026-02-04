import enum

class MQTTStatus(enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"