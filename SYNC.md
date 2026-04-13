# 🔄 Système de Synchronisation Base Locale → Base Distante

## Vue d'ensemble

Le système de synchronisation garantit que toutes les données collectées localement sont transmises vers la base distante via MQTT ou HTTP (fallback).

## Architecture

```
Base Locale (SQLite)
       ↓
   Sync Worker (background thread)
       ↓
   Décision intelligente: MQTT ou HTTP
       ↓  
   Base Distante
```

### Composants

1. **Sync Worker** : Thread en arrière-plan qui synchronise périodiquement
2. **Champs de synchronisation** : Chaque enregistrement a `sync_status`, `sync_timestamp`, `sync_version`
3. **Retry intelligent** : Backoff exponentiel pour les échecs
4. **Stats en temps réel** : Suivi des performances et erreurs

## États de synchronisation

- `sync_status = 0` : Non synchronisé (nouveau)
- `sync_status = 1` : Synchronisé avec succès  
- `sync_status = 2` : Erreur de synchronisation (retry plus tard)

## Configuration

### Dans config.ini

```ini
[settings]
tempo_sync = 300        # Intervalle de sync en secondes (défaut: 5 min)
mqtt_enabled = 1        # 1=activé, 0=HTTP seulement

[mqtt]
host = broker.mqtt.com
port = 1883
user = username
password = password

[api]  
url = https://api.surveillance-pc.example.com
```

## Tables synchronisées

1. **Processes** : Métadonnées des processus détectés
2. **ProcessInstances** : Instances de processus en cours/arrêtés  
3. **ProcessEvents** : Événements START/STOP
4. **Queue** : Messages de notification en attente

## Ordre de priorité

1. **ProcessEvents** (plus urgent) → START/STOP temps réel
2. **ProcessInstances** → Nouvelles détections  
3. **Processes** → Métadonnées processus
4. **Queue** → Notifications diverses

## Logique de retry

- **1er échec** : Retry dans 1 minute
- **2ème échec** : Retry dans 2 minutes  
- **3ème échec** : Retry dans 4 minutes
- **4ème échec** : Retry dans 8 minutes
- **5ème+ échec** : Retry dans 30 minutes (max)

## Basculement MQTT → HTTP

Le système bascule automatiquement vers HTTP quand :
- MQTT broker indisponible
- Erreurs de connexion MQTT répétées
- Timeout sur publication MQTT

## Fonctions utilitaires

### Force sync
```python
from core.component.sync_worker import force_sync
force_sync()  # Force synchronisation immédiate
```

### Re-marquer pour sync
```python
from core.component.sync_worker import mark_for_resync

mark_for_resync("processes")          # Tous les processus
mark_for_resync("instances", 123)     # Instance spécifique
mark_for_resync("events")             # Tous les événements
```

### Reset erreurs  
```python
from core.component.sync_worker import reset_sync_errors
reset_sync_errors()  # Remet sync_status=2 à sync_status=0
```

### Stats de sync
```python
from core.component.sync_worker import get_sync_stats
stats = get_sync_stats()
print(f"Total synchronisé: {stats['total_synced']}")
print(f"En attente: {stats['unsync_records']}")
```

## Monitoring

### Logs de synchronisation
```
[INFO] 🔄 Sync Worker démarré avec intervalle de 300s
[INFO] ✅ 15 enregistrements synchronisés en 2.34s  
[DEBUG] 🔄 Synchronisation de 8 événements...
[WARN] ❌ Échec sync processus 123: Connection timeout
```

### Stats périodiques
Toutes les 10 minutes, les stats sont affichées :
```
[INFO] 📊 Sync stats: 1247 synced, {'processes': 2, 'events': 5} pending
```

## Résolution problèmes

### Beaucoup d'échecs de sync
1. Vérifier connexion MQTT/HTTP
2. Augmenter `tempo_sync` si surcharge
3. Utiliser `reset_sync_errors()` pour relancer

### Données non synchronisées  
1. Vérifier les logs pour erreurs
2. Forcer sync avec `force_sync()`
3. Vérifier `sync_status` en BDD

### Performance dégradée
1. Réduire `tempo_sync` si besoin de réactivité
2. Augmenter si trop de charge système
3. Monitorer les stats de durée de sync

## Intégration dans run.py

Le sync worker se lance automatiquement :

```python
# Démarrage automatique
sync_worker = get_sync_worker(sync_interval)

# Arrêt propre  
stop_sync_worker()
```

## Exemple de flux complet

1. **Nouvelle instance détectée** → `add_process_instance()` → `sync_status=0`
2. **Sync Worker** détecte enregistrement non-sync
3. **Tentative MQTT** → Si succès: `sync_status=1`, sinon essai HTTP  
4. **Si HTTP échoue** → `sync_status=2` + retry programmé
5. **Retry ultérieur** avec backoff exponentiel

Cette architecture garantit qu'aucune donnée n'est perdue et que le système s'adapte aux conditions réseau variables.