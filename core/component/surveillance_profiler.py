#!/usr/bin/env python3
"""
🔍 Profileur spécifique pour le système de surveillance
"""

import time
import psutil
import tracemalloc
from contextlib import contextmanager
from core.component.logger import get_logger
from core.component.memory_optimizer import MemoryOptimizer, ProcessCache

logger = get_logger("profiler")


class SurveillanceProfiler:
    """🎯 Profileur optimisé pour le système de surveillance"""

    def __init__(self):
        self.process_cache = ProcessCache(max_size=500, ttl_seconds=60)
        self.start_time = time.time()
        self.stats = {
            "scan_count": 0,
            "populate_count": 0,
            "compute_count": 0,
            "memory_peaks": [],
            "slow_operations": [],
        }

    @contextmanager
    def profile_operation(self, operation_name, warn_threshold=1.0):
        """🕐 Profile une opération avec seuil d'alerte"""
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024

        try:
            yield
        finally:
            duration = time.time() - start_time
            end_memory = psutil.Process().memory_info().rss / 1024 / 1024
            memory_diff = end_memory - start_memory

            # Log si l'opération est lente
            if duration > warn_threshold:
                logger.warning(
                    f"⚠️ {operation_name} lente: {duration:.2f}s (seuil: {warn_threshold}s)"
                )
                self.stats["slow_operations"].append(
                    {
                        "operation": operation_name,
                        "duration": duration,
                        "memory_diff": memory_diff,
                        "timestamp": time.time(),
                    }
                )

            # Log si consommation mémoire importante
            if memory_diff > 10:  # Plus de 10MB
                logger.warning(f"🧠 {operation_name} consomme: +{memory_diff:.1f}MB")
                self.stats["memory_peaks"].append(
                    {
                        "operation": operation_name,
                        "memory_used": memory_diff,
                        "timestamp": time.time(),
                    }
                )

            logger.debug(f"✅ {operation_name}: {duration:.2f}s, {memory_diff:+.1f}MB")

    def get_process_info_cached(self, pid):
        """🎯 Récupère les infos processus avec cache"""
        cache_key = f"pid_{pid}"
        cached = self.process_cache.get(cache_key)

        if cached:
            return cached

        try:
            proc = psutil.Process(pid)
            info = {
                "name": proc.name(),
                "exe": proc.exe(),
                "cmdline": " ".join(proc.cmdline()),
                "create_time": proc.create_time(),
                "memory_percent": proc.memory_percent(),
            }

            self.process_cache.put(cache_key, info)
            return info

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None

    def profile_scan_processes(self):
        """📊 Profile le scan des processus"""
        with self.profile_operation("scan_processes", warn_threshold=2.0):
            self.stats["scan_count"] += 1
            # Le code de scan existant serait ici
            pass

    def profile_populate_instances(self):
        """📊 Profile la population des instances"""
        with self.profile_operation("populate_instances", warn_threshold=5.0):
            self.stats["populate_count"] += 1
            # Le code de population existant serait ici
            pass

    def profile_compute_scores(self):
        """📊 Profile le calcul des scores"""
        with self.profile_operation("compute_scores", warn_threshold=3.0):
            self.stats["compute_count"] += 1
            # Le code de calcul existant serait ici
            pass

    def cleanup_expired_cache(self):
        """🧹 Nettoie le cache expiré"""
        expired = self.process_cache.clear_expired()
        if expired > 0:
            logger.debug(f"🧹 {expired} entrées de cache expirées nettoyées")

    def get_performance_report(self):
        """📋 Génère un rapport de performance"""
        uptime = time.time() - self.start_time
        cache_stats = self.process_cache.get_stats()

        report = {
            "uptime_hours": uptime / 3600,
            "operations": {
                "scans": self.stats["scan_count"],
                "populations": self.stats["populate_count"],
                "computations": self.stats["compute_count"],
            },
            "cache": cache_stats,
            "performance_issues": {
                "slow_operations": len(self.stats["slow_operations"]),
                "memory_peaks": len(self.stats["memory_peaks"]),
            },
        }

        return report

    def log_performance_report(self):
        """📋 Log le rapport de performance"""
        report = self.get_performance_report()

        logger.info("=== RAPPORT PERFORMANCE ===")
        logger.info(f"⏱️ Uptime: {report['uptime_hours']:.1f}h")
        logger.info(
            f"📊 Opérations: Scans={report['operations']['scans']}, "
            f"Populations={report['operations']['populations']}, "
            f"Calculs={report['operations']['computations']}"
        )
        logger.info(
            f"💾 Cache: {report['cache']['size']}/{report['cache']['max_size']} "
            f"({report['cache']['usage_percent']:.1f}%)"
        )

        if report["performance_issues"]["slow_operations"] > 0:
            logger.warning(
                f"⚠️ {report['performance_issues']['slow_operations']} opérations lentes détectées"
            )

        if report["performance_issues"]["memory_peaks"] > 0:
            logger.warning(
                f"🧠 {report['performance_issues']['memory_peaks']} pics mémoire détectés"
            )

    def get_memory_optimization_tips(self):
        """💡 Suggestions d'optimisation mémoire"""
        tips = []

        # Analyse des pics mémoire
        if len(self.stats["memory_peaks"]) > 5:
            tips.append("🧠 Pics mémoire fréquents - Considérer un cache plus agressif")

        # Analyse des opérations lentes
        slow_ops = [op for op in self.stats["slow_operations"] if op["duration"] > 5]
        if len(slow_ops) > 3:
            tips.append("⚠️ Opérations lentes fréquentes - Optimiser les requêtes DB")

        # Analyse du cache
        cache_stats = self.process_cache.get_stats()
        if cache_stats["usage_percent"] > 90:
            tips.append(
                "💾 Cache proche de la limite - Augmenter la taille ou réduire le TTL"
            )

        return tips


# Instance globale
profiler = SurveillanceProfiler()


# Fonctions d'aide
def profile_operation(operation_name, warn_threshold=1.0):
    """🎯 Décorateur pour profiler une opération"""
    return profiler.profile_operation(operation_name, warn_threshold)


def get_process_info_cached(pid):
    """🎯 Version cachée de récupération d'infos processus"""
    return profiler.get_process_info_cached(pid)


def log_performance_report():
    """📋 Log le rapport de performance"""
    profiler.log_performance_report()


def cleanup_profiler():
    """🧹 Nettoie le profileur"""
    profiler.cleanup_expired_cache()


def get_optimization_tips():
    """💡 Obtient les conseils d'optimisation"""
    return profiler.get_memory_optimization_tips()
