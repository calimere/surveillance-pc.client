#!/usr/bin/env python3
"""
🧪 Test complet du monitoring et optimisation mémoire
"""

import sys
import os
import time
import gc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.component.memory_monitor import MemoryMonitor
from core.component.memory_optimizer import MemoryOptimizer, ProcessCache, ObjectPool
from core.component.surveillance_profiler import SurveillanceProfiler, profile_operation
from core.component.logger import get_logger

logger = get_logger("memory_test")


def simulate_memory_usage():
    """🎯 Simule différents patterns d'utilisation mémoire"""

    print("🧪 Test de Monitoring et Optimisation Mémoire")
    print("=" * 60)

    # 1. Test du monitoring de base
    print("\n1️⃣ Test du monitoring mémoire de base")
    monitor = MemoryMonitor(check_interval=1, history_size=20)
    monitor.start_monitoring()

    # Simulation de consommation
    data_lists = []
    for i in range(5):
        print(f"   Ajout de données batch {i + 1}...")
        # Simule l'ajout de processus
        batch = [f"process_{j}" for j in range(1000)]
        data_lists.append(batch)
        time.sleep(1.2)

    # Rapport mémoire
    monitor.log_memory_report()
    monitor.stop_monitoring()

    # 2. Test d'optimisation
    print("\n2️⃣ Test des optimisations")

    # Test pool d'objets
    print("   🏊 Test du pool d'objets...")

    def create_dict():
        return {}

    pool = ObjectPool(create_dict, max_size=10)

    # Utilise le pool au lieu de créer des objets
    objects = []
    for i in range(20):
        obj = pool.get()
        obj[f"key_{i}"] = f"value_{i}"
        objects.append(obj)

    # Remet dans le pool
    for obj in objects:
        pool.put(obj)

    print("   ✅ Pool testé")

    # Test cache optimisé
    print("   💾 Test du cache optimisé...")
    cache = ProcessCache(max_size=100, ttl_seconds=5)

    # Simule la mise en cache de processus
    for i in range(50):
        cache.put(
            f"pid_{i}", {"name": f"process_{i}", "memory": i * 1024, "cpu": i * 0.1}
        )

    cache_stats = cache.get_stats()
    print(
        f"   Cache: {cache_stats['size']}/{cache_stats['max_size']} "
        f"({cache_stats['usage_percent']:.1f}%)"
    )

    # Attendre expiration
    print("   ⏳ Attente expiration TTL...")
    time.sleep(6)
    expired = cache.clear_expired()
    print(f"   🧹 {expired} entrées expirées nettoyées")

    # 3. Test du profileur
    print("\n3️⃣ Test du profileur avancé")
    profiler = SurveillanceProfiler()

    with profiler.profile_operation("test_heavy_operation", warn_threshold=0.5):
        # Simule une opération lourde
        heavy_data = []
        for i in range(10000):
            heavy_data.append(
                {"id": i, "data": f"test_data_{i}" * 10, "timestamp": time.time()}
            )
        time.sleep(1)  # Force à dépasser le seuil

    with profiler.profile_operation("test_light_operation", warn_threshold=2.0):
        # Simule une opération légère
        light_data = [i for i in range(100)]
        time.sleep(0.1)

    profiler.log_performance_report()

    # 4. Test de détection de fuites
    print("\n4️⃣ Test de détection de fuites")

    # Créer des objets qui pourraient causer des fuites
    leak_objects = []
    for i in range(1000):
        obj = {"id": i, "data": [j for j in range(100)], "refs": []}
        # Créer des références circulaires
        obj["refs"].append(obj)
        leak_objects.append(obj)

    print("   📊 Objets avant nettoyage:")
    counts_before = MemoryOptimizer.get_object_counts()
    for obj_type, count in list(counts_before.items())[:5]:
        print(f"     {obj_type}: {count}")

    # Nettoyage forcé
    collected = MemoryOptimizer.force_garbage_collection()
    print(f"   🗑️ {collected} objets collectés par le GC")

    # Vérification après nettoyage
    print("   📊 Objets après nettoyage:")
    counts_after = MemoryOptimizer.get_object_counts()
    for obj_type, count in list(counts_after.items())[:5]:
        print(f"     {obj_type}: {count}")

    # Détection de fuites
    leak_info = MemoryOptimizer.find_memory_leaks()
    print(f"   🔍 Objets non atteignables: {leak_info['unreachable_objects']}")
    print(f"   🔍 Objets dans le garbage: {leak_info['garbage_objects']}")

    # 5. Conseils d'optimisation
    print("\n5️⃣ Conseils d'optimisation")
    tips = profiler.get_memory_optimization_tips()
    if tips:
        for tip in tips:
            print(f"   💡 {tip}")
    else:
        print("   ✅ Aucun problème majeur détecté")

    # 6. Rapport final
    print("\n6️⃣ Rapport mémoire final")
    final_usage = monitor.get_current_usage()
    if final_usage:
        print(f"   💾 RAM finale: {final_usage['rss_mb']:.1f} MB")
        print(f"   📊 Pourcentage système: {final_usage['percent']:.1f}%")
        print(f"   🆓 RAM disponible: {final_usage['available_mb']:.1f} MB")

    print("\n🎯 Test terminé !")

    # Nettoyage final
    del data_lists, heavy_data, light_data, leak_objects
    gc.collect()


def test_memory_tracking_decorator():
    """🎯 Test du décorateur de tracking mémoire"""
    print("\n🔍 Test du décorateur de tracking mémoire")

    from core.component.memory_optimizer import memory_tracking

    with memory_tracking("Test allocation massive"):
        # Simule une allocation massive
        big_list = [i * "data" for i in range(100000)]

    with memory_tracking("Test allocation légère"):
        # Simule une allocation légère
        small_list = [i for i in range(1000)]


if __name__ == "__main__":
    try:
        simulate_memory_usage()
        test_memory_tracking_decorator()
    except Exception as e:
        logger.error(f"Erreur dans le test: {e}")
        import traceback

        traceback.print_exc()
