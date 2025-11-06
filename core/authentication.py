import uuid
from config import get_db_path, get_pc_alias
from dbm import sqlite3

from db import add_or_update_config

#enrollment_code used to register new clients
#status: pending, approved, rejected
#client_id
#token
#private_key
#user_id


def generate_client_id():
    client_id = get_client_id()

    if(not client_id):
        client_id = str(uuid.uuid4())
        set_client_id(client_id)

    return client_id

def get_client_id():
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()

    cur.execute("SELECT cfg_value FROM config WHERE cfg_key=?", ("client_id",))
    row = cur.fetchone()

    conn.close()

    if row:
        return row[0]
    else:
        return None

def set_client_id(client_id):
    add_or_update_config("client_id", client_id)

def register_client():
    client_id = generate_client_id()
    pc_alias = get_pc_alias()

    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()
