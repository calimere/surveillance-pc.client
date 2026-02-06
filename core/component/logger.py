"""
Module de logging centralisé avec rotation horaire des fichiers de log.
"""

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# Dossier de logs
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Configuration du logger principal
logger = logging.getLogger("surveillance")
logger.setLevel(logging.DEBUG)

# Format des logs
log_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Handler pour fichier avec rotation horaire
file_handler = TimedRotatingFileHandler(
    filename=LOG_DIR / "surveillance.log",
    when="H",  # Rotation toutes les heures
    interval=1,
    backupCount=168,  # Garde 168 heures (7 jours) de logs
    encoding="utf-8",
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(log_formatter)
file_handler.suffix = "%Y%m%d_%H"  # Format: surveillance.log.20260204_14

# Handler pour console (optionnel)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)

# Ajout des handlers
logger.addHandler(file_handler)
logger.addHandler(console_handler)


def get_logger(name: str = None):
    """
    Retourne un logger avec le nom spécifié.

    Args:
        name: Nom du module/composant (optionnel)

    Returns:
        Logger configuré
    """
    if name:
        return logging.getLogger(f"surveillance.{name}")
    return logger


def get_latest_log_file():
    """
    Retourne le chemin du fichier de log actuel.

    Returns:
        Path: Chemin du fichier de log actuel
    """
    return LOG_DIR / "surveillance.log"


def get_log_files(limit: int = None):
    """
    Retourne la liste des fichiers de logs triés par date (plus récent en premier).

    Args:
        limit: Nombre maximum de fichiers à retourner (optionnel)

    Returns:
        list[Path]: Liste des fichiers de logs
    """
    log_files = sorted(
        LOG_DIR.glob("surveillance.log*"), key=lambda f: f.stat().st_mtime, reverse=True
    )

    if limit:
        return log_files[:limit]
    return log_files


def read_log_file(file_path: Path = None, lines: int = None):
    """
    Lit le contenu d'un fichier de log.

    Args:
        file_path: Chemin du fichier (par défaut le fichier actuel)
        lines: Nombre de lignes à lire depuis la fin (optionnel)

    Returns:
        str: Contenu du fichier de log
    """
    if file_path is None:
        file_path = get_latest_log_file()

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            if lines:
                # Lit les N dernières lignes
                content = f.readlines()
                return "".join(content[-lines:])
            else:
                return f.read()
    except Exception as e:
        logger.error(f"Erreur lors de la lecture du fichier de log {file_path}: {e}")
        return ""


def tail_log(file_path: Path = None, callback=None):
    """
    Suit un fichier de log en temps réel (comme tail -f).

    Args:
        file_path: Chemin du fichier (par défaut le fichier actuel)
        callback: Fonction appelée pour chaque nouvelle ligne

    Yields:
        str: Nouvelles lignes du fichier
    """
    if file_path is None:
        file_path = get_latest_log_file()

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            # Va à la fin du fichier
            f.seek(0, 2)

            while True:
                line = f.readline()
                if line:
                    if callback:
                        callback(line)
                    yield line
                else:
                    # Pas de nouvelle ligne, attendre un peu
                    import time

                    time.sleep(0.1)
    except Exception as e:
        logger.error(f"Erreur lors du suivi du fichier de log {file_path}: {e}")


# Initialisation du logger au démarrage
logger.info("=" * 80)
logger.info("Système de logging initialisé")
logger.info(f"Dossier de logs: {LOG_DIR.absolute()}")
logger.info("=" * 80)
