from urllib import request
import uuid

import requests
from core.component.config import get_api_url, get_db_path, get_pc_alias
import sqlite3

from core.business.db import add_or_update_config
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding


# je récupère le token du client dans la db locale
# si pas de token, j'essaie de m'authentifier auprès de l'api distante
# si l'authentification réussit, je stocke le token dans la db locale
# si l'authentification échoue, je tente d'enregistrer le client dans pending_clients
def init_authentication():
    token = get_client_token()

    if not token:
        token = authenticate_client()
        if token:
            set_client_token(token)
            return token
        else:
            remote_register_client()
            return None
    else:
        return token


def authenticate_client():

    # request api
    post_data = {"client_id": get_client_id()}
    challenge = requests.post(get_api_url() + "/device/challenge", json=post_data)

    if challenge.status_code == 200:
        challenge_data = challenge.json()
        # sign the challenge with the private key
        signature = sign_challenge(challenge_data["challenge"])
        # send the signature to the api
        post_data = {
            "client_id": get_client_id(),
            "signature": signature,
            "challenge_id": challenge_data["challenge_id"],
        }
        response = requests.post(get_api_url() + "/device/authenticate", json=post_data)

        if response.status_code == 200:
            response_data = response.json()
            set_client_token(response_data["token"])
            return response_data["token"]
        else:
            return None
    if challenge.status_code == 404:
        # client not registered, need to register

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        set_private_key(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

        public_key = private_key.public_key()

        register_data = {
            "client_id": get_client_id(),
            "firmware_version": get_firmware_version(),
            "name": get_pc_alias(),
            "os": get_os_info(),
            "os_build": get_os_version(),
            "public_key": public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode(),
        }

        response = requests.post(get_api_url() + "/device/register", json=register_data)
        if response.status_code == 200:
            return authenticate_client()

    return None


def sign_challenge(challenge):
    private_key = get_private_key()
    return private_key.sign(
        challenge.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256(),
    )


def set_private_key(private_key):
    add_or_update_config("private_key", private_key)


def get_private_key():

    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()

    cur.execute("SELECT cfg_value FROM config WHERE cfg_key='private_key'")
    row = cur.fetchone()

    conn.close()

    if row:
        return row[0]
    else:
        return None

    pass


def get_client_token():
    pass


def set_client_token(token):
    add_or_update_config("client_token", token)


# generate a unique client id and store it in the local db
def generate_client_id():
    client_id = get_client_id()

    if not client_id:
        client_id = str(uuid.uuid4())
        set_client_id(client_id)

    return client_id


# get the client id from the local db
def get_client_id():
    conn = sqlite3.connect(get_db_path())
    cur = conn.cursor()

    cur.execute("SELECT cfg_value FROM config WHERE cfg_key='client_id'")
    row = cur.fetchone()

    conn.close()

    if row:
        return row[0]
    else:
        return None


def get_os_info():
    import platform

    return platform.system()


def get_os_version():
    import platform

    return platform.version()


def get_firmware_version():
    return "1.0.0"  # Placeholder for actual firmware version retrieval


# set the client id in the local db
def set_client_id(client_id):
    add_or_update_config("client_id", client_id)


# get the user from local db
def get_user_token():
    # TO-DO: implement api call to get user token
    pass


# authenticate user with remote db
def authenticate_user():
    pass


# enregistrement d'un client sans authentifiier le compte parent
# il faut passer par une table intermédiaire pour stocker les clients en attente d'approbation
# la table s'appellera pending_clients
def remote_register_client():
    pass


# register client in the remote db
def register_client():
    authenticate_user()

    client_id = generate_client_id()
    pc_alias = get_pc_alias()
    user_token = get_user_token()
    os = get_os_info()
    os_version = get_os_version()
    firmware_version = get_firmware_version()

    import requests

    # TO-DO: implement api call to register client
    requests.post(
        get_api_url() + "/register_client",
        json={
            "client_id": client_id,
            "pc_alias": pc_alias,
            "user_token": user_token,
            "os": os,
            "os_version": os_version,
            "firmware_version": firmware_version,
        },
    )
    pass
