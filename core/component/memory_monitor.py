#!/usr/bin/env python3
"""
🧠 Moniteur de mémoire pour détecter les fuites
"""

import psutil
import os
import time
import threading
from collections import deque
from datetime import datetime, timedelta
from core.component.logger import get_logger

logger = get_logger("memory_monitor")


class MemoryMonitor:
    """🔍 Moniteur de consommation mémoire avec détection de fuites"""

    def __init__(self, check_interval=30, history_size=100, leak_threshold=50):
        """
        Args:
            check_interval: Intervalle de vérification en secondes
            history_size: Nombre de mesures à garder en historique
            leak_threshold: Seuil de détection de fuite en MB
        """
        self.check_interval = check_interval
        self.leak_threshold = leak_threshold
        self.history = deque(maxlen=history_size)
        self.process = psutil.Process(os.getpid())
        self._monitoring = False
        self._thread = None

    def start_monitoring(self):
        """🚀 Démarre le monitoring en arrière-plan"""
        if self._monitoring:
            logger.warning("Monitoring déjà démarré")
            return

        self._monitoring = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info(f"Monitoring mémoire démarré (intervalle: {self.check_interval}s)")

    def stop_monitoring(self):
        """🛑 Arrête le monitoring"""
        self._monitoring = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Monitoring mémoire arrêté")

    def _monitor_loop(self):
        """🔄 Boucle de monitoring"""
        while self._monitoring:
            try:
                self._check_memory()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Erreur monitoring mémoire: {e}")
                time.sleep(self.check_interval)

    def _check_memory(self):
        """📊 Vérifie la consommation mémoire"""
        try:
            memory_info = self.process.memory_info()

            data = {
                "timestamp": datetime.now(),
                "rss_mb": memory_info.rss / 1024 / 1024,
                "vms_mb": memory_info.vms / 1024 / 1024,
                "percent": self.process.memory_percent(),
            }

            self.history.append(data)

            # Détection de fuite potentielle
            if len(self.history) >= 10:
                self._check_memory_leak()

        except Exception as e:
            logger.error(f"Erreur mesure mémoire: {e}")

    def _check_memory_leak(self):
        """🔍 Détecte les fuites mémoire potentielles"""
        if len(self.history) < 10:
            return

        # Compare les 5 dernières mesures aux 5 précédentes
        recent = list(self.history)[-5:]
        older = list(self.history)[-10:-5]

        avg_recent = sum(d["rss_mb"] for d in recent) / len(recent)
        avg_older = sum(d["rss_mb"] for d in older) / len(older)

        growth = avg_recent - avg_older

        if growth > self.leak_threshold:
            logger.warning(f"🚨 Fuite mémoire potentielle détectée:")
            logger.warning(f"   Croissance: +{growth:.1f} MB")
            logger.warning(f"   Moyenne récente: {avg_recent:.1f} MB")
            logger.warning(f"   Pourcentage système: {recent[-1]['percent']:.1f}%")

    def get_current_usage(self):
        """📈 Obtient l'usage mémoire actuel"""
        try:
            memory_info = self.process.memory_info()
            return {
                "rss_mb": memory_info.rss / 1024 / 1024,
                "vms_mb": memory_info.vms / 1024 / 1024,
                "percent": self.process.memory_percent(),
                "available_mb": psutil.virtual_memory().available / 1024 / 1024,
            }
        except Exception as e:
            logger.error(f"Erreur obtention usage mémoire: {e}")
            return None

    def get_memory_stats(self):
        """📊 Statistiques mémoire détaillées"""
        if not self.history:
            return None

        rss_values = [d["rss_mb"] for d in self.history]

        return {
            "current_mb": rss_values[-1],
            "min_mb": min(rss_values),
            "max_mb": max(rss_values),
            "avg_mb": sum(rss_values) / len(rss_values),
            "growth_mb": rss_values[-1] - rss_values[0] if len(rss_values) > 1 else 0,
            "measurements": len(rss_values),
        }

    def log_memory_report(self):
        """📋 Log un rapport mémoire détaillé"""
        usage = self.get_current_usage()
        stats = self.get_memory_stats()

        if usage:
            logger.info("=== RAPPORT MÉMOIRE ===")
            logger.info(
                f"💾 RAM actuelle: {usage['rss_mb']:.1f} MB ({usage['percent']:.1f}%)"
            )
            logger.info(f"🗄️ Mémoire virtuelle: {usage['vms_mb']:.1f} MB")
            logger.info(f"🆓 RAM système disponible: {usage['available_mb']:.1f} MB")

            if stats:
                logger.info(
                    f"📊 Min/Max/Moy: {stats['min_mb']:.1f}/{stats['max_mb']:.1f}/{stats['avg_mb']:.1f} MB"
                )
                logger.info(f"📈 Croissance totale: {stats['growth_mb']:.1f} MB")
                logger.info(f"📏 Mesures: {stats['measurements']}")


# Instance globale
memory_monitor = MemoryMonitor()


def start_memory_monitoring():
    """🚀 Démarre le monitoring global"""
    memory_monitor.start_monitoring()


def stop_memory_monitoring():
    """🛑 Arrête le monitoring global"""
    memory_monitor.stop_monitoring()


def get_memory_usage():
    """📊 Usage mémoire actuel"""
    return memory_monitor.get_current_usage()


def log_memory_report():
    """📋 Log rapport mémoire"""
    memory_monitor.log_memory_report()
