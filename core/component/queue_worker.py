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
        """♻️ Retry intelligent avec backoff"""
        retries = item.get("retries", 0)

        if retries < 3:
            # Backoff exponentiel avec jitter
            delay = (2**retries) + uniform(0, 1)

            # Repriorise selon l'urgence
            if item.get("priority") == "high":
                priority = 1
            else:
                priority = 5 + retries  # Baisse la priorité

            # Remet en queue après délai
            threading.Timer(delay, lambda: self.add_item(item, priority)).start()

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
        """⚡ Envoi prioritaire multi-canal avec traçabilité"""
        success = False
        message_id = item.get("id")

        try:
            # Priorité : MQTT si rapide, sinon HTTP
            if self._mqtt_healthy() and self._mqtt_fast():
                success = self._try_mqtt(item)

            if not success:
                success = self._try_api(item)

            if success:
                # ✅ Message envoyé avec succès
                self.processed_ids.add(message_id)
                if item.get("type") in self.persistent_types:
                    self._mark_message_sent(message_id)

            else:
                # ❌ Échec - retry intelligent
                if item.get("type") in self.persistent_types:
                    self._mark_message_failed(message_id)
                self._smart_retry(item)

        except Exception as e:
            logger.error(f"Send failed for {message_id}: {e}")
            if item.get("type") in self.persistent_types:
                self._mark_message_failed(message_id)

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
        """📡 Tentative d'envoi MQTT"""
        try:
            # Construire le topic selon le type de message
            topic = self._get_mqtt_topic(item)
            payload = self._format_mqtt_payload(item)

            # Envoi avec timeout
            result = publish(topic, payload, timeout=2)
            return result is not None

        except Exception as e:
            logger.error(f"MQTT send failed: {e}")
            return False

    def _try_api(self, item):
        """🌐 Tentative d'envoi API HTTP"""
        try:
            url = f"{API_BASE_URL}/notifications"
            payload = self._format_api_payload(item)

            response = requests.post(
                url,
                json=payload,
                timeout=5,
                headers={"Content-Type": "application/json"},
            )

            return response.status_code == 200

        except Exception as e:
            logger.error(f"API send failed: {e}")
            return False

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
        """📦 Envoi batch API optimisé"""
        try:
            import requests

            # Regrouper les données
            batch_data = [item for _, item in batch]

            response = requests.post(
                f"{API_BASE_URL}/batch", json={"items": batch_data}, timeout=10
            )

            if response.status_code == 200:
                # Marquer tous comme envoyés
                for _, item in batch:
                    if item.get("id"):
                        self.processed_ids.add(item["id"])
                        if item.get("type") in self.persistent_types:
                            self._mark_message_sent(item["id"])
                return True
            else:
                # Traiter individuellement en cas d'échec batch
                for _, item in batch:
                    self._send_immediately(item)

        except Exception as e:
            logger.error(f"Batch API failed: {e}")
            # Fallback individuel
            for _, item in batch:
                self._send_immediately(item)

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

    def _format_api_payload(self, item):
        """📝 Formatter payload API"""
        return {
            "message_id": item.get("id"),
            "message_type": item.get("type"),
            "timestamp": item.get("created_at"),
            "payload": item,
        }
