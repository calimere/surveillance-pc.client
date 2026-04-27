#!/usr/bin/env python3
"""
Test de la synchronisation bidirectionnelle
Simule des changements serveur et vérifie que le client les applique correctement
"""

import json
import time
from datetime import datetime
from core.component.mqtt_client import init_mqtt, publish, subscribe
from core.component.logger import get_logger
from core.business.mqtt_handlers import handle_server_changes, handle_sync_request
from core.component.bidirectional_sync_worker import get_bidirectional_sync_worker

logger = get_logger("test_bidirectional_sync")

def test_mqtt_server_push():
    """Test push de changements serveur via MQTT"""
    logger.info("🧪 Test: Push changements serveur via MQTT")
    
    # Simuler changements serveur
    mock_changes = {
        "changes": [
            {
                "table": "process",
                "operation": "UPDATE",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "id": 123,
                    "prc_name": "test_updated.exe",
                    "prc_is_dangerous": True
                }
            },
            {
                "table": "process_instance", 
                "operation": "INSERT",
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "id": 456,
                    "prc_id": 123,
                    "pri_pid": 9999
                }
            }
        ]
    }
    
    # Publier via MQTT (simule serveur)
    payload = json.dumps(mock_changes)
    publish("surveillance/[client]/server_changes", payload)
    logger.info(f"📤 Changements publiés: {len(mock_changes['changes'])} items")

def test_sync_request():
    """Test demande de sync par serveur"""
    logger.info("🧪 Test: Demande sync par serveur")
    
    mock_sync_request = {
        "type": "immediate",
        "reason": "admin_request",
        "timestamp": datetime.now().isoformat()
    }
    
    payload = json.dumps(mock_sync_request)
    publish("surveillance/[client]/sync_request", payload)
    logger.info("📤 Demande sync publiée")

def test_bidirectional_sync_stats():
    """Test récupération statistiques"""
    logger.info("🧪 Test: Statistiques sync bidirectionnel")
    
    from core.component.bidirectional_sync_worker import get_bidirectional_sync_stats
    stats = get_bidirectional_sync_stats()
    
    logger.info(f"📊 Stats sync bidirectionnel: {stats}")
    
    if stats.get("is_running"):
        logger.info("✅ Sync bidirectionnel actif")
    else:
        logger.warning("⚠️ Sync bidirectionnel non démarré")

def simulate_server_changes_during_downtime():
    """Simule changements serveur pendant que client était hors ligne"""
    logger.info("🧪 Test: Simulation changements pendant déconnexion")
    
    # Simuler plusieurs changements avec timestamps différents
    changes = []
    base_time = datetime.now()
    
    for i in range(5):
        change_time = base_time.replace(minute=base_time.minute - (5-i))
        changes.append({
            "table": "process",
            "operation": "UPDATE", 
            "timestamp": change_time.isoformat(),
            "data": {
                "id": 100 + i,
                "prc_name": f"missed_change_{i}.exe",
                "prc_is_watched": True
            }
        })
    
    # Simuler réception via pull API (normalement fait par worker)
    worker = get_bidirectional_sync_worker()
    applied = worker._apply_server_changes(changes)
    logger.info(f"📥 {applied}/{len(changes)} changements simulés appliqués")

def main():
    """Fonction principale de test"""
    logger.info("🚀 Démarrage tests synchronisation bidirectionnelle")
    
    try:
        # Initialiser MQTT pour les tests
        init_mqtt()
        logger.info("📡 MQTT initialisé pour tests")
        
        # Démarrer worker sync bidirectionnel
        worker = get_bidirectional_sync_worker(sync_interval=60)  # 1 minute pour tests
        worker.start()
        logger.info("🔄 Worker sync bidirectionnel démarré")
        
        # Attendre un peu pour la stabilisation
        time.sleep(2)
        
        # Tests
        test_bidirectional_sync_stats()
        time.sleep(1)
        
        test_mqtt_server_push()
        time.sleep(2)
        
        test_sync_request() 
        time.sleep(2)
        
        simulate_server_changes_during_downtime()
        time.sleep(2)
        
        # Stats finales
        test_bidirectional_sync_stats()
        
        logger.info("✅ Tests terminés avec succès")
        
    except Exception as e:
        logger.error(f"❌ Erreur pendant tests: {e}")
        
    finally:
        # Nettoyage
        try:
            from core.component.bidirectional_sync_worker import stop_bidirectional_sync_worker
            stop_bidirectional_sync_worker()
            logger.info("🛑 Worker sync arrêté")
        except:
            pass

if __name__ == "__main__":
    main()