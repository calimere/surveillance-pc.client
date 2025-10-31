from core.mqtt_client import publish
import json

def publish_executable_update(exe_id, exe_name, exe_path):
    payload = {
        "exe_id": exe_id,
        "exe_name": exe_name,
        "exe_path": exe_path,
    }

    publish("processus/[client]/update", json.dumps(payload))

def publish_executable_add(exe_name, exe_path):
    payload = {
        "exe_name": exe_name,
        "exe_path": exe_path,
    }

    publish("processus/[client]/add", json.dumps(payload))