import json
import requests
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from core.component.logger import get_logger
from core.component.config import config
from core.component.authentication import generate_client_id

logger = get_logger("api_publish")
API_BASE_URL = config.get("api", "url", fallback="http://localhost:5000/api")
_HEADERS = {"Content-Type": "application/json"}


def _cid() -> str:
    return generate_client_id()


def _generate_dedup_hash(client_id: str, local_id: int, obj_type: str) -> str:
    """Génère un hash de déduplication basé sur client_id + local_id + type d'objet."""
    content = f"{client_id}:{local_id}:{obj_type}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


def _serialize_object_data(obj: dict) -> dict:
    """Convertit les objets datetime en chaînes ISO pour la sérialisation JSON.
    S'assure que l'ID local SQLite est préservé pour éviter les doublons côté serveur."""
    result = {}
    for k, v in obj.items():
        if isinstance(v, (datetime, date)):
            result[k] = v.isoformat()
        else:
            result[k] = v
    
    # Validation : s'assurer qu'un ID local existe pour la déduplication
    if 'id' not in result or result['id'] is None:
        logger.warning("⚠️ Objet sans ID local - risque de duplication côté serveur")
    
    return result


def add_processes(processes: list) -> bool:
    """POST /api/processes/add
    
    Stratégie Anti-Duplication:
    - Garde les IDs SQLite locaux (envoyés dans __data__)  
    - Serveur ajoute son propre ID unique 
    - Serveur utilise contrainte unique sur (client_id, local_id)
    - Hash de déduplication ajouté pour sécurité supplémentaire
    """
    try:
        client_id = _cid()
        serialized_processes = []
        
        for p in processes:
            data = _serialize_object_data(p.__data__)
            # Ajouter hash de déduplication
            if 'id' in data:
                data['dedup_hash'] = _generate_dedup_hash(client_id, data['id'], 'process')
            serialized_processes.append(data)
        
        payload = {
            "client_id": client_id,
            "processes": serialized_processes,
        }
        r = requests.post(
            f"{API_BASE_URL}/processes/add",
            json=payload,
            headers=_HEADERS,
            timeout=5,
        )
        if r.status_code == 200:
            logger.info(f"✅ {len(processes)} processus envoyés (IDs locaux préservés)")
            return True
        logger.warning(f"⚠️ /processes/add → HTTP {r.status_code}")
        return False
    except Exception as e:
        logger.error(f"❌ add_processes: {e}")
        return False


def add_process_instances(instances: list) -> bool:
    """POST /api/process_instances/add
    
    Stratégie Anti-Duplication:
    - Préserve IDs SQLite locaux + ajoute hash de déduplication
    - Serveur détecte doublons via (client_id, local_id)
    """
    try:
        client_id = _cid()
        serialized_instances = []
        
        for i in instances:
            data = _serialize_object_data(i.__data__)
            # Ajouter hash de déduplication
            if 'id' in data:
                data['dedup_hash'] = _generate_dedup_hash(client_id, data['id'], 'instance')
            serialized_instances.append(data)
        
        payload = {
            "client_id": client_id,
            "instances": serialized_instances,
        }
        r = requests.post(
            f"{API_BASE_URL}/process_instances/add",
            json=payload,
            headers=_HEADERS,
            timeout=5,
        )
        if r.status_code == 200:
            logger.info(f"✅ {len(instances)} instances envoyées (anti-duplication)")
            return True
        logger.warning(f"⚠️ /process_instances/add → HTTP {r.status_code}")
        return False
    except Exception as e:
        logger.error(f"❌ add_process_instances: {e}")
        return False


def add_process_events(events: list) -> bool:
    """POST /api/process_events/add
    
    Stratégie Anti-Duplication:
    - Préserve IDs SQLite locaux + ajoute hash de déduplication
    - Serveur détecte doublons via (client_id, local_id)
    """
    try:
        client_id = _cid()
        serialized_events = []
        
        for e in events:
            data = _serialize_object_data(e.__data__)
            # Ajouter hash de déduplication
            if 'id' in data:
                data['dedup_hash'] = _generate_dedup_hash(client_id, data['id'], 'event')
            serialized_events.append(data)
        
        payload = {
            "client_id": client_id,
            "events": serialized_events,
        }
        r = requests.post(
            f"{API_BASE_URL}/process_events/add",
            json=payload,
            headers=_HEADERS,
            timeout=5,
        )
        if r.status_code == 200:
            logger.info(f"✅ {len(events)} événements envoyés (anti-duplication)")
            return True
        
        logger.warning(f"⚠️ /process_events/add → HTTP {r.status_code} | Body: {r.text}")
        return False
    except Exception as e:
        logger.error(f"❌ add_process_events: {e}")
        return False


def add_security_alerts(alerts: list) -> bool:
    """POST /api/security/alerts
    
    Stratégie Anti-Duplication:
    - Préserve IDs SQLite locaux + ajoute hash de déduplication  
    - Serveur détecte doublons via (client_id, local_id)
    """
    try:
        client_id = _cid()
        serialized_alerts = []
        
        for a in alerts:
            data = _serialize_object_data(a.__data__)
            # Ajouter hash de déduplication
            if 'id' in data:
                data['dedup_hash'] = _generate_dedup_hash(client_id, data['id'], 'alert')
            serialized_alerts.append(data)
        
        payload = {
            "client_id": client_id,
            "alerts": serialized_alerts,
        }
        r = requests.post(
            f"{API_BASE_URL}/security/alerts",
            json=payload,
            headers=_HEADERS,
            timeout=5,
        )
        if r.status_code == 200:
            logger.info(f"✅ {len(alerts)} alertes de sécurité envoyées (anti-duplication)")
            return True
        logger.warning(f"⚠️ /security/alerts → HTTP {r.status_code}")
        return False
    except Exception as e:
        logger.error(f"❌ add_security_alerts: {e}")
        return False


# ==================== SYNCHRONISATION BIDIRECTIONNELLE ====================

def get_server_changes_since(since_timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Récupère les changements serveur depuis un timestamp donné
    
    Returns:
        List of changes in format:
        {
            "table": "processes",
            "operation": "UPDATE|INSERT|DELETE", 
            "timestamp": "2026-04-27T10:30:00",
            "data": {...}
        }
    """
    try:
        params = {
            "client_id": _cid(),
        }
        
        if since_timestamp:
            params["since"] = since_timestamp.isoformat()
        
        r = requests.get(
            f"{API_BASE_URL}/sync/changes",
            params=params,
            headers=_HEADERS,
            timeout=10
        )
        
        if r.status_code == 200:
            response = r.json()
            changes = response.get("changes", [])
            logger.info(f"📥 {len(changes)} changements serveur récupérés")
            return changes
        elif r.status_code == 304:
            # Pas de changements
            logger.debug("📄 Aucun changement serveur")
            return []
        else:
            logger.warning(f"⚠️ /sync/changes → HTTP {r.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"❌ get_server_changes_since: {e}")
        return []


def notify_client_changes(changes: List[Dict[str, Any]]) -> bool:
    """Notifie le serveur des changements locaux pour éviter les conflits
    
    Args:
        changes: Liste des changements locaux format:
        {
            "table": "processes", 
            "local_id": 123,
            "operation": "UPDATE|INSERT|DELETE",
            "timestamp": "2026-04-27T10:30:00"
        }
    """
    try:
        payload = {
            "client_id": _cid(),
            "changes": changes,
        }
        
        r = requests.post(
            f"{API_BASE_URL}/sync/client_changes",
            json=payload,
            headers=_HEADERS,
            timeout=5
        )
        
        if r.status_code == 200:
            logger.info(f"📤 {len(changes)} changements client notifiés")
            return True
        else:
            logger.warning(f"⚠️ /sync/client_changes → HTTP {r.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ notify_client_changes: {e}")
        return False


def request_server_sync(sync_type: str = "incremental") -> bool:
    """Demande une synchronisation immédiate au serveur
    
    Args:
        sync_type: "incremental" ou "full"
    """
    try:
        payload = {
            "client_id": _cid(),
            "sync_type": sync_type,
            "request_timestamp": datetime.now().isoformat()
        }
        
        r = requests.post(
            f"{API_BASE_URL}/sync/request",
            json=payload,
            headers=_HEADERS,
            timeout=5
        )
        
        if r.status_code == 200:
            logger.info(f"🔄 Demande de sync {sync_type} acceptée par serveur")
            return True
        else:
            logger.warning(f"⚠️ /sync/request → HTTP {r.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ request_server_sync: {e}")
        return False


def get_server_timestamp() -> Optional[datetime]:
    """Récupère le timestamp serveur pour synchronisation d'horloge"""
    try:
        r = requests.get(
            f"{API_BASE_URL}/sync/timestamp",
            headers=_HEADERS,
            timeout=3
        )
        
        if r.status_code == 200:
            response = r.json()
            server_time = datetime.fromisoformat(response["timestamp"])
            logger.debug(f"🕐 Timestamp serveur: {server_time}")
            return server_time
        else:
            logger.warning(f"⚠️ /sync/timestamp → HTTP {r.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ get_server_timestamp: {e}")
        return None
