import requests
from core.component.logger import get_logger
from component import config

logger = get_logger("mqtt_client")
API_BASE_URL = config.get("api", "url", fallback="http://localhost:5000/api")


def add_processes(processes: list):
    retour = requests.post(
        f"{API_BASE_URL}/processes/add",
        json={"processes": [proc.__dict__ for proc in processes]},
        timeout=5,
    )

    if retour and retour.status_code == 200:
        logger.info(f"{len(processes)} processus ajoutés via API")


def add_process_instances(instances: list):
    requests.post(
        f"{API_BASE_URL}/process_instances/add",
        json={"instances": [inst.__dict__ for inst in instances]},
        timeout=5,
    )
