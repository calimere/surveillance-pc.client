import queue
from random import *
import threading
import time
import uuid
from datetime import datetime
import psutil
from core.component.logger import get_logger
from core.component.config import config
import requests
from core.business.db import add_queue_with_tracking
from core.business.db import get_pending_queue_messages
from core.business.db import update_queue_status
from core.business.db import cleanup_old_queue_messages

from core.component.mqtt_client import publish
from core.component.mqtt_client import get_mqtt_status, MQTTStatus
from core.component.mqtt_client import ping


"""
🧠 Décisions autonomes : MQTT vs HTTP selon disponibilité
⚡ Auto-optimisation : Batch size selon CPU/succès
🎯 Priorités dynamiques : Alertes de sécurité en premier
💤 Veille adaptative : Économie de ressources en période calme
♻️ Retry intelligent : Backoff exponentiel avec dégradation
📊 Métriques temps réel : Auto-ajustement selon performances
"""

logger = get_logger("running_processes")
API_BASE_URL = config.get("api", "url", fallback="http://localhost:5000/api")


class IntelligentQueueWorker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.running = True
        self.queue = queue.PriorityQueue()  # Priorité automatique

        # Intelligence adaptative
        self.batch_size = 1
        self.sleep_time = 0.1
        self.last_activity = time.time()

        # Métriques pour auto-adaptation
        self.success_rate = 1.0
        self.avg_processing_time = 0.1

        # Traçabilité des messages
        self.persistent_types = ["security_alert", "critical_error", "process_blocked"]
        self.processed_ids = set()  # Cache des IDs traités
        self._sequence_counter = 0  # Pour éviter les comparaisons de dict
        
        # 🛡️ Circuit breaker pour API et MQTT
        self.api_circuit_breaker = {
            "state": "closed",  # closed, open, half_open
            "failure_count": 0,
            "last_failure": None,
            "timeout": 30,  # seconds before trying half_open
            "failure_threshold": 5,
            "next_retry": 0
        }
        
        self.mqtt_circuit_breaker = {
            "state": "closed",
            "failure_count": 0, 
            "last_failure": None,
            "timeout": 15,  # MQTT plus rapide à récupérer
            "failure_threshold": 3,
            "next_retry": 0
        }
        
        # 📊 Limitation des threads de retry actifs
        self.active_retry_threads = 0
        self.max_retry_threads = 5

    def run(self):
        """Boucle autonome avec auto-optimisation"""
        while self.running:
            try:
                # 🔄 Récupérer les messages persistants non traités
                self._load_pending_persistent_messages()

                # 🎯 Détection charge système
                items = self._collect_batch()

                if not items:
                    # 😴 Mode veille intelligent
                    self._adaptive_sleep()
                    continue

                # 🚀 Traitement optimisé
                self._process_batch_intelligently(items)

                # 📊 Auto-ajustement des performances
                self._adapt_performance()

                # 🧹 Nettoyage périodique (toutes les 10 itérations)
                if hasattr(self, "_cleanup_counter"):
                    self._cleanup_counter += 1
                else:
                    self._cleanup_counter = 1

                if self._cleanup_counter % 10 == 0:
                    self._cleanup_processed_messages()

            except Exception as e:
                logger.error(f"Worker error: {e}")
                time.sleep(1)

    def add_item(self, item, priority=5):
        """🎯 Ajout intelligent avec priorité et traçabilité"""
        # Générer UUID unique si pas déjà présent
        if "id" not in item:
            item["id"] = str(uuid.uuid4())

        item["created_at"] = datetime.now().isoformat()

        # Auto-priorité selon le type
        if item.get("type") == "security_alert":
            priority = 1
        elif item.get("type") == "process_update":
            priority = 3
        elif item.get("type") == "heartbeat":
            priority = 9

        # 🔧 Sequence counter pour éviter comparaison de dict
        self._sequence_counter += 1

        # Structure: (priority, sequence, item) - évite comparaison dict
        self.queue.put((priority, self._sequence_counter, item))
        self.last_activity = time.time()

        # Backup persistant pour messages critiques
        if item.get("type") in self.persistent_types:
            self._save_to_persistent_queue(item, priority)

    def _collect_batch(self):
        """📦 Collecte intelligente par batch"""
        items = []
        deadline = time.time() + 0.1  # Max 100ms pour collecter

        while len(items) < self.batch_size and time.time() < deadline:
            try:
                priority, sequence, item = self.queue.get_nowait()
                items.append((priority, item))  # On ignore sequence dans le traitement
            except queue.Empty:
                break

        return items

    def _process_batch_intelligently(self, items):
        """🧠 Traitement intelligent multi-canal"""
        start_time = time.time()

        # Groupement par type pour optimisation
        grouped = self._group_by_type(items)

        for item_type, batch in grouped.items():
            if item_type == "high_priority":
                # ⚡ Immédiat, pas de batching
                for _, item in batch:
                    self._send_immediately(item)

            elif item_type == "process_data":
                # 📊 Batching intelligent
                self._send_batch_api(batch)

            elif item_type == "heartbeat":
                # 💓 MQTT seulement si disponible
                if self._mqtt_healthy():
                    self._send_mqtt_batch(batch)

    def _adaptive_sleep(self):
        """😴 Veille adaptative selon l'activité"""
        idle_time = time.time() - self.last_activity

        if idle_time < 10:  # Récemment actif
            time.sleep(0.1)
        elif idle_time < 60:  # Modérément inactif
            time.sleep(0.5)
        else:  # Très inactif
            time.sleep(2.0)

    def _adapt_performance(self):
        """📊 Auto-ajustement selon les performances"""
        # Augmente batch si système peu chargé
        if psutil.cpu_percent() < 30 and self.success_rate > 0.95:
            self.batch_size = min(50, self.batch_size + 5)

        # Réduit si surcharge
        elif psutil.cpu_percent() > 80 or self.success_rate < 0.8:
            self.batch_size = max(1, self.batch_size - 2)

    def _send_immediately(self, item):
        """⚡ Envoi prioritaire multi-canal"""
        success = False

        # Priorité : MQTT si rapide, sinon HTTP
        if self._mqtt_healthy() and self._mqtt_fast():
            success = self._try_mqtt(item)

        if not success:
            success = self._try_api(item)

        if not success:
            # ♻️ Retry intelligent avec dégradation
            self._smart_retry(item)

    def _mqtt_healthy(self):
        """🩺 Santé MQTT avec cache intelligent"""
        if not hasattr(self, "_mqtt_status_cache"):
            self._mqtt_status_cache = {"status": False, "expires": 0}

        if time.time() > self._mqtt_status_cache["expires"]:
            # Vérification périodique pas trop fréquente
            self._mqtt_status_cache = {
                "status": self._check_mqtt_connection(),
                "expires": time.time() + 30,  # Cache 30 secondes
            }

        return self._mqtt_status_cache["status"]

    def _smart_retry(self, item):
        """♻️ Retry intelligent avec backoff et limitation des threads"""
        retries = item.get("retries", 0)
        
        # 🛑 Limiter le nombre de retries
        if retries >= 5:  # Maximum 5 retries au lieu de 3
            logger.warning(f"Max retries reached for item {item.get('id')}, dropping")
            if item.get("type") in self.persistent_types:
                self._mark_message_failed(item.get("id"))
            return
        
        # 🛑 Limiter le nombre de threads de retry actifs
        if self.active_retry_threads >= self.max_retry_threads:
            logger.debug(f"Max retry threads ({self.max_retry_threads}) reached, queueing for later")
            # Remet directement en queue au lieu de créer un thread
            item["retries"] = retries + 1
            priority = 7 + retries  # Priorité plus basse
            self.add_item(item, priority)
            return
        
        # ⏳ Calcul du délai avec backoff exponentiel + jitter
        base_delay = 2 ** retries  # 1s, 2s, 4s, 8s, 16s
        jitter = uniform(0.5, 1.5)  # Éviter thundering herd
        delay = min(base_delay * jitter, 60)  # Max 60s
        
        # 🔍 Augmenter délai si circuit breakers ouverts
        if self.api_circuit_breaker["state"] == "open" and self.mqtt_circuit_breaker["state"] == "open":
            delay = max(delay, 30)  # Minimum 30s si tout est down
            logger.debug(f"Both API and MQTT down, increasing retry delay to {delay:.1f}s")
        
        # 📊 Mise à jour item pour retry
        item["retries"] = retries + 1
        
        # Repriorise selon l'urgence et tentatives
        if item.get("type") == "security_alert":
            priority = min(2 + retries, 5)  # Garde priorité pour security
        else:
            priority = 5 + retries  # Baisse la priorité
        
        # 🕐 Programmer retry avec thread limité
        def retry_with_cleanup():
            self.active_retry_threads += 1
            try:
                time.sleep(delay)  # Pause avant retry
                if self.running:  # Vérifier si worker toujours actif
                    self.add_item(item, priority)
            finally:
                self.active_retry_threads -= 1
                
        threading.Timer(0, retry_with_cleanup).start()
        
        logger.debug(f"Scheduled retry #{retries + 1} for {item.get('id')} in {delay:.1f}s (priority {priority})")

    def _save_to_persistent_queue(self, item, priority):
        """💾 Sauvegarde en table avec statut"""
        try:
            add_queue_with_tracking(
                queue_id=item["id"],
                queue_type=item.get("type"),
                queue_data=item,
                priority=priority,
                status="pending",  # pending, processing, sent, failed
                created_at=datetime.now(),
            )
        except Exception as e:
            logger.error(f"Failed to save persistent queue: {e}")

    def _load_pending_persistent_messages(self):
        """🔄 Charger les messages persistants non traités"""
        try:
            pending_messages = get_pending_queue_messages()

            for msg in pending_messages:
                # Éviter les doublons
                if msg["id"] not in self.processed_ids:
                    # Marquer comme en cours de traitement
                    self._mark_message_processing(msg["id"])

                    # Remettre en queue mémoire avec priorité adaptée
                    self._sequence_counter += 1
                    self.queue.put(
                        (msg["priority"], self._sequence_counter, msg["data"])
                    )

        except Exception as e:
            logger.error(f"Failed to load pending messages: {e}")

    def _send_immediately(self, item):
        """⚡ Envoi prioritaire multi-canal avec circuit breakers"""
        success = False
        message_id = item.get("id")

        try:
            # 🛡️ Essayer MQTT en premier si healthy et rapide
            if (self._can_try_mqtt() and self._mqtt_healthy() and self._mqtt_fast()):
                success = self._try_mqtt(item)

            # 🛡️ Fallback API si MQTT échoue ou indisponible
            if not success and self._can_try_api():
                success = self._try_api(item)

            if success:
                # ✅ Message envoyé avec succès
                self.processed_ids.add(message_id)
                if item.get("type") in self.persistent_types:
                    self._mark_message_sent(message_id)

            else:
                # ❌ Échec sur tous les canaux - retry intelligent
                if item.get("type") in self.persistent_types:
                    self._mark_message_failed(message_id)
                
                # ⏳ Pause légère pour éviter retry immédiat
                if not self._can_try_api() and not self._can_try_mqtt():
                    # Tous les canaux fermés - attendre avant retry
                    time.sleep(uniform(1.0, 3.0))
                    
                self._smart_retry(item)

        except Exception as e:
            logger.error(f"Send failed for {message_id}: {e}")
            if item.get("type") in self.persistent_types:
                self._mark_message_failed(message_id)
            self._smart_retry(item)
            
    def get_circuit_breaker_status(self):
        """📊 Retourner le statut des circuit breakers"""
        return {
            "api": {
                "state": self.api_circuit_breaker["state"],
                "failure_count": self.api_circuit_breaker["failure_count"],
                "next_retry": self.api_circuit_breaker.get("next_retry", 0),
                "time_until_retry": max(0, self.api_circuit_breaker.get("next_retry", 0) - time.time())
            },
            "mqtt": {
                "state": self.mqtt_circuit_breaker["state"], 
                "failure_count": self.mqtt_circuit_breaker["failure_count"],
                "next_retry": self.mqtt_circuit_breaker.get("next_retry", 0),
                "time_until_retry": max(0, self.mqtt_circuit_breaker.get("next_retry", 0) - time.time())
            },
            "active_retry_threads": self.active_retry_threads,
            "max_retry_threads": self.max_retry_threads
        }

    def _mark_message_processing(self, message_id):
        """🔄 Marquer message en cours de traitement"""
        try:
            update_queue_status(message_id, "processing")
        except Exception as e:
            logger.error(f"Failed to mark processing {message_id}: {e}")

    def _mark_message_sent(self, message_id):
        """✅ Marquer message comme envoyé"""
        try:
            update_queue_status(message_id, "sent", datetime.now())
        except Exception as e:
            logger.error(f"Failed to mark sent {message_id}: {e}")

    def _mark_message_failed(self, message_id):
        """❌ Marquer message comme échoué"""
        try:
            update_queue_status(message_id, "failed", datetime.now())
        except Exception as e:
            logger.error(f"Failed to mark failed {message_id}: {e}")

    def _cleanup_processed_messages(self):
        """🧹 Nettoyage périodique des messages traités"""
        try:
            # Supprimer messages envoyés > 24h ou échoués > 7 jours
            cleanup_old_queue_messages(
                sent_older_than_hours=24,
                failed_older_than_hours=168,  # 7 jours
            )

            # Nettoyer le cache local
            if len(self.processed_ids) > 1000:
                self.processed_ids.clear()

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

    def _try_mqtt(self, item):
        """📡 Tentative d'envoi MQTT avec circuit breaker"""
        # 🛡️ Vérifier circuit breaker avant tentative
        if not self._can_try_mqtt():
            logger.debug("MQTT circuit breaker open, skipping attempt")
            return False
            
        try:
            # Construire le topic selon le type de message
            topic = self._get_mqtt_topic(item)
            payload = self._format_mqtt_payload(item)

            # Envoi avec timeout
            result = publish(topic, payload, timeout=2)
            
            if result is not None:
                # ✅ Succès MQTT
                self._mqtt_success()
                return True
            else:
                # ❌ Échec MQTT
                self._mqtt_failure()
                return False

        except Exception as e:
            logger.debug(f"MQTT send failed: {e}")
            # ❌ Échec MQTT
            self._mqtt_failure()
            return False
            
    def _can_try_mqtt(self):
        """🛡️ Vérifier si on peut essayer MQTT (circuit breaker)"""
        cb = self.mqtt_circuit_breaker
        now = time.time()
        
        if cb["state"] == "closed":
            return True
            
        elif cb["state"] == "open":
            if now >= cb["next_retry"]:
                cb["state"] = "half_open"
                logger.info("🔄 MQTT circuit breaker: open → half_open")
                return True
            return False
            
        elif cb["state"] == "half_open":
            return True
            
        return False
        
    def _mqtt_success(self):
        """✅ Enregistrer succès MQTT"""
        cb = self.mqtt_circuit_breaker
        if cb["failure_count"] > 0:
            logger.info(f"🔄 MQTT recovered after {cb['failure_count']} failures")
        
        cb["state"] = "closed"
        cb["failure_count"] = 0
        cb["last_failure"] = None
        
    def _mqtt_failure(self):
        """❌ Enregistrer échec MQTT"""
        cb = self.mqtt_circuit_breaker
        cb["failure_count"] += 1
        cb["last_failure"] = time.time()
        
        if cb["failure_count"] >= cb["failure_threshold"]:
            if cb["state"] != "open":
                backoff_time = min(cb["timeout"] * (2 ** (cb["failure_count"] - cb["failure_threshold"])), 120)  # Max 2min pour MQTT
                cb["state"] = "open"
                cb["next_retry"] = time.time() + backoff_time
                logger.warning(f"🚫 MQTT circuit breaker OPEN for {backoff_time:.0f}s after {cb['failure_count']} failures")
        
        elif cb["state"] == "half_open":
            backoff_time = cb["timeout"]
            cb["state"] = "open" 
            cb["next_retry"] = time.time() + backoff_time
            logger.warning(f"🚫 MQTT circuit breaker: half_open → open for {backoff_time}s")

    def _try_api(self, item):
        """🌐 Tentative d'envoi API HTTP avec circuit breaker"""
        # 🛡️ Vérifier circuit breaker avant tentative
        if not self._can_try_api():
            logger.debug("API circuit breaker open, skipping attempt")
            return False
            
        try:
            # 🎯 Routage intelligent selon le type de message
            endpoint_info = self._get_api_endpoint(item)
            url = f"{API_BASE_URL}{endpoint_info['path']}"
            payload = self._format_api_payload(item, endpoint_info['format'])

            response = requests.post(
                url,
                json=payload,
                timeout=endpoint_info.get('timeout', 5),
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                # ✅ Succès - reset circuit breaker
                self._api_success()
                return True
            else:
                # ❌ Échec HTTP - compter comme erreur
                self._api_failure()
                return False

        except Exception as e:
            logger.debug(f"API send failed: {e}")
            # ❌ Échec réseau/timeout - compter comme erreur
            self._api_failure() 
            return False
            
    def _can_try_api(self):
        """🛡️ Vérifier si on peut essayer l'API (circuit breaker)"""
        cb = self.api_circuit_breaker
        now = time.time()
        
        if cb["state"] == "closed":
            return True
            
        elif cb["state"] == "open":
            # Vérifier si on peut passer en half_open
            if now >= cb["next_retry"]:
                cb["state"] = "half_open"
                logger.info("🔄 API circuit breaker: open → half_open")
                return True
            return False
            
        elif cb["state"] == "half_open":
            return True
            
        return False
        
    def _api_success(self):
        """✅ Enregistrer succès API - reset circuit breaker"""
        cb = self.api_circuit_breaker
        if cb["failure_count"] > 0:
            logger.info(f"🔄 API recovered after {cb['failure_count']} failures")
        
        cb["state"] = "closed"
        cb["failure_count"] = 0
        cb["last_failure"] = None
        
    def _api_failure(self):
        """❌ Enregistrer échec API - incrémenter circuit breaker"""
        cb = self.api_circuit_breaker
        cb["failure_count"] += 1
        cb["last_failure"] = time.time()
        
        if cb["failure_count"] >= cb["failure_threshold"]:
            if cb["state"] != "open":
                # Passage en mode ouvert avec backoff exponentiel  
                backoff_time = min(cb["timeout"] * (2 ** (cb["failure_count"] - cb["failure_threshold"])), 300)  # Max 5min
                cb["state"] = "open"
                cb["next_retry"] = time.time() + backoff_time
                logger.warning(f"🚫 API circuit breaker OPEN for {backoff_time:.0f}s after {cb['failure_count']} failures")
        
        elif cb["state"] == "half_open":
            # Retour en mode ouvert si échec en half_open
            backoff_time = cb["timeout"]  
            cb["state"] = "open"
            cb["next_retry"] = time.time() + backoff_time
            logger.warning(f"🚫 API circuit breaker: half_open → open for {backoff_time}s")

    def _get_api_endpoint(self, item):
        """🎯 Déterminer l'endpoint API selon le type de message"""
        message_type = item.get("type", "unknown")
        
        # 📍 Mapping des endpoints spécialisés
        endpoint_mapping = {
            "security_alert": {
                "path": "/security/alerts",
                "format": "security",
                "timeout": 10  # Plus de temps pour les alertes critiques
            },
            "process_event": {
                "path": self._get_process_endpoint_path(item),
                "format": "process_event", 
                "timeout": 7
            },
            "notification": {
                "path": "/notifications/general",
                "format": "notification",
                "timeout": 5
            },
            "heartbeat": {
                "path": "/system/heartbeat",
                "format": "heartbeat",
                "timeout": 3  # Heartbeat doit être rapide
            }
        }
        
        return endpoint_mapping.get(
            message_type, 
            {"path": "/events/generic", "format": "generic", "timeout": 5}  # Fallback
        )
    
    def _get_process_endpoint_path(self, item):
        """🔄 Sous-routage pour les événements de processus"""
        action = item.get("action", "unknown")
        
        action_endpoints = {
            "instance_created": "/processes/instances",
            "process_started": "/processes/events/start", 
            "process_stopped": "/processes/events/stop",
            "process_updated": "/processes/instances/update"
        }
        
        return action_endpoints.get(action, "/processes/events/generic")
    
    def _format_api_payload(self, item, format_type):
        """📝 Formatter payload API selon le type d'endpoint"""
        base_payload = {
            "message_id": item.get("id"),
            "timestamp": item.get("created_at"),
        }
        
        if format_type == "security":
            return {
                **base_payload,
                "alert_type": "process_security",
                "severity": self._map_priority_to_severity(item),
                "process_name": item.get("process_name"),  
                "risk_score": item.get("risk_score"),
                "details": item.get("details", {}),
                "instance_id": item.get("instance_id")
            }
            
        elif format_type == "process_event":
            return {
                **base_payload,
                "event_type": item.get("action"), 
                "process_instance": item.get("instance", {}),
                "metadata": {
                    "source": "surveillance_client",
                    "version": "1.0"
                }
            }
            
        elif format_type == "heartbeat":
            return {
                **base_payload,
                "client_status": "alive",
                "system_info": item,
                "metrics": {
                    "uptime": item.get("uptime"),
                    "cpu_usage": item.get("cpu_usage"),
                    "memory_usage": item.get("memory_usage")
                }
            }
            
        elif format_type == "notification":
            return {
                **base_payload,
                "notification_type": "general",
                "message": item.get("message", ""),
                "severity": "info", 
                "data": {k: v for k, v in item.items() 
                        if k not in ["id", "type", "created_at"]}
            }
            
        else:  # format_type == "generic"
            return {
                **base_payload,
                "event_type": "generic",  
                "raw_data": item
            }
            
    def _map_priority_to_severity(self, item):
        """🎯 Mapper priorité vers niveau de sévérité"""
        score = item.get("risk_score", 0)
        
        if score >= 20:
            return "critical"
        elif score >= 10:
            return "high" 
        elif score >= 5:
            return "medium"
        else:
            return "low"

    def _mqtt_fast(self):
        """⚡ Vérifier si MQTT est rapide (latence < 500ms)"""
        if not hasattr(self, "_mqtt_latency_cache"):
            self._mqtt_latency_cache = {"latency": 1000, "expires": 0}

        if time.time() > self._mqtt_latency_cache["expires"]:
            # Test de latence périodique
            start = time.time()
            try:
                ping()
                latency = (time.time() - start) * 1000  # en ms
            except:
                latency = 9999  # Très lent si erreur

            self._mqtt_latency_cache = {
                "latency": latency,
                "expires": time.time() + 60,  # Cache 1 minute
            }

        return self._mqtt_latency_cache["latency"] < 500

    def _check_mqtt_connection(self):
        """🔍 Vérifier connexion MQTT"""
        try:
            return get_mqtt_status() == MQTTStatus.CONNECTED
        except:
            return False

    def _group_by_type(self, items):
        """📊 Grouper items par type pour optimisation"""
        groups = {}

        for priority, item in items:
            item_type = item.get("type", "unknown")

            # Classification intelligente
            if item_type in ["security_alert", "critical_error"]:
                group_key = "high_priority"
            elif item_type in ["process_update", "instance_add"]:
                group_key = "process_data"
            elif item_type in ["heartbeat", "status_update"]:
                group_key = "heartbeat"
            else:
                group_key = "other"

            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append((priority, item))

        return groups

    def _send_batch_api(self, batch):
        """📦 Envoi batch API avec circuit breaker et rate limiting"""
        # 🛡️ Vérifier circuit breaker avant batch
        if not self._can_try_api():
            logger.debug("API circuit breaker open, skipping batch and queueing individual items")
            # Reporter tous les items au lieu de les perdre
            for _, item in batch:
                self._smart_retry(item)
            return False
            
        try:
            # 📊 Regrouper par type d'endpoint pour batch optimisé
            endpoint_groups = self._group_batch_by_endpoint(batch)
            
            all_success = True
            
            for endpoint_path, items in endpoint_groups.items():
                # 🛑 Vérifier si on peut encore essayer après chaque groupe
                if not self._can_try_api():
                    logger.debug(f"API circuit breaker opened mid-batch, queueing remaining items")
                    for _, item in items:
                        self._smart_retry(item)
                    all_success = False
                    continue
                    
                try:
                    # Préparer payload batch spécialisé
                    batch_payload = self._format_batch_payload(endpoint_path, items)
                    url = f"{API_BASE_URL}{endpoint_path}/batch"
                    
                    response = requests.post(
                        url, 
                        json=batch_payload, 
                        timeout=15,  # Timeout plus long pour batch
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if response.status_code == 200:
                        # ✅ Succès batch - marquer items et reset circuit breaker
                        self._api_success()  # Reset circuit breaker
                        for _, item in items:
                            if item.get("id"):
                                self.processed_ids.add(item["id"])
                                if item.get("type") in self.persistent_types:
                                    self._mark_message_sent(item["id"])
                    else:
                        # ❌ Échec batch HTTP - compter comme erreur
                        self._api_failure()
                        logger.warning(f"Batch failed for {endpoint_path} (HTTP {response.status_code}), queueing individual retries")
                        
                        # ⏳ Pause avant retry pour éviter thundering herd
                        time.sleep(uniform(0.5, 2.0))
                        
                        for _, item in items:
                            self._smart_retry(item)
                        all_success = False
                        
                except Exception as e:
                    # ❌ Échec batch réseau/timeout
                    self._api_failure()
                    logger.warning(f"Batch endpoint {endpoint_path} failed: {e}")
                    
                    # ⏳ Pause avant retry pour éviter surcharge
                    time.sleep(uniform(1.0, 3.0))
                    
                    for _, item in items:
                        self._smart_retry(item)
                    all_success = False
            
            return all_success
            
        except Exception as e:
            logger.error(f"Batch API failed: {e}")
            self._api_failure()
            
            # ⏳ Pause avant retry pour éviter surcharge
            time.sleep(uniform(2.0, 5.0))
            
            # Fallback individuel avec retry intelligent
            for _, item in batch:
                self._smart_retry(item)
            return False

    def _group_batch_by_endpoint(self, batch):
        """📊 Regrouper items de batch par endpoint"""
        endpoint_groups = {}
        
        for priority, item in batch:
            endpoint_info = self._get_api_endpoint(item)
            endpoint_path = endpoint_info['path']
            
            if endpoint_path not in endpoint_groups:
                endpoint_groups[endpoint_path] = []
            endpoint_groups[endpoint_path].append((priority, item))
            
        return endpoint_groups
    
    def _format_batch_payload(self, endpoint_path, items):
        """📝 Formatter payload batch selon l'endpoint"""
        batch_items = []
        
        for _, item in items:
            # Réutiliser la logique de formatting individuel
            endpoint_info = self._get_api_endpoint(item)
            formatted_item = self._format_api_payload(item, endpoint_info['format'])
            batch_items.append(formatted_item)
        
        return {
            "batch_id": str(uuid.uuid4()),
            "batch_timestamp": datetime.now().isoformat(),
            "item_count": len(batch_items),
            "endpoint_type": self._extract_endpoint_type(endpoint_path),
            "items": batch_items
        }
    
    def _extract_endpoint_type(self, endpoint_path):
        """🏷️ Extraire le type d'endpoint depuis le chemin"""
        if "/security/" in endpoint_path:
            return "security_alerts"
        elif "/processes/" in endpoint_path:
            return "process_events"
        elif "/system/" in endpoint_path:
            return "system_heartbeat"
        elif "/notifications/" in endpoint_path:
            return "general_notifications"
        else:
            return "generic_events"

    def _send_mqtt_batch(self, batch):
        """📡 Envoi batch MQTT"""
        try:
            for _, item in batch:
                topic = self._get_mqtt_topic(item)
                payload = self._format_mqtt_payload(item)

                if publish(topic, payload):
                    if item.get("id"):
                        self.processed_ids.add(item["id"])
                        if item.get("type") in self.persistent_types:
                            self._mark_message_sent(item["id"])
                else:
                    # Retry individuel si échec
                    self._smart_retry(item)

        except Exception as e:
            logger.error(f"MQTT batch failed: {e}")

    def _get_mqtt_topic(self, item):
        """🎯 Construire topic MQTT selon le type"""
        item_type = item.get("type", "general")

        topic_map = {
            "security_alert": "surveillance/[client]/alert",
            "process_update": "surveillance/[client]/process",
            "heartbeat": "surveillance/[client]/heartbeat",
            "critical_error": "surveillance/[client]/error",
        }

        return topic_map.get(item_type, "surveillance/[client]/general")

    def _format_mqtt_payload(self, item):
        """📝 Formatter payload MQTT"""
        return {
            "id": item.get("id"),
            "type": item.get("type"),
            "timestamp": item.get("created_at", datetime.now().isoformat()),
            "data": {
                k: v for k, v in item.items() if k not in ["id", "type", "created_at"]
            },
        }
