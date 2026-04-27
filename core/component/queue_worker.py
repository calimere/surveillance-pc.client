import queue
from random import uniform
import threading
import time
import uuid
from datetime import datetime
import psutil
from core.component.logger import get_logger
from core.business.db import add_queue_with_tracking
from core.business.db import get_pending_queue_messages
from core.business.db import update_queue_status
from core.business.db import cleanup_old_queue_messages

from core.component.mqtt_client import publish
from core.component.mqtt_client import get_mqtt_status, MQTTStatus
from core.component.mqtt_client import ping

"""
🎯 Priorités dynamiques : Alertes de sécurité en premier
💤 Veille adaptative : Économie de ressources en période calme
♻️ Retry intelligent : Backoff exponentiel — MQTT uniquement (best-effort)
📡 Données structurées → sync_worker via HTTP (source de vérité)
"""

logger = get_logger("queue_worker")


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

        # 🛡️ Circuit breaker MQTT
        self.mqtt_circuit_breaker = {
            "state": "closed",
            "failure_count": 0,
            "last_failure": None,
            "timeout": 15,  # MQTT plus rapide à récupérer
            "failure_threshold": 3,
            "next_retry": 0,
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
        """🧠 Traitement MQTT par priorité"""
        grouped = self._group_by_type(items)

        for item_type, batch in grouped.items():
            if item_type == "high_priority":
                # ⚡ Envoi immédiat item par item (alertes, erreurs critiques)
                for _, item in batch:
                    self._send_immediately(item)
            else:
                # 📦 Batch MQTT pour process_data, heartbeat, other
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
            logger.debug(
                f"Max retry threads ({self.max_retry_threads}) reached, queueing for later"
            )
            # Remet directement en queue au lieu de créer un thread
            item["retries"] = retries + 1
            priority = 7 + retries  # Priorité plus basse
            self.add_item(item, priority)
            return

        # ⏳ Calcul du délai avec backoff exponentiel + jitter
        base_delay = 2**retries  # 1s, 2s, 4s, 8s, 16s
        jitter = uniform(0.5, 1.5)  # Éviter thundering herd
        delay = min(base_delay * jitter, 60)  # Max 60s

        # 🔍 Augmenter délai si MQTT circuit breaker ouvert
        if self.mqtt_circuit_breaker["state"] == "open":
            delay = max(delay, 30)  # Minimum 30s si MQTT est down
            logger.debug(f"MQTT down, increasing retry delay to {delay:.1f}s")

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

        logger.debug(
            f"Scheduled retry #{retries + 1} for {item.get('id')} in {delay:.1f}s (priority {priority})"
        )

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
        """⚡ Envoi prioritaire MQTT"""
        success = False
        message_id = item.get("id")

        try:
            if self._can_try_mqtt() and self._mqtt_healthy():
                success = self._try_mqtt(item)

            if success:
                self.processed_ids.add(message_id)
                if item.get("type") in self.persistent_types:
                    self._mark_message_sent(message_id)
            else:
                # MQTT indisponible → retry en attendant que MQTT revienne
                if item.get("type") in self.persistent_types:
                    self._mark_message_failed(message_id)
                self._smart_retry(item)

        except Exception as e:
            logger.error(f"Send failed for {message_id}: {e}")
            if item.get("type") in self.persistent_types:
                self._mark_message_failed(message_id)
            self._smart_retry(item)

    def get_circuit_breaker_status(self):
        """📊 Retourner le statut du circuit breaker MQTT"""
        return {
            "mqtt": {
                "state": self.mqtt_circuit_breaker["state"],
                "failure_count": self.mqtt_circuit_breaker["failure_count"],
                "next_retry": self.mqtt_circuit_breaker.get("next_retry", 0),
                "time_until_retry": max(
                    0, self.mqtt_circuit_breaker.get("next_retry", 0) - time.time()
                ),
            },
            "active_retry_threads": self.active_retry_threads,
            "max_retry_threads": self.max_retry_threads,
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

            # Envoi
            result = publish(topic, payload)

            if result is not None:
                # ✅ Succès MQTT
                self._mqtt_success()
                logger.info(
                    f"📡 MQTT envoyé → topic={topic} | type={item.get('type')} | id={item.get('id')}"
                )
                return True
            else:
                # ❌ Échec MQTT
                self._mqtt_failure()
                logger.warning(
                    f"📡 MQTT échec → topic={topic} | type={item.get('type')} | id={item.get('id')}"
                )
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
                backoff_time = min(
                    cb["timeout"]
                    * (2 ** (cb["failure_count"] - cb["failure_threshold"])),
                    120,
                )  # Max 2min pour MQTT
                cb["state"] = "open"
                cb["next_retry"] = time.time() + backoff_time
                logger.warning(
                    f"🚫 MQTT circuit breaker OPEN for {backoff_time:.0f}s after {cb['failure_count']} failures"
                )

        elif cb["state"] == "half_open":
            backoff_time = cb["timeout"]
            cb["state"] = "open"
            cb["next_retry"] = time.time() + backoff_time
            logger.warning(
                f"🚫 MQTT circuit breaker: half_open → open for {backoff_time}s"
            )

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
            except Exception:
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
        except Exception:
            return False

    def _group_by_type(self, items):
        """📊 Grouper items par type pour optimisation"""
        groups = {}

        for priority, item in items:
            item_type = item.get("type", "unknown")

            # Classification intelligente
            if item_type in ["security_alert"]:
                group_key = "high_priority"
            elif item_type in ["process_event"]:
                group_key = "process_event"
            elif item_type in ["process"]:
                group_key = "process"
            elif item_type in ["process_instance"]:
                group_key = "process_instance"
            elif item_type in ["heartbeat"]:
                group_key = "heartbeat"
            elif item_type in ["notification"]:
                group_key = "high_priority"
            else:
                group_key = "other"

            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append((priority, item))

        return groups

    def _send_mqtt_batch(self, batch):
        """📡 Envoi batch MQTT"""
        try:
            for _, item in batch:
                topic = self._get_mqtt_topic(item)
                payload = self._format_mqtt_payload(item)

                result = publish(topic, payload)
                if result is not None:
                    logger.info(
                        f"📡 MQTT envoyé → topic={topic} | type={item.get('type')} | id={item.get('id')}"
                    )
                    if item.get("id"):
                        self.processed_ids.add(item["id"])
                        if item.get("type") in self.persistent_types:
                            self._mark_message_sent(item["id"])
                else:
                    logger.warning(
                        f"📡 MQTT échec (client non init) → type={item.get('type')} | id={item.get('id')}"
                    )
                    # Retry individuel si échec
                    self._smart_retry(item)

        except Exception as e:
            logger.error(f"MQTT batch failed: {e}")

    def _get_mqtt_topic(self, item):
        """🎯 Construire topic MQTT selon le type"""
        item_type = item.get("type", "general")

        topic_map = {
            "security_alert": "surveillance/[client]/alert",
            "process_event": "surveillance/[client]/process/event",
            "process": "surveillance/[client]/process",
            "process_instance": "surveillance/[client]/process/instance",
            "notification": "surveillance/[client]/notification",
            "heartbeat": "surveillance/[client]/heartbeat",
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
