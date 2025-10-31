import configparser
import os
import sqlite3
import datetime
from core.config import get_app_data_dir, get_db_path

def init_db():

    print("Initialisation de la base de données...")

    print(f"Vérification de l'existence de la base de données à {get_db_path()}...")

    if os.path.exists(get_db_path()):
        print("Base de données déjà initialisée.")
        return

    print(f"Création de la base de données à {get_db_path()}...")
    os.makedirs(get_app_data_dir(), exist_ok=True)
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS exe_list (
            exe_id INTEGER PRIMARY KEY AUTOINCREMENT,
            exe_name TEXT NOT NULL,
            exe_path TEXT NOT NULL,
            exe_program_name TEXT NOT NULL,
            exe_first_seen TIMESTAMP NOT NULL,
            exe_last_seen TIMESTAMP NOT NULL,
            exe_is_unknown BOOLEAN NOT NULL DEFAULT 0,
            exe_is_watched BOOLEAN NOT NULL DEFAULT 0,
            exe_launched BOOLEAN NOT NULL DEFAULT 0,
            exe_is_dangerous BOOLEAN NOT NULL DEFAULT 0,
            exe_blocked BOOLEAN NOT NULL DEFAULT 0
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS exe_event (
            eev_id INTEGER PRIMARY KEY AUTOINCREMENT,
            exe_id INTEGER NOT NULL,
            eev_type INTEGER NOT NULL,
            eev_timestamp TIMESTAMP NOT NULL,
            FOREIGN KEY(exe_id) REFERENCES exe_list(exe_id)
        )
    """)
   
    conn.commit()
    conn.close()
    print(f"Base de données créée à {get_db_path()}.")

REQUEST = "SELECT exe_name, exe_path, exe_id, exe_launched, exe_is_unknown,exe_is_dangerous, exe_blocked FROM exe_list"

def get_all_exe():
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()
    cur.execute( REQUEST )
    rows = cur.fetchall()
    
    ExeListObj = lambda exe_name, exe_path, exe_id, exe_launched, exe_is_unknown,exe_is_dangerous, exe_blocked: {
        "exe_name": exe_name,
        "exe_path": exe_path,
        "exe_id": exe_id,
        "exe_launched": exe_launched,
        "exe_is_unknown": exe_is_unknown,
        "exe_is_dangerous": exe_is_dangerous,
        "exe_blocked": exe_blocked
    }
    retour = [ExeListObj(*row) for row in rows]

    conn.close()
    return retour

def get_all_events():
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()
    cur.execute("SELECT eev_id,exe_id,eev_type,eev_timestamp FROM exe_event")
    rows = cur.fetchall()

    ExeEvent = lambda eev_id, exe_id, eev_type, eev_timestamp: {
        "eev_id": eev_id,
        "exe_id": exe_id,
        "eev_type": eev_type,
        "eev_timestamp": eev_timestamp
    }
    retour = [ExeEvent(*row) for row in rows]
    
    conn.close()
    return retour

def get_known_watched_processes():
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()
    cur.execute(REQUEST + " WHERE exe_is_watched=1 and exe_is_unknown=0")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_known_blocked_processes():
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()
    cur.execute( REQUEST + " WHERE exe_blocked=1 and exe_is_unknown=0")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_unknown_processes():
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()
    cur.execute( REQUEST + " WHERE exe_is_unknown=1")
    rows = cur.fetchall()
    conn.close()
    return rows

def update_launched_status(exe_id, launched):
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()
    cur.execute("UPDATE exe_list SET exe_launched=? WHERE exe_id=?", (launched, exe_id))
    conn.commit()
    conn.close()

def get_process_by_name(name,path):
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()

    cur.execute("SELECT exe_id FROM exe_list WHERE exe_name=? AND exe_path=?", (name, path))
    row = cur.fetchone()

    conn.close()
    return row[0] if row else None

def add_or_update_unknown_executable(name, path):
    conn = sqlite3.connect(get_db_path())
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

        print(f"Nouvel exécutable inconnu détecté : {name}")
        cur.execute("""INSERT INTO exe_list (exe_name, exe_path, exe_program_name , exe_first_seen , exe_last_seen , exe_is_unknown,exe_is_watched ,exe_launched ,exe_is_dangerous ,exe_blocked ) VALUES (?, ?, ?, ?, ?, 1, 1, 0, 0, 0)""", (name, path, name, now, now))
        exe_id = cur.lastrowid

    conn.commit()
    conn.close()
    return exe_id

def get_exe_by_name_path(name, path):
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()

    cur.execute("SELECT exe_id, exe_name, exe_path, exe_program_name, exe_first_seen, exe_last_seen, exe_is_unknown, exe_is_watched, exe_launched, exe_is_dangerous, exe_blocked FROM exe_list WHERE exe_name=? AND exe_path=?", (name, path))
    row = cur.fetchone()

    conn.close()
    return row

def add_executable(name, path):
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()

    now = datetime.datetime.now().isoformat()

    print(f"Nouvel exécutable détecté : {name}")
    cur.execute("""INSERT INTO exe_list (exe_name, exe_path, exe_program_name , exe_first_seen , exe_last_seen , exe_is_unknown,exe_is_watched ,exe_launched ,exe_is_dangerous ,exe_blocked ) VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, 0)""", (name, path, name, now, now))
    exe_id = cur.lastrowid

    conn.commit()
    conn.close()
    return exe_id
def update_executable(exe_id, name, path):
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()

    now = datetime.datetime.now().isoformat()

    cur.execute("""
        UPDATE exe_list
        SET exe_name=?, exe_path=?, exe_last_seen=?
        WHERE exe_id=?
    """, (name, path, now, exe_id))

    conn.commit()
    conn.close()

def add_or_update_executable(name, path):
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()

    cur.execute("SELECT exe_id FROM exe_list WHERE exe_name=? AND exe_path=?", (name, path))
    row = cur.fetchone()

    now = datetime.datetime.now().isoformat()

    if row:  # déjà connu → mise à jour

        cur.execute("""
            UPDATE exe_list
            SET exe_last_seen=?
            WHERE exe_id=?
        """, (now, row[0]))
        exe_id = row[0]
    else:  # nouvel exe → insertion

        print(f"Nouvel exécutable détecté : {name}")
        cur.execute("""INSERT INTO exe_list (exe_name, exe_path, exe_program_name , exe_first_seen , exe_last_seen , exe_is_unknown,exe_is_watched ,exe_launched ,exe_is_dangerous ,exe_blocked ) VALUES (?, ?, ?, ?, ?, 0, 0, 0, 0, 0)""", (name, path, name, now, now))
        exe_id = cur.lastrowid

    conn.commit()
    conn.close()
    return exe_id

#event_type: 0=STOP, 1=START, 2=KILL
def add_event(exe_id, event_type):
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()
    cur.execute("""INSERT INTO exe_event (exe_id, eev_type, eev_timestamp) VALUES (?, ?, ?)""", (exe_id, event_type, datetime.datetime.now().isoformat()))
    
    cur.execute("SELECT * FROM exe_event WHERE eev_id = ?", (cur.lastrowid,))
    row = cur.fetchone()
    
    conn.commit()
    conn.close()

    return row

def set_executable_blocked(exe_id, blocked):
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()
    cur.execute("UPDATE exe_list SET exe_blocked=? WHERE exe_id=?", (blocked, exe_id))
    conn.commit()
    conn.close()

def set_executable_dangerous(exe_id, dangerous):
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()
    cur.execute("UPDATE exe_list SET exe_is_dangerous=? WHERE exe_id=?", (dangerous, exe_id))
    conn.commit()
    conn.close()

def set_executable_watched(exe_id, watched):
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()
    cur.execute("UPDATE exe_list SET exe_is_watched=? WHERE exe_id=?", (watched, exe_id))
    conn.commit()
    conn.close()
