# 🛡️ Système de Circuit Breaker et Backoff Exponentiel

## Problème résolu

**Avant :** Quand l'API distante est indisponible (pas de réseau), l'application bombardait le serveur avec des dizaines d'appels HTTP/MQTT sans pause, créant une surcharge de threads de retry.

**Maintenant :** Circuit breakers intelligents avec backoff exponentiel qui détectent les pannes et ajustent automatiquement la fréquence des tentatives.

## 🔧 Architecture de circuit breaker

### États du circuit breaker
```
CLOSED (normal) → OPEN (panne détectée) → HALF_OPEN (test de récupération)
     ↑                                                      ↓
     ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←
```

### ⚙️ Configuration par défaut

**API Circuit Breaker :**
- `failure_threshold`: 5 échecs consécutifs  
- `timeout`: 30s minimum avant retry
- `max_backoff`: 5 minutes maximum

**MQTT Circuit Breaker :**
- `failure_threshold`: 3 échecs consécutifs
- `timeout`: 15s minimum avant retry  
- `max_backoff`: 2 minutes maximum

## 📊 Logique de backoff exponentiel

### Calcul du délai de retry
```python
base_delay = 2 ** retry_count    # 1s, 2s, 4s, 8s, 16s, 32s
jitter = uniform(0.5, 1.5)       # Évite thundering herd
final_delay = min(base_delay * jitter, max_delay)
```

### Augmentation selon l'état du système
- **Un canal down** : délai normal
- **Tous canaux down** : minimum 30s  
- **Circuit breaker ouvert** : respect du timeout du breaker

## 🚦 Protection contre la surcharge de threads

### Limitation des threads de retry
- **Maximum concurrent** : 5 threads de retry actifs
- **Dépassement** : items remis en queue au lieu de créer de nouveaux threads
- **Priorité dégradée** : retry items ont priorité plus basse

### Monitoring des threads
```python
worker.get_circuit_breaker_status()
# Retourne nombre de threads actifs et état des breakers
```

## 📈 Comportement adaptatif 

### Détection automatique de panne
1. **5 échecs API** → Circuit breaker API ouvert pour 30s - 5min
2. **3 échecs MQTT** → Circuit breaker MQTT ouvert pour 15s - 2min
3. **Backoff croissant** : 30s, 60s, 120s, 240s, 300s (max)

### Récupération automatique  
1. **Timer expiré** → Passage en `half_open`
2. **Premier succès** → Retour en `closed` + reset compteurs
3. **Échec en half_open** → Retour en `open` avec nouveau délai

## 🎯 Avantages de cette approche

### ✅ **Protection réseau**
- Évite le bombardement de serveurs indisponibles
- Réduit la charge réseau inutile
- Respecte les serveurs en difficulté

### ✅ **Performance système**  
- Limitation des threads = moins de contention
- Pas d'accumulation de threads de retry
- CPU préservé pour le traitement principal

### ✅ **Résilience intelligente**
- Détection automatique des pannes
- Récupération progressive et testée
- Priorité préservée pour messages critiques

### ✅ **Monitoring intégré**
- Statut temps réel des breakers  
- Compteurs de performance
- Logs détaillés des transitions d'état

## 📊 Logs de debugging

### Transitions de circuit breaker
```
[WARN] 🚫 API circuit breaker OPEN for 60s after 5 failures
[INFO] 🔄 API circuit breaker: open → half_open  
[INFO] 🔄 API recovered after 7 failures
```

### Limitation de threads
```
[DEBUG] Max retry threads (5) reached, queueing for later
[DEBUG] Both API and MQTT down, increasing retry delay to 45.3s
[DEBUG] Scheduled retry #3 for item-uuid in 8.7s (priority 7)
```

### Stats en temps réel
```python
status = worker.get_circuit_breaker_status()
print(f"API: {status['api']['state']} ({status['api']['failure_count']} failures)")  
print(f"MQTT: {status['mqtt']['state']} (next retry in {status['mqtt']['time_until_retry']:.0f}s)")
print(f"Active retry threads: {status['active_retry_threads']}/{status['max_retry_threads']}")
```

## ⚡ Impact sur les performances

### Réduction drastique des appels inutiles
- **Avant** : 100+ tentatives/minute quand API down
- **Maintenant** : 2-4 tentatives/minute avec backoff intelligent

### Préservation des ressources
- **Threads** : Maximum 5 au lieu de potentiellement illimités  
- **CPU** : Pas de surcharge de création/destruction de threads
- **Réseau** : Pas de spam inutile vers serveurs indisponibles

### Priorisation intelligente
- **Security alerts** : Priorité préservée même en retry
- **Heartbeat** : Priorité basse, s'efface en cas de surcharge
- **Process events** : Priorité normale avec dégradation progressive

Cette architecture garantit une montée en charge contrôlée et une résilience face aux pannes réseau ! 🎯