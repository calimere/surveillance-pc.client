import os
from business import EExeEventType
from core.db import add_executable, add_notification, get_exe_by_name_path, set_executable_watched_dangerous
from core.mqtt_publish import publish_executable_add, publish_executable_event, publish_executable_event, publish_executable_update, publish_notification
import win32ui
import win32gui
import pefile
import hashlib
from core.logger import get_logger

logger = get_logger("scan_exe")

def find_exe_files(start_dirs):
    exe_files = []
    for start_dir in start_dirs:
        for root, dirs, files in os.walk(start_dir):
            for file in files:
                if file.lower().endswith('.exe'):
                    exe_files.append(os.path.join(root, file))
    return exe_files

# Dossiers courants où les programmes et jeux sont souvent installés
common_dirs = [
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\Users\%USERNAME%\AppData",
    # Steam
    r"C:\Program Files (x86)\Steam\steamapps\common",
    r"D:\SteamLibrary\steamapps\common",  # Chemin alternatif courant
    # Epic Games
    r"C:\Program Files\Epic Games",
    r"D:\Epic Games",  # Chemin alternatif courant
    # Ubisoft Connect
    r"C:\Program Files (x86)\Ubisoft\Ubisoft Game Launcher\games",
    r"D:\Ubisoft\games",  # Chemin alternatif courant
    # Battle.net (Blizzard)
    r"C:\Program Files (x86)\Battle.net",
    r"C:\Program Files (x86)\Blizzard Entertainment",
    r"D:\Battle.net",  # Chemin alternatif courant
    # Microsoft Store (jeux installés via WindowsApps)
    r"C:\Program Files\WindowsApps",
]

# Expansion de la variable d'environnement %USERNAME%
common_dirs = [os.path.expandvars(d) for d in common_dirs]

first_scan_done = False
def scan_exe(avoid_scan_windows_folder=True):
    global first_scan_done
    logger.info("Scan des fichiers .exe...")
    exe_files = find_exe_files(common_dirs)

    if not first_scan_done and not avoid_scan_windows_folder:
        logger.info("Scan du dossier Windows (premier scan)...")
        find_exe_files([r"C:\Windows"])
        first_scan_done = True

    for exe in exe_files:
        exe_name = os.path.basename(exe)
        exe_path = exe
        exe_is_system = exe.lower().startswith(r"c:\windows")
        exe_icon = get_exe_icon(exe_path)
        exe_hash = get_exe_hash(exe_path)
        exe_signed_by = get_exe_signature(exe_path)

        e = get_exe_by_name_path(exe_name, exe_path)
        if e is None:
            exe = add_executable(exe_name, exe_path, exe_hash, exe_signed_by, exe_icon, exe_is_system)
            publish_executable_add(exe)
        else:
            logger.debug(f"Exécutable existant : {exe_name}")
            if e.exe_hash != exe_hash or e.exe_signed_by != exe_signed_by:
                logger.warning(f"L'exécutable a changé : {exe_name}")
                publish_executable_event(e.exe_id, EExeEventType.HASH_CHANGE if e.exe_hash != exe_hash else EExeEventType.SIGNATURE_CHANGE)
                publish_notification(e.exe_id, f"L'exécutable '{exe_name}' a changé. Nouveau hash ou signature détecté.")
                notification = add_notification(e.exe_id, f"L'exécutable '{exe_name}' a changé. Nouveau hash ou signature détecté.")
                exe = set_executable_watched_dangerous(e.exe_id)
                publish_executable_update(exe)
            
def get_exe_icon(file_path):
    try:
        large, _ = win32gui.ExtractIconEx(file_path, 0)
        if large:
            icon = large[0]
            hdc = win32ui.CreateDCFromHandle(win32ui.GetDC(0))
            bmp = win32ui.CreateBitmap()
            bmp.CreateCompatibleBitmap(hdc, 32, 32)
            hdc.SelectObject(bmp)
            hdc.DrawIcon((0, 0), icon)
            return bmp
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'icône pour {file_path}: {e}")
    return None

def get_exe_hash(file_path):
    """
    Generates a SHA-256 hash for the given executable file.

    Args:
        file_path (str): The path to the executable file.

    Returns:
        str: The SHA-256 hash of the file in hexadecimal format, or None if an error occurs.
    """

    try:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        logger.error(f"Erreur lors de la génération du hash pour {file_path}: {e}")
    return None

def get_exe_signature(file_path):
    """
    Extracts the Authenticode signature from a given executable file.

    This function attempts to parse the Portable Executable (PE) file located at the specified
    file path and retrieve its Authenticode signature, if present. The Authenticode signature
    is typically used to verify the authenticity and integrity of the executable.

    Args:
        file_path (str): The path to the executable file to analyze.

    Returns:
        bytes: The Authenticode certificate data if found, otherwise None.

    Note:
        - If the file cannot be parsed as a PE file or if the Authenticode signature is not
          present, the function will return None.
        - Any exceptions encountered during the process are caught and logged to the console.
    """
    try:
        pe = pefile.PE(file_path)
        if hasattr(pe, 'DIRECTORY_ENTRY_SECURITY'):
            for entry in pe.DIRECTORY_ENTRY_SECURITY:
                if entry.name == b"Authenticode":
                    return entry.cert
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la signature pour {file_path}: {e}")
    return None