# 🎯 Architecture d'Endpoints API Spécialisés

## Problème résolu

**Avant :** Tous les messages convergent vers `/notifications` ou `/batch` 
**Maintenant :** Endpoints spécialisés selon le type de données

## 📍 Mapping des endpoints 

### 1. 🚨 **Security Alerts**
```
POST /api/security/alerts
POST /api/security/alerts/batch
```
**Usage :** Alertes de sécurité avec scores de risque
**Payload :**
```json
{
  "message_id": "uuid",
  "timestamp": "2026-04-13T...",
  "alert_type": "process_security", 
  "severity": "critical|high|medium|low",
  "process_name": "malware.exe",
  "risk_score": 25,
  "details": {...},
  "instance_id": 123
}
```

### 2. 🔄 **Process Events**
```
POST /api/processes/instances        # instance_created
POST /api/processes/events/start     # process_started  
POST /api/processes/events/stop      # process_stopped
POST /api/processes/instances/update # process_updated
POST /api/processes/events/generic   # fallback
```
**Usage :** Cycle de vie des processus
**Payload :**
```json
{
  "message_id": "uuid",
  "timestamp": "2026-04-13T...", 
  "event_type": "process_started",
  "process_instance": {
    "instance_id": 456,
    "process_name": "chrome.exe",
    "pid": 1234,
    "ppid": 567,
    "exe": "C:\\Program Files\\Google\\Chrome\\chrome.exe",
    "has_window": true
  },
  "metadata": {
    "source": "surveillance_client", 
    "version": "1.0"
  }
}
```

### 3. 💓 **System Heartbeat**
```
POST /api/system/heartbeat
POST /api/system/heartbeat/batch
```
**Usage :** Signalements de vie du client
**Payload :**
```json
{
  "message_id": "uuid",
  "timestamp": "2026-04-13T...",
  "client_status": "alive",
  "system_info": {...},
  "metrics": {
    "uptime": "5d 12h 30m",
    "cpu_usage": 15.2,
    "memory_usage": 67.8
  }
}
```

### 4. 📢 **General Notifications** 
```
POST /api/notifications/general
POST /api/notifications/general/batch
```
**Usage :** Notifications diverses
**Payload :**
```json
{
  "message_id": "uuid",
  "timestamp": "2026-04-13T...",
  "notification_type": "general",
  "message": "System status update", 
  "severity": "info",
  "data": {...}
}
```

### 5. 🔧 **Generic Fallback**
```
POST /api/events/generic
```
**Usage :** Types non reconnus
**Payload :**
```json
{
  "message_id": "uuid", 
  "timestamp": "2026-04-13T...",
  "event_type": "generic",
  "raw_data": {...}
}
```

## 📦 **Batch Endpoints**

Chaque endpoint principal a sa version batch :
- `/security/alerts/batch`
- `/processes/events/start/batch` 
- `/system/heartbeat/batch`
- etc.

**Format batch :**
```json
{
  "batch_id": "uuid",
  "batch_timestamp": "2026-04-13T...",
  "item_count": 15,
  "endpoint_type": "security_alerts",
  "items": [
    {...payload1...},
    {...payload2...},
    {...payload3...}
  ]
}
```

## 🎯 **Avantages de cette architecture**

### ✅ **Scalabilité spécialisée**
- Load balancing par type de données
- Scaling horizontal ciblé 
- Optimisations par endpoint

### ✅ **Monitoring granulaire**
- Métriques par type d'événement
- Alerting spécialisé  
- SLA différenciés

### ✅ **Traitement optimisé** 
- Logique métier spécialisée
- Validation adaptée
- Storage optimisé

### ✅ **Sécurité renforcée**
- Rate limiting par type
- Authentification forte sur security alerts
- Audit trail détaillé

### ✅ **Maintenance facilitée**
- Code découplé par domaine
- Déploiements indépendants
- Tests ciblés

## ⚙️ **Configuration côté serveur**

### Rate Limiting suggéré
```yaml
/security/alerts:     10 req/min  # Strict - alertes critiques
/processes/events:    100 req/min # Normal - événements fréquents  
/system/heartbeat:    6 req/min   # Spacé - toutes les 10s max
/notifications:       50 req/min  # Modéré - notifications diverses
```

### Timeouts différenciés
```yaml
security_alerts:  15s  # Plus de temps pour traitement critique
process_events:   8s   # Standard
heartbeat:        3s   # Rapide - simple ping
notifications:    5s   # Standard
```

### Storage spécialisé  
```yaml
security_alerts:  → Elasticsearch + Alerting
process_events:   → Time-series DB (InfluxDB)
heartbeat:        → Redis (TTL courte) 
notifications:    → PostgreSQL standard
```

## 🚀 **Migration progressive**

1. **Phase 1 :** Garder l'ancien `/notifications` en parallèle
2. **Phase 2 :** Router selon `message_type` 
3. **Phase 3 :** Déprécier l'ancien endpoint
4. **Phase 4 :** Suppression complète

## 📊 **Monitoring recommandé**

```grafana
- security_alerts_per_minute
- process_events_throughput  
- heartbeat_gaps_detected
- endpoint_response_times_p95
- batch_vs_individual_ratio
```

Cette architecture offre une base solide pour une montée en charge spécialisée et un monitoring fin ! 🎯