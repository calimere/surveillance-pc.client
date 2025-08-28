import os
import sqlite3
import datetime
import psutil  # pip install psutil

APP_DATA_DIR = os.path.join(os.getenv('APPDATA') or os.path.expanduser('~/.config'), 'surveillance-pc')
DB_PATH = os.path.join(APP_DATA_DIR, "watch.db")

def init_db():

    print("Initialisation de la base de données...")

    if os.path.exists(DB_PATH):
        print("Base de données déjà initialisée.")
        return
    
    print(f"Création de la base de données à {DB_PATH}...")
    os.makedirs(APP_DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS exe_list (
            exe_id INTEGER PRIMARY KEY AUTOINCREMENT,
            exe_name TEXT NOT NULL,
            exe_path TEXT NOT NULL,
            exe_program_name TEXT NOT NULL,
            exe_type INTEGER NULL,
            exe_first_seen TIMESTAMP NOT NULL,
            exe_last_seen TIMESTAMP NOT NULL,
            exe_still_installed BOOLEAN NOT NULL,
            exe_watch BOOLEAN NOT NULL DEFAULT 0,
            exe_launched BOOLEAN NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS exe_event (
            eev_id INTEGER PRIMARY KEY AUTOINCREMENT,
            exe_id INTEGER NOT NULL,
            eev_type INTEGER NOT NULL,
            eev_timestamp TIMESTAMP NOT NULL,
            FOREIGN KEY(exe_id) REFERENCES exe_list(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS exe_type (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type_name TEXT NOT NULL UNIQUE,
        description TEXT
        )""")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS unknown_exe (
            uex_id INTEGER PRIMARY KEY AUTOINCREMENT,
            uex_process_name TEXT NOT NULL,
            uex_process_path TEXT,
            uex_first_seen TIMESTAMP NOT NULL,
            uex_last_seen TIMESTAMP NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()
    print(f"Base de données créée à {DB_PATH}.")

def get_watch_processes():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT exe_name, exe_path, exe_id, exe_launched FROM exe_list WHERE exe_watch=1")
    rows = cur.fetchall()
    conn.close()
    return rows

def update_launched_status(exe_id, launched):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE exe_list SET exe_launched=? WHERE exe_id=?", (launched, exe_id))
    conn.commit()
    conn.close()

def add_or_update_unknown_executable(name, path):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT uex_id FROM unknown_exe WHERE uex_process_name=? AND uex_process_path=?", (name, path))
    row = cur.fetchone()

    now = datetime.datetime.now().isoformat()

    if row:  # déjà connu → mise à jour

        cur.execute("""
            UPDATE unknown_exe
            SET uex_last_seen=?
            WHERE uex_id=?
        """, (now, row[0]))
        uex_id = row[0]
    else:  # nouvel exe → insertion

        print(f"Nouvel exécutable inconnu détecté : {name}")
        cur.execute("""
            INSERT INTO unknown_exe (uex_process_name, uex_process_path, uex_first_seen, uex_last_seen)
            VALUES (?, ?, ?, ?)
        """, (name, path, now, now))
        uex_id = cur.lastrowid

    conn.commit()
    conn.close()
    return uex_id

def get_process_by_name(name,path):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT exe_id FROM exe_list WHERE exe_name=? AND exe_path=?", (name, path))
    row = cur.fetchone()

    conn.close()
    return row[0] if row else None

def add_or_update_executable(name, path):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT exe_id FROM exe_list WHERE exe_name=? AND exe_path=?", (name, path))
    row = cur.fetchone()

    now = datetime.datetime.now().isoformat()

    if row:  # déjà connu → mise à jour

        cur.execute("""
            UPDATE exe_list
            SET exe_last_seen=?, exe_still_installed=1
            WHERE exe_id=?
        """, (now, row[0]))
        exe_id = row[0]
    else:  # nouvel exe → insertion

        print(f"Nouvel exécutable détecté : {name}")
        cur.execute("""
            INSERT INTO exe_list (exe_name, exe_path,exe_program_name, exe_first_seen, exe_last_seen, exe_still_installed, exe_watch)
            VALUES (?, ?, ?, ?, ?, 1, 0)
        """, (name, path, name, now, now))
        exe_id = cur.lastrowid

    conn.commit()
    conn.close()
    return exe_id

def add_event(exe_id, event_type):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""INSERT INTO exe_event (exe_id, eev_type, eev_timestamp) VALUES (?, ?, ?)""", (exe_id, event_type, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

def mark_missing_executables():
    """Met à jour still_present=0 pour les exe plus détectés."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # récupère tous les exe encore marqués comme présents
    cur.execute("SELECT id, path FROM Executables WHERE still_present=1")
    rows = cur.fetchall()

    current_paths = [proc.info['exe'] for proc in psutil.process_iter(['exe']) if proc.info['exe']]

    for exe_id, path in rows:
        if path not in current_paths:
            cur.execute("UPDATE Executables SET still_present=0 WHERE id=?", (exe_id,))
            add_event(exe_id, "STOP")

    conn.commit()
    conn.close()