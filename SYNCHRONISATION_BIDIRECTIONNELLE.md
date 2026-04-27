# Synchronisation Bidirectionnelle - Guide d'Implémentation

## 🎯 Réponse à votre question

**Question** : Comment effectuer une mise à jour efficace sur le client lorsque le serveur modifie la base de données et que le client a été déconnecté ?

**Réponse** : Une **stratégie hybride** combinant Push MQTT + Pull API est optimale.

---

## 💡 Architecture Implémentée

### **1. Stratégie Push (Temps Réel)**
- ✅ **Avantage** : Latence minimale quand connecté
- 📡 **Mécanisme** : MQTT topics `surveillance/[client]/server_changes`
- 🎯 **Usage** : Notifications instantanées des changements serveur

### **2. Stratégie Pull (Rattrapage)**  
- ✅ **Avantage** : Récupère tous les changements manqués
- 🔄 **Mécanisme** : API `GET /sync/changes?since=TIMESTAMP`
- 🎯 **Usage** : Démarrage, reconnexion, sync périodique

### **3. Résolution de Conflits**
- ⚖️ **Principe** : Comparaison timestamps + politique configurable
- 🏆 **Par défaut** : Serveur wins (`conflict_resolution = server_wins`)
- 🔀 **Alternative** : Client wins si besoin

---

## 🔄 Flux de Fonctionnement

### **Scénario 1: Client Connecté (Temps Réel)**
```
Serveur modifie processus #123
   ↓
Serveur publie sur MQTT: surveillance/client_A/server_changes
   ↓
Client A reçoit immédiatement et applique changement
   ↓ 
Résolution conflit si nécessaire (timestamp comparison)
```

### **Scénario 2: Client Déconnecté puis Reconnecté**
```
Client déconnecté pendant 2 heures
   ↓
Serveur modifie 50 enregistrements (stockés avec timestamps)
   ↓
Client reconnexion détectée (MQTT)
   ↓
Pull immédiat: GET /sync/changes?since=<last_sync>
   ↓
Application des 50 changements avec résolution conflits
   ↓
Mise à jour timestamp de dernière sync
```

### **Scénario 3: Sync Périodique (Sécurité)**
```
Toutes les 10 minutes (configurable)
   ↓
GET /sync/changes?since=<last_periodic_sync>
   ↓
Application changements éventuellement manqués
```

---

## 🗃️ Structure de Données

### **Table `sync_metadata`**
```sql
CREATE TABLE sync_metadata (
    smd_id INTEGER PRIMARY KEY,
    smd_key TEXT UNIQUE,           -- "last_server_sync_timestamp"  
    smd_value TEXT,                -- "2026-04-27T15:30:00"
    smd_updated DATETIME           -- Timestamp mise à jour
);
```

### **Colonnes de Sync sur Chaque Table**
```sql
-- Ajouté à toutes les tables (Process, ProcessInstance, etc.)
sync_status INTEGER DEFAULT 0,     -- 0=local, 1=synced, 2=error
sync_timestamp DATETIME,           -- Dernière modification
sync_version INTEGER DEFAULT 1     -- Gestion versions
```

### **Format Message MQTT Push**
```json
{
  "changes": [
    {
      "table": "process",
      "operation": "UPDATE",
      "timestamp": "2026-04-27T15:30:00",
      "data": {
        "id": 123,
        "prc_name": "chrome_updated.exe",
        "prc_is_dangerous": true
      }
    }
  ]
}
```

---

## 🎮 Configuration

### **config.ini**
```ini
[settings]
# Intervalle sync bidirectionelle (secondes)
bidirectional_sync_interval = 600

[sync]
# Résolution conflits: "server_wins" ou "client_wins"
conflict_resolution = server_wins
# Push temps réel via MQTT
enable_mqtt_push = true
```

---

## 🚀 APIs Serveur Nécessaires

### **1. Pull Changes**
```http
GET /api/sync/changes?since=2026-04-27T10:00:00&client_id=abc123

Response:
{
  "changes": [...],
  "server_timestamp": "2026-04-27T15:30:00"
}
```

### **2. Notify Client Changes**  
```http
POST /api/sync/client_changes
{
  "client_id": "abc123",
  "changes": [...]
}
```

### **3. Request Sync**
```http
POST /api/sync/request
{
  "client_id": "abc123", 
  "sync_type": "incremental"
}
```

---

## ✅ Avantages de cette Architecture

1. **🚀 Temps Réel** : MQTT push pour latence minimale
2. **🛡️ Résilient** : Pull API rattrape les déconnexions  
3. **⚖️ Intelligent** : Résolution conflits basée timestamps
4. **🔄 Automatique** : Sync sur reconnexion MQTT
5. **📊 Monitoré** : Statistiques dans logs système
6. **⚙️ Configurable** : Politiques de conflit modifiables

---

## 🎯 Réponse Finale

**Pour votre cas d'usage** :

- ✅ **Le serveur PUSH via MQTT** quand le client est connecté (temps réel)
- ✅ **Le client PULL automatiquement** lors des reconnexions et périodiquement  
- ✅ **Résolution intelligente des conflits** avec timestamps
- ✅ **Zero perte de données** même après longues déconnexions

Cette approche hybride est **plus efficace** qu'une solution pure push ou pull !