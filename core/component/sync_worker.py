"""
🔄 Synchronisation périodique base locale → base distante
Gère la synchronisation des enregistrements non synchronisés
"""

import threading
import time
import datetime
import json
from typing import List, Dict, Any
from core.component.logger import get_logger
from core.business.db import (
    Process,
    ProcessInstance, 
    ProcessEvent,
    Config,
    Queue
)
from core.business.mqtt_publish import (
    publish_process_add,
    publish_process_event,
    publish_notification
)
from core.business.api_publish import (
    add_processes,
    add_process_instances
)
from core.component.mqtt_client import get_mqtt_status, MQTTStatus
from core.enum.EExeEventType import EExeEventType

logger = get_logger("sync_worker")


class SyncWorker(threading.Thread):
    """Worker de synchronisation en arrière-plan"""
    
    def __init__(self, sync_interval: int = 30):
        super().__init__(daemon=True, name="SyncWorker")
        self.running = True
        self.sync_interval = sync_interval  # Intervalle en secondes
        self.last_sync = datetime.datetime.now()
        self.error_backoff = {}  # Backoff pour retry intelligent
        
        # Statistiques de synchronisation
        self.stats = {
            "total_synced": 0,
            "total_errors": 0,
            "last_batch_size": 0,
            "last_sync_duration": 0
        }
    
    def run(self):
        """Boucle principale de synchronisation"""
        logger.info("🔄 Sync Worker démarré")
        
        while self.running:
            try:
                start_time = time.time()
                
                # Synchronisation des différentes tables
                total_synced = self._sync_all_tables()
                
                # Mise à jour des stats
                duration = time.time() - start_time
                self.stats["last_sync_duration"] = duration
                self.stats["last_batch_size"] = total_synced
                self.stats["total_synced"] += total_synced
                self.last_sync = datetime.datetime.now()
                
                if total_synced > 0:
                    logger.info(f"✅ {total_synced} enregistrements synchronisés en {duration:.2f}s")
                    
                # Attente jusqu'au prochain cycle
                time.sleep(self.sync_interval)
                
            except Exception as e:
                logger.error(f"❌ Erreur dans sync worker: {e}")
                self.stats["total_errors"] += 1
                time.sleep(5)  # Attente courte en cas d'erreur
    
    def _sync_all_tables(self) -> int:
        """Synchronise toutes les tables avec données non synchronisées"""
        total_synced = 0
        
        # Ordre de priorité : Events > Instances > Processes
        # Les événements sont plus urgents que les métadonnées
        total_synced += self._sync_process_events()
        total_synced += self._sync_process_instances()
        total_synced += self._sync_processes()
        total_synced += self._sync_queue_messages()
        
        return total_synced
    
    def _sync_processes(self) -> int:
        """Synchronise les processus non synchronisés"""
        try:
            # Récupérer processus non syncs ou en erreur
            unsync_processes = list(Process.select().where(
                (Process.sync_status == 0) | (Process.sync_status == 2)
            ).limit(50))  # Limiter le batch pour éviter surcharge
            
            if not unsync_processes:
                return 0
                
            logger.debug(f"🔄 Synchronisation de {len(unsync_processes)} processus...")
            
            synced_count = 0
            for process in unsync_processes:
                if self._should_retry(f"process_{process.prc_id}"):
                    try:
                        # Tenter synchronisation via MQTT ou API
                        if self._sync_single_process(process):
                            # Marquer comme synchronisé
                            process.sync_status = 1
                            process.sync_timestamp = datetime.datetime.now()
                            process.save()
                            synced_count += 1
                            self._clear_backoff(f"process_{process.prc_id}")
                        else:
                            # Marquer erreur et programmer retry
                            process.sync_status = 2
                            process.sync_timestamp = datetime.datetime.now()
                            process.save()
                            self._add_backoff(f"process_{process.prc_id}")
                            
                    except Exception as e:
                        logger.error(f"❌ Erreur sync processus {process.prc_id}: {e}")
                        process.sync_status = 2
                        process.sync_timestamp = datetime.datetime.now()
                        process.save()
                        self._add_backoff(f"process_{process.prc_id}")
            
            return synced_count
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la sync des processus: {e}")
            return 0
    
    def _sync_process_instances(self) -> int:
        """Synchronise les instances non synchronisées"""
        try:
            unsync_instances = list(ProcessInstance.select().where(
                (ProcessInstance.sync_status == 0) | (ProcessInstance.sync_status == 2)
            ).limit(50))
            
            if not unsync_instances:
                return 0
                
            logger.debug(f"🔄 Synchronisation de {len(unsync_instances)} instances...")
            
            synced_count = 0
            for instance in unsync_instances:
                if self._should_retry(f"instance_{instance.pri_id}"):
                    try:
                        if self._sync_single_instance(instance):
                            instance.sync_status = 1
                            instance.sync_timestamp = datetime.datetime.now()
                            instance.save()
                            synced_count += 1
                            self._clear_backoff(f"instance_{instance.pri_id}")
                        else:
                            instance.sync_status = 2
                            instance.sync_timestamp = datetime.datetime.now()
                            instance.save()
                            self._add_backoff(f"instance_{instance.pri_id}")
                            
                    except Exception as e:
                        logger.error(f"❌ Erreur sync instance {instance.pri_id}: {e}")
                        instance.sync_status = 2
                        instance.sync_timestamp = datetime.datetime.now()
                        instance.save()
                        self._add_backoff(f"instance_{instance.pri_id}")
            
            return synced_count
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la sync des instances: {e}")
            return 0
    
    def _sync_process_events(self) -> int:
        """Synchronise les événements non synchronisés"""
        try:
            unsync_events = list(ProcessEvent.select().where(
                (ProcessEvent.sync_status == 0) | (ProcessEvent.sync_status == 2)
            ).limit(100))  # Plus d'événements car ils sont plus petits
            
            if not unsync_events:
                return 0
                
            logger.debug(f"🔄 Synchronisation de {len(unsync_events)} événements...")
            
            synced_count = 0
            for event in unsync_events:
                if self._should_retry(f"event_{event.pev_id}"):
                    try:
                        if self._sync_single_event(event):
                            event.sync_status = 1
                            event.sync_timestamp = datetime.datetime.now()
                            event.save()
                            synced_count += 1
                            self._clear_backoff(f"event_{event.pev_id}")
                        else:
                            event.sync_status = 2
                            event.sync_timestamp = datetime.datetime.now()
                            event.save()
                            self._add_backoff(f"event_{event.pev_id}")
                            
                    except Exception as e:
                        logger.error(f"❌ Erreur sync événement {event.pev_id}: {e}")
                        event.sync_status = 2
                        event.sync_timestamp = datetime.datetime.now()
                        event.save()
                        self._add_backoff(f"event_{event.pev_id}")
            
            return synced_count
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la sync des événements: {e}")
            return 0
    
    def _sync_queue_messages(self) -> int:
        """Synchronise les messages de queue en attente"""
        try:
            # Queue utilise un statut différent (pending/sent/failed)
            unsync_queue = list(Queue.select().where(
                (Queue.sync_status == 0) | (Queue.sync_status == 2)
            ).limit(30))
            
            if not unsync_queue:
                return 0
                
            logger.debug(f"🔄 Synchronisation de {len(unsync_queue)} messages queue...")
            
            synced_count = 0
            for queue_msg in unsync_queue:
                if self._should_retry(f"queue_{queue_msg.que_id}"):
                    try:
                        if self._sync_single_queue_message(queue_msg):
                            queue_msg.sync_status = 1
                            queue_msg.sync_timestamp = datetime.datetime.now()
                            queue_msg.save()
                            synced_count += 1
                            self._clear_backoff(f"queue_{queue_msg.que_id}")
                        else:
                            queue_msg.sync_status = 2
                            queue_msg.sync_timestamp = datetime.datetime.now()
                            queue_msg.save()
                            self._add_backoff(f"queue_{queue_msg.que_id}")
                            
                    except Exception as e:
                        logger.error(f"❌ Erreur sync queue {queue_msg.que_id}: {e}")
                        queue_msg.sync_status = 2
                        queue_msg.sync_timestamp = datetime.datetime.now()
                        queue_msg.save()
                        self._add_backoff(f"queue_{queue_msg.que_id}")
            
            return synced_count
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la sync de la queue: {e}")
            return 0
    
    def _sync_single_process(self, process: Process) -> bool:
        """Synchronise un processus individuel"""
        try:
            # Utiliser MQTT si disponible, sinon HTTP
            if get_mqtt_status() == MQTTStatus.CONNECTED:
                publish_process_add(process)
                return True
            else:
                # Fallback HTTP
                add_processes([process])
                return True
                
        except Exception as e:
            logger.debug(f"Échec sync processus {process.prc_id}: {e}")
            return False
    
    def _sync_single_instance(self, instance: ProcessInstance) -> bool:
        """Synchronise une instance individuelle"""
        try:
            if get_mqtt_status() == MQTTStatus.CONNECTED:
                # Pour MQTT, utiliser les notifications existantes
                return True  # À implémenter selon vos besoins MQTT
            else:
                # Fallback HTTP
                add_process_instances([instance])
                return True
                
        except Exception as e:
            logger.debug(f"Échec sync instance {instance.pri_id}: {e}")
            return False
    
    def _sync_single_event(self, event: ProcessEvent) -> bool:
        """Synchronise un événement individuel"""
        try:
            if get_mqtt_status() == MQTTStatus.CONNECTED:
                # Convertir le type d'événement
                event_type = EExeEventType(event.pev_type) if event.pev_type else EExeEventType.START
                publish_process_event(event.pri_id, event_type)
                return True
            else:
                # Pour HTTP, on pourrait avoir besoin d'une API spécifique
                return True  # À implémenter selon vos besoins
                
        except Exception as e:
            logger.debug(f"Échec sync événement {event.pev_id}: {e}")
            return False
    
    def _sync_single_queue_message(self, queue_msg: Queue) -> bool:
        """Synchronise un message de queue individuel"""
        try:
            # Traiter selon le type de message
            queue_data = json.loads(queue_msg.que_data)
            
            if queue_msg.que_type == "notification":
                if get_mqtt_status() == MQTTStatus.CONNECTED:
                    publish_notification(queue_data.get("exe_id", 0), queue_data.get("message", ""))
                    return True
            
            # Autres types de messages à implémenter selon vos besoins
            return True
                
        except Exception as e:
            logger.debug(f"Échec sync queue {queue_msg.que_id}: {e}")
            return False
    
    def _should_retry(self, key: str) -> bool:
        """Vérifie si on peut retry un élément selon backoff exponentiel"""
        if key not in self.error_backoff:
            return True
            
        retry_after = self.error_backoff[key]["retry_after"]
        return datetime.datetime.now() >= retry_after
    
    def _add_backoff(self, key: str):
        """Ajoute ou augmente le backoff pour un élément en erreur"""
        if key not in self.error_backoff:
            self.error_backoff[key] = {"attempts": 1, "retry_after": datetime.datetime.now() + datetime.timedelta(minutes=1)}
        else:
            attempts = self.error_backoff[key]["attempts"] + 1
            # Backoff exponentiel : 1min, 2min, 4min, 8min, puis max 30min
            backoff_minutes = min(2 ** (attempts - 1), 30)
            self.error_backoff[key] = {
                "attempts": attempts,
                "retry_after": datetime.datetime.now() + datetime.timedelta(minutes=backoff_minutes)
            }
    
    def _clear_backoff(self, key: str):
        """Efface le backoff après succès"""
        if key in self.error_backoff:
            del self.error_backoff[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de synchronisation"""
        unsync_counts = self._count_unsync_records()
        
        return {
            **self.stats,
            "last_sync": self.last_sync,
            "unsync_records": unsync_counts,
            "error_backoffs": len(self.error_backoff)
        }
    
    def _count_unsync_records(self) -> Dict[str, int]:
        """Compte les enregistrements non synchronisés par table"""
        try:
            return {
                "processes": Process.select().where((Process.sync_status == 0) | (Process.sync_status == 2)).count(),
                "instances": ProcessInstance.select().where((ProcessInstance.sync_status == 0) | (ProcessInstance.sync_status == 2)).count(),
                "events": ProcessEvent.select().where((ProcessEvent.sync_status == 0) | (ProcessEvent.sync_status == 2)).count(),
                "queue": Queue.select().where((Queue.sync_status == 0) | (Queue.sync_status == 2)).count()
            }
        except Exception as e:
            logger.error(f"Erreur comptage records non-sync: {e}")
            return {}
    
    def force_sync(self):
        """Force une synchronisation immédiate"""
        logger.info("🔄 Synchronisation forcée demandée")
        self._sync_all_tables()
    
    def stop(self):
        """Arrête proprement le worker"""
        logger.info("🛑 Arrêt du Sync Worker")
        self.running = False


# Instance globale
_sync_worker_instance = None


def get_sync_worker(sync_interval: int = 30) -> SyncWorker:
    """Récupère l'instance unique du sync worker"""
    global _sync_worker_instance
    
    if _sync_worker_instance is None:
        logger.info("🔄 Initialisation du Sync Worker...")
        _sync_worker_instance = SyncWorker(sync_interval)
        _sync_worker_instance.start()
        logger.info("🔄 Sync Worker démarré")
    
    return _sync_worker_instance


def stop_sync_worker():
    """Arrête proprement le sync worker"""
    global _sync_worker_instance
    
    if _sync_worker_instance is not None:
        _sync_worker_instance.stop()
        _sync_worker_instance.join(timeout=5)
        _sync_worker_instance = None
        logger.info("🔄 Sync Worker arrêté")


def force_sync():
    """Force une synchronisation immédiate"""
    worker = get_sync_worker()
    worker.force_sync()


def get_sync_stats() -> Dict[str, Any]:
    """Retourne les stats de synchronisation"""
    if _sync_worker_instance:
        return _sync_worker_instance.get_stats()
    else:
        return {"status": "not_running"}


def mark_for_resync(table_name: str, record_id: int = None):
    """Marque un élément ou une table pour re-synchronisation"""
    try:
        if table_name == "processes":
            query = Process.update(sync_status=0, sync_timestamp=None)
            if record_id:
                query = query.where(Process.prc_id == record_id)
            count = query.execute()
            
        elif table_name == "instances":
            query = ProcessInstance.update(sync_status=0, sync_timestamp=None)
            if record_id:
                query = query.where(ProcessInstance.pri_id == record_id)
            count = query.execute()
            
        elif table_name == "events":
            query = ProcessEvent.update(sync_status=0, sync_timestamp=None)
            if record_id:
                query = query.where(ProcessEvent.pev_id == record_id)
            count = query.execute()
            
        elif table_name == "queue":
            query = Queue.update(sync_status=0, sync_timestamp=None)
            if record_id:
                query = query.where(Queue.que_id == record_id)
            count = query.execute()
        else:
            logger.error(f"Table inconnue: {table_name}")
            return False
            
        logger.info(f"✅ {count} enregistrements marqués pour re-synchronisation dans {table_name}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur marquage re-sync {table_name}: {e}")
        return False


def reset_sync_errors():
    """Remet tous les enregistrements en erreur (sync_status=2) à non-synchronisé (sync_status=0)"""
    try:
        tables = [Process, ProcessInstance, ProcessEvent, Queue]
        total_reset = 0
        
        for table in tables:
            count = table.update(
                sync_status=0,
                sync_timestamp=None
            ).where(table.sync_status == 2).execute()
            
            if count > 0:
                logger.info(f"🔄 {count} enregistrements en erreur reset dans {table._meta.table_name}")
                total_reset += count
        
        if total_reset > 0:
            logger.info(f"✅ {total_reset} enregistrements total remis en attente de synchronisation")
        
        return total_reset
        
    except Exception as e:
        logger.error(f"❌ Erreur reset sync errors: {e}")
        return 0