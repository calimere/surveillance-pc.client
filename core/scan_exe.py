import os

from yarg import get

from core.db import add_executable, add_or_update_executable, get_all_exe, get_exe_by_name_path, update_executable
from core.mqtt_publish import publish_executable_add, publish_executable_update

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
    print("Scan des fichiers .exe...")
    exe_files = find_exe_files(common_dirs)

    if not first_scan_done and not avoid_scan_windows_folder:
        print("Scan du dossier Windows (premier scan)...")
        find_exe_files([r"C:\Windows"])
        first_scan_done = True

    for exe in exe_files:
        exe_name = os.path.basename(exe)
        exe_path = exe
        exe_is_system = exe.lower().startswith(r"c:\windows")
        #exe_icon = ""
        #exe_hash = ""
        #exe_signed_by = ""

        e = get_exe_by_name_path(exe_name, exe_path)
        if e is None:
            publish_executable_add(exe_name, exe_path)
            add_executable(exe_name, exe_path)
        else:
            if e[1] != exe_name or e[2] != exe_path:
                publish_executable_update(e[0], exe_name, exe_path)
                update_executable(e[0], exe_name, exe_path)
