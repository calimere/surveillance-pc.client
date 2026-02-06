import queue
from random import random
import threading
import time

import psutil

from core.component import logger


"""
🧠 Décisions autonomes : MQTT vs HTTP selon disponibilité
⚡ Auto-optimisation : Batch size selon CPU/succès
🎯 Priorités dynamiques : Alertes de sécurité en premier
💤 Veille adaptative : Économie de ressources en période calme
♻️ Retry intelligent : Backoff exponentiel avec dégradation
📊 Métriques temps réel : Auto-ajustement selon performances
"""


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

    def run(self):
        """Boucle autonome avec auto-optimisation"""
        while self.running:
            try:
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

            except Exception as e:
                logger.error(f"Worker error: {e}")
                time.sleep(1)

    def _collect_batch(self):
        """📦 Collecte intelligente par batch"""
        items = []
        deadline = time.time() + 0.1  # Max 100ms pour collecter

        while len(items) < self.batch_size and time.time() < deadline:
            try:
                priority, item = self.queue.get_nowait()
                items.append((priority, item))
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
            delay = (2**retries) + random.uniform(0, 1)

            # Repriorise selon l'urgence
            if item.get("priority") == "high":
                priority = 1
            else:
                priority = 5 + retries  # Baisse la priorité

            # Remet en queue après délai
            threading.Timer(delay, lambda: self.add_item(item, priority)).start()

    def add_item(self, item, priority=5):
        """🎯 Ajout intelligent avec priorité"""
        # Auto-priorité selon le type
        if item.get("type") == "security_alert":
            priority = 1
        elif item.get("type") == "process_update":
            priority = 3
        elif item.get("type") == "heartbeat":
            priority = 9

        self.queue.put((priority, item))
        self.last_activity = time.time()
