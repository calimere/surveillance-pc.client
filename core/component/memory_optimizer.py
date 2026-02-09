#!/usr/bin/env python3
"""
🛠️ Techniques d'optimisation mémoire pour éviter les fuites
"""

import gc
import weakref
from collections import defaultdict
import threading
from contextlib import contextmanager


class MemoryOptimizer:
    """🧹 Optimiseur de mémoire avec techniques anti-fuites"""

    @staticmethod
    def force_garbage_collection():
        """🗑️ Force le nettoyage de la mémoire"""
        collected = gc.collect()
        return collected

    @staticmethod
    def get_object_counts():
        """🔍 Compte les objets par type (détection de fuites)"""
        counts = defaultdict(int)
        for obj in gc.get_objects():
            counts[type(obj).__name__] += 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True)[:20])

    @staticmethod
    def find_memory_leaks():
        """🔍 Détecte les fuites potentielles"""
        # Objets non référençables (cycles)
        unreachable = gc.collect()

        # Objets avec références circulaires
        referrers = []
        for obj in gc.garbage:
            refs = gc.get_referrers(obj)
            referrers.append((type(obj).__name__, len(refs)))

        return {
            "unreachable_objects": unreachable,
            "garbage_objects": len(gc.garbage),
            "circular_refs": referrers[:10],  # Top 10
        }


class ObjectPool:
    """♻️ Pool d'objets réutilisables pour éviter les allocations répétées"""

    def __init__(self, factory_func, max_size=100):
        self.factory = factory_func
        self.max_size = max_size
        self._pool = []
        self._lock = threading.Lock()

    def get(self):
        """Obtient un objet du pool"""
        with self._lock:
            if self._pool:
                return self._pool.pop()
            return self.factory()

    def put(self, obj):
        """Remet un objet dans le pool"""
        with self._lock:
            if len(self._pool) < self.max_size:
                # Nettoie l'objet avant remise en pool
                if hasattr(obj, "clear"):
                    obj.clear()
                elif hasattr(obj, "reset"):
                    obj.reset()
                self._pool.append(obj)


class WeakRefRegistry:
    """📝 Registre avec weak references pour éviter les fuites"""

    def __init__(self):
        self._refs = weakref.WeakSet()

    def register(self, obj):
        """Enregistre un objet avec weak ref"""
        self._refs.add(obj)

    def get_alive_count(self):
        """Nombre d'objets encore vivants"""
        return len(self._refs)

    def cleanup_dead_refs(self):
        """Nettoie les références mortes"""
        # WeakSet se nettoie automatiquement
        return len(self._refs)


@contextmanager
def memory_tracking(label="Operation"):
    """🔍 Context manager pour tracker la consommation mémoire"""
    import psutil

    process = psutil.Process()

    start_memory = process.memory_info().rss / 1024 / 1024
    print(f"🔍 {label} - Mémoire avant: {start_memory:.1f} MB")

    try:
        yield
    finally:
        end_memory = process.memory_info().rss / 1024 / 1024
        diff = end_memory - start_memory
        print(f"🔍 {label} - Mémoire après: {end_memory:.1f} MB (Δ{diff:+.1f} MB)")


# Techniques spécifiques d'optimisation


def optimize_list_operations(data_list):
    """📝 Optimise les opérations sur listes"""
    # ❌ Mauvais: concaténation répétée
    # result = ""
    # for item in data_list:
    #     result += str(item)

    # ✅ Bon: join est plus efficace
    return "".join(str(item) for item in data_list)


def optimize_dict_operations():
    """📚 Optimise les opérations sur dictionnaires"""
    # ✅ Utilise defaultdict pour éviter les vérifications répétées
    from collections import defaultdict

    # ❌ Mauvais
    # counts = {}
    # for item in items:
    #     if item in counts:
    #         counts[item] += 1
    #     else:
    #         counts[item] = 1

    # ✅ Bon
    counts = defaultdict(int)
    # for item in items:
    #     counts[item] += 1

    return counts


def optimize_generator_usage():
    """🔄 Utilise des générateurs pour économiser la mémoire"""

    # ❌ Mauvais: charge tout en mémoire
    def load_all_data():
        return [process_item(i) for i in range(10000)]

    # ✅ Bon: générateur économe
    def load_data_generator():
        for i in range(10000):
            yield process_item(i)

    return load_data_generator


def process_item(i):
    """Fonction exemple"""
    return f"item_{i}"


class LazyLoader:
    """💤 Chargement paresseux pour économiser la mémoire"""

    def __init__(self, loader_func):
        self._loader = loader_func
        self._data = None
        self._loaded = False

    @property
    def data(self):
        if not self._loaded:
            self._data = self._loader()
            self._loaded = True
        return self._data

    def clear(self):
        """Libère la mémoire"""
        self._data = None
        self._loaded = False


# Exemple d'usage pour votre système de surveillance
class ProcessCache:
    """💾 Cache optimisé pour les données de processus"""

    def __init__(self, max_size=1000, ttl_seconds=300):
        from collections import OrderedDict

        self._cache = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl_seconds
        self._lock = threading.RLock()

    def get(self, key):
        """Récupère un élément du cache"""
        with self._lock:
            if key in self._cache:
                # Déplace en fin (LRU)
                value, timestamp = self._cache.pop(key)

                # Vérifie TTL
                import time

                if time.time() - timestamp < self.ttl:
                    self._cache[key] = (value, timestamp)
                    return value

        return None

    def put(self, key, value):
        """Ajoute un élément au cache"""
        import time

        with self._lock:
            # Supprime le plus ancien si cache plein
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)

            self._cache[key] = (value, time.time())

    def clear_expired(self):
        """Nettoie les éléments expirés"""
        import time

        current_time = time.time()

        with self._lock:
            expired_keys = [
                key
                for key, (_, timestamp) in self._cache.items()
                if current_time - timestamp >= self.ttl
            ]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)

    def get_stats(self):
        """Statistiques du cache"""
        with self._lock:
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "usage_percent": (len(self._cache) / self.max_size) * 100,
            }
