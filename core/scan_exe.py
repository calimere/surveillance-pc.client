import os

from core.db import add_or_update_executable, get_all_exe

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
        add_or_update_executable(exe_name, exe)