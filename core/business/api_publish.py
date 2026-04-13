import requests
from core.component.logger import get_logger
from core.component.config import config
from core.component.authentication import generate_client_id

logger = get_logger("api_publish")
API_BASE_URL = config.get("api", "url", fallback="http://localhost:5000/api")
_HEADERS = {"Content-Type": "application/json"}


def _cid() -> str:
    return generate_client_id()


def add_processes(processes: list) -> bool:
    """POST /api/processes/add"""
    try:
        payload = {
            "client_id": _cid(),
            "processes": [p.__dict__ for p in processes],
        }
        r = requests.post(
            f"{API_BASE_URL}/processes/add", json=payload, headers=_HEADERS, timeout=5
        )
        if r.status_code == 200:
            logger.info(f"✅ {len(processes)} processus envoyés")
            return True
        logger.warning(f"⚠️ /processes/add → HTTP {r.status_code}")
        return False
    except Exception as e:
        logger.error(f"❌ add_processes: {e}")
        return False


def add_process_instances(instances: list) -> bool:
    """POST /api/process_instances/add"""
    try:
        payload = {
            "client_id": _cid(),
            "instances": [i.__dict__ for i in instances],
        }
        r = requests.post(
            f"{API_BASE_URL}/process_instances/add",
            json=payload,
            headers=_HEADERS,
            timeout=5,
        )
        if r.status_code == 200:
            logger.info(f"✅ {len(instances)} instances envoyées")
            return True
        logger.warning(f"⚠️ /process_instances/add → HTTP {r.status_code}")
        return False
    except Exception as e:
        logger.error(f"❌ add_process_instances: {e}")
        return False


def add_process_events(events: list) -> bool:
    """POST /api/process_events/add"""
    try:
        payload = {
            "client_id": _cid(),
            "events": [e.__dict__ for e in events],
        }
        r = requests.post(
            f"{API_BASE_URL}/process_events/add",
            json=payload,
            headers=_HEADERS,
            timeout=5,
        )
        if r.status_code == 200:
            logger.info(f"✅ {len(events)} événements envoyés")
            return True
        logger.warning(f"⚠️ /process_events/add → HTTP {r.status_code}")
        return False
    except Exception as e:
        logger.error(f"❌ add_process_events: {e}")
        return False
