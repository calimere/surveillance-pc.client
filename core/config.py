import os
import sys
import configparser
import socket

def get_base_path():
    """Retourne le dossier de l'exécutable ou du script"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(sys.argv[0]))

def get_app_data_dir():
    """Retourne le dossier utilisateur pour stocker les données"""
    return os.path.join(
        os.getenv("APPDATA") or os.path.expanduser("~/.config"),
        "surveillance-pc"
    )

def get_config_path():
    """Chemin absolu vers config.ini"""
    base_path = get_base_path()
    return os.path.join(base_path, "config.ini")

def get_db_path():
    """Construit le chemin absolu de la DB SQLite"""
    app_data_dir = get_app_data_dir()
    os.makedirs(app_data_dir, exist_ok=True)
    db_filename = config.get("paths", "db_path", fallback="watch.db")
    return os.path.join(app_data_dir, db_filename)

def get_pc_alias():
    return os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or socket.gethostname()

# Charger la config une seule fois
config = configparser.ConfigParser()
config.read(get_config_path())

