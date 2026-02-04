# Système de Logging

## Vue d'ensemble

Le système de logging utilise le module `logging` de Python avec rotation horaire des fichiers. Les logs sont stockés dans le dossier `logs/` à la racine du projet.

## Configuration

### Rotation des fichiers
- **Rotation** : Toutes les heures
- **Conservation** : 168 heures (7 jours)
- **Format du nom** : `surveillance.log.YYYYMMDD_HH`
- **Encodage** : UTF-8

### Niveaux de log
- **DEBUG** : Informations détaillées pour le débogage
- **INFO** : Confirmations que tout fonctionne comme prévu
- **WARNING** : Avertissement d'un événement inattendu
- **ERROR** : Erreur sérieuse, le logiciel ne peut pas effectuer certaines fonctions
- **CRITICAL** : Erreur critique, le programme peut s'arrêter

### Format des logs
```
2026-02-04 14:30:45 | INFO     | surveillance.main | Démarrage de la surveillance...
```

## Utilisation

### Dans un module Python

```python
from core.logger import get_logger

# Créer un logger pour votre module
logger = get_logger("mon_module")

# Utiliser le logger
logger.debug("Message de debug")
logger.info("Information")
logger.warning("Avertissement")
logger.error("Erreur")
logger.critical("Erreur critique")
```

### Remplacement des print()

❌ **Avant** :
```python
print("Démarrage de l'application...")
print(f"Erreur: {e}")
```

✅ **Après** :
```python
logger.info("Démarrage de l'application...")
logger.error(f"Erreur: {e}")
```

## API du module logger

### `get_logger(name: str = None)`
Retourne un logger configuré.

**Paramètres** :
- `name` : Nom du module/composant (optionnel)

**Exemple** :
```python
logger = get_logger("scan_exe")
logger.info("Scan des fichiers...")
```

### `get_latest_log_file()`
Retourne le chemin du fichier de log actuel.

**Retour** : `Path` - Chemin du fichier de log actuel

### `get_log_files(limit: int = None)`
Retourne la liste des fichiers de logs triés par date (plus récent en premier).

**Paramètres** :
- `limit` : Nombre maximum de fichiers à retourner (optionnel)

**Retour** : `list[Path]` - Liste des fichiers de logs

### `read_log_file(file_path: Path = None, lines: int = None)`
Lit le contenu d'un fichier de log.

**Paramètres** :
- `file_path` : Chemin du fichier (par défaut le fichier actuel)
- `lines` : Nombre de lignes à lire depuis la fin (optionnel)

**Retour** : `str` - Contenu du fichier de log

**Exemple** :
```python
from core.logger import read_log_file, get_latest_log_file

# Lire les 100 dernières lignes du log actuel
content = read_log_file(lines=100)

# Lire un fichier de log spécifique
content = read_log_file(Path("logs/surveillance.log.20260204_14"))
```

### `tail_log(file_path: Path = None, callback=None)`
Suit un fichier de log en temps réel (comme `tail -f`).

**Paramètres** :
- `file_path` : Chemin du fichier (par défaut le fichier actuel)
- `callback` : Fonction appelée pour chaque nouvelle ligne

**Retour** : Generator qui yield les nouvelles lignes

**Exemple** :
```python
from core.logger import tail_log

def print_line(line):
    print(f"Nouvelle ligne: {line}")

# Suivre le fichier de log en temps réel
for line in tail_log(callback=print_line):
    # Traiter chaque nouvelle ligne
    pass
```

## Interface UI - Visualiseur de logs

L'application UI (`ui.py`) inclut un visualiseur de logs en temps réel avec les fonctionnalités suivantes :

### Fonctionnalités
- **Lecture en temps réel** : Affiche automatiquement les nouvelles lignes de log
- **Sélection de fichier** : Permet de naviguer entre les différents fichiers de logs
- **Pause/Reprendre** : Met en pause l'affichage des nouveaux logs
- **Actualiser** : Recharge la liste des fichiers de logs
- **Effacer** : Efface l'affichage (ne supprime pas les fichiers)
- **Interface sombre** : Style console avec coloration syntaxique

### Utilisation
1. Lancer l'application UI : `python ui.py`
2. L'onglet "📋 Logs" s'ouvre automatiquement
3. Les logs s'affichent en temps réel
4. Utilisez les boutons pour contrôler l'affichage

## Structure des dossiers

```
surveillance-pc/
├── logs/                           # Dossier des fichiers de log
│   ├── surveillance.log           # Fichier de log actuel
│   ├── surveillance.log.20260204_14
│   ├── surveillance.log.20260204_13
│   └── ...
├── core/
│   ├── logger.py                  # Module de logging
│   ├── scan_exe.py               # Utilise get_logger("scan_exe")
│   ├── db.py                     # Utilise get_logger("db")
│   └── ...
├── run.py                         # Utilise get_logger("main")
└── ui.py                          # Interface avec visualiseur de logs
```

## Conseils

### Niveaux de log appropriés

- **DEBUG** : Informations détaillées pour le développement
  ```python
  logger.debug(f"Exécutable existant : {exe_name}")
  logger.debug(f"Prochaine analyse dans {tempo_scan} secondes...")
  ```

- **INFO** : Événements normaux de l'application
  ```python
  logger.info("Démarrage de la surveillance...")
  logger.info("Scan des fichiers .exe...")
  logger.info("Processus surveillé arrêté : steam.exe")
  ```

- **WARNING** : Situations anormales mais gérables
  ```python
  logger.warning("MQTT non connecté, mise en queue du message")
  logger.warning("Processus dangereux détecté : malware.exe")
  ```

- **ERROR** : Erreurs qui empêchent une fonctionnalité
  ```python
  logger.error(f"Erreur lors du scan : {e}")
  logger.error("Impossible de se connecter à la base de données")
  ```

- **CRITICAL** : Erreurs critiques qui arrêtent l'application
  ```python
  logger.critical("Échec d'initialisation de la base de données")
  ```

### Performance

Le système de logging est optimisé pour minimiser l'impact sur les performances :
- Rotation automatique pour éviter les fichiers trop volumineux
- Buffering des écritures
- Thread séparé pour la lecture en temps réel dans l'UI

### Maintenance

Les anciens fichiers de log sont automatiquement supprimés après 7 jours. Pour modifier cette durée, ajustez le paramètre `backupCount` dans `logger.py` :

```python
file_handler = TimedRotatingFileHandler(
    # ...
    backupCount=168,  # 168 heures = 7 jours
)
```
