# 📋 Contrat API — Client Python ↔ .NET Backend

## Architecture globale

```
React Dashboard
    │  GET /api/processes (liste)
    │  GET /api/processes/running
    │  POST /api/commands/block  ──────────────────────────────┐
    ▼                                                           ▼
.NET REST API ──── HTTP ────► Python Client          .NET publie MQTT
    │                           (envoie données)     surveillance/[client_id]/cmd
    ▼
SQL Server / PostgreSQL
(copie des données du client)
```

---

## 1. Endpoints reçus depuis le client Python (push)

### POST /api/processes/add
Envoyé par le **sync_worker** quand de nouveaux processus sont détectés.

```json
{
  "processes": [
    {
      "prc_id": 42,
      "prc_name": "chrome.exe",
      "prc_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "prc_program_name": "chrome.exe",
      "prc_first_seen": "2026-04-13T10:00:00",
      "prc_is_unknown": false,
      "prc_is_watched": false,
      "prc_is_dangerous": false,
      "prc_blocked": false,
      "prc_is_running": true
    }
  ]
}
```

**Réponse attendue :** `200 OK`

---

### POST /api/process_instances/add
Envoyé par le **sync_worker** pour les nouvelles instances.

```json
{
  "instances": [
    {
      "pri_id": 101,
      "prc_id": 42,
      "pri_timestamp": "2026-04-13T10:01:00",
      "pri_pid": 1234,
      "pri_ppid": 567,
      "pri_start_time": "2026-04-13T10:00:58",
      "pri_owner": "DESKTOP\\Remy",
      "pri_has_window": true,
      "pri_signed": true,
      "pri_signed_by": "Google LLC",
      "pri_signed_thumbprint": "ABCDEF...",
      "pri_signed_is_ev": false,
      "pri_weird_path": false,
      "pri_is_running": true,
      "pri_score": 0
    }
  ]
}
```

**Réponse attendue :** `200 OK`

---

### POST /api/processes/events/start
Envoyé par le **queue_worker** quand un processus démarre.

```json
{
  "message_id": "uuid",
  "timestamp": "2026-04-13T10:01:00",
  "event_type": "process_started",
  "process_instance": {
    "instance_id": 101,
    "process_name": "chrome.exe",
    "pid": 1234,
    "ppid": 567,
    "exe": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "has_window": true
  }
}
```

---

### POST /api/processes/events/stop
Même structure, `event_type: "process_stopped"`.

---

### POST /api/security/alerts
Envoyé quand le score de risque dépasse le seuil.

```json
{
  "message_id": "uuid",
  "timestamp": "2026-04-13T10:01:00",
  "alert_type": "process_security",
  "severity": "high",
  "process_name": "suspicious.exe",
  "risk_score": 15,
  "instance_id": 101,
  "details": {}
}
```

---

### POST /api/system/heartbeat
Envoyé toutes les ~10 minutes.

```json
{
  "message_id": "uuid",
  "timestamp": "2026-04-13T10:01:00",
  "client_id": "uuid-du-client",
  "client_status": "alive",
  "metrics": {
    "cpu_usage": 12.5,
    "memory_usage": 45.2
  }
}
```

---

## 2. Endpoints consommés par le Dashboard React (lecture)

### GET /api/processes/running
Liste des processus actuellement en cours d'exécution.

**Réponse :**
```json
[
  {
    "prc_id": 42,
    "prc_name": "chrome.exe",
    "prc_path": "C:\\Program Files\\...",
    "prc_is_watched": false,
    "prc_blocked": false,
    "prc_is_dangerous": false,
    "running_instances": [
      {
        "pri_id": 101,
        "pri_pid": 1234,
        "pri_owner": "DESKTOP\\Remy",
        "pri_score": 0,
        "pri_signed": true,
        "pri_signed_by": "Google LLC"
      }
    ]
  }
]
```

---

### GET /api/processes
Tous les processus jamais vus (historique complet).

**Query params optionnels :**
- `?page=1&limit=50`
- `?search=chrome`
- `?blocked=true`
- `?dangerous=true`

---

### GET /api/processes/{prc_id}
Détail d'un processus avec son historique d'instances et d'événements.

---

### GET /api/security/alerts
Liste des alertes de sécurité.

**Query params :** `?severity=high&since=2026-04-13`

---

## 3. Endpoint de commande (Dashboard → .NET → MQTT)

### POST /api/commands/block
Le dashboard envoie cette requête, le .NET publie le message MQTT correspondant.

**Body :**
```json
{
  "prc_id": 42,
  "process_name": "suspicious.exe",
  "client_id": "uuid-du-client"
}
```

**Le .NET publie ensuite sur Mosquitto :**
- Topic : `surveillance/{client_id}/cmd`
- Payload :
```json
{
  "command": "set_blocked",
  "prc_id": 42,
  "process_name": "suspicious.exe"
}
```

---

### POST /api/commands/unblock
Même principe, payload `"command": "unset_blocked"`.

### POST /api/commands/watch
Payload `"command": "set_watched"`.

### POST /api/commands/unwatch
Payload `"command": "unset_watched"`.

---

## 4. Topics MQTT

| Topic | Direction | Usage |
|---|---|---|
| `surveillance/{client_id}/cmd` | Serveur → Client | Commandes (block, watch...) |
| `surveillance/{client_id}/ack` | Client → Serveur | Accusé de réception |
| `surveillance/{client_id}/uptime` | Client → Serveur | Heartbeat périodique |
| `surveillance/{client_id}/alert` | Client → Serveur | Alertes sécurité temps réel |
| `surveillance/{client_id}/process` | Client → Serveur | Événements processus |
| `surveillance/{client_id}/heartbeat` | Client → Serveur | Métriques système |

---

## 5. Payload de commande MQTT (Client reçoit)

```json
{
  "command": "set_blocked | unset_blocked | set_watched | unset_watched",
  "prc_id": 42,
  "process_name": "suspicious.exe"
}
```

Le client répond sur `surveillance/{client_id}/ack` :
```json
{
  "status": "ok | error",
  "message": "Processus 'suspicious.exe' bloqué. 2 instance(s) tuée(s).",
  "original_command": { ... }
}
```
