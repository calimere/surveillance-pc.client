import win32gui
import win32process
import wmi
import os
import subprocess
import threading
import time
from core.component.logger import get_logger

logger = get_logger("process")

# Singleton WMI connection avec timeout
_wmi_connection = None
_wmi_lock = threading.Lock()


def get_wmi_connection():
    global _wmi_connection
    with _wmi_lock:
        if _wmi_connection is None:
            try:
                _wmi_connection = wmi.WMI()
            except Exception as e:
                logger.error(f"Erreur connexion WMI: {e}")
                _wmi_connection = None
        return _wmi_connection


# 1️⃣ Fenêtres visibles (process principaux)
def get_visible_window_pids():
    pids = set()

    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            pids.add(pid)
        return True

    win32gui.EnumWindows(callback, None)
    return pids


# 2️⃣ PPID + owner via WMI (optimisé)
def get_wmi_process_info():
    c = get_wmi_connection()
    if not c:
        return {}

    info = {}
    try:
        # Récupération en une seule requête avec les propriétés nécessaires uniquement
        for p in c.Win32_Process(["ProcessId", "ParentProcessId", "Name"]):
            pid = int(p.ProcessId)
            ppid = int(p.ParentProcessId) if p.ParentProcessId else 0
            owner = None
            try:
                owner = p.GetOwner()[2]
            except:
                pass
            info[pid] = {"ppid": ppid, "owner": owner}
    except Exception as e:
        logger.warning(f"Erreur WMI get_wmi_process_info: {e}")

    return info


def get_owner_for_pid_fast(pid):
    """🚀 Version rapide avec psutil - 10x plus rapide que WMI"""
    try:
        import psutil

        process = psutil.Process(pid)
        return process.username()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return "system"
    except Exception as e:
        logger.debug(f"Erreur psutil PID {pid}: {e}")
        return "system"


def get_owner_for_pid_win32(pid):
    """🏃‍♂️ Version Win32 API directe - encore plus rapide"""
    try:
        import win32api
        import win32security
        import win32process
        import win32con

        # Ouvrir le processus
        handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, pid)
        if not handle:
            return "system"

        try:
            # Récupérer le token du processus
            token = win32security.OpenProcessToken(handle, win32security.TOKEN_QUERY)

            # Récupérer les infos utilisateur
            user_info = win32security.GetTokenInformation(
                token, win32security.TokenUser
            )
            user_sid = user_info[0]

            # Convertir SID en nom d'utilisateur
            username, domain, account_type = win32security.LookupAccountSid(
                None, user_sid
            )

            win32api.CloseHandle(token)
            win32api.CloseHandle(handle)

            return f"{domain}\\{username}" if domain else username

        except Exception:
            win32api.CloseHandle(handle)
            return "system"

    except Exception as e:
        logger.debug(f"Erreur Win32 PID {pid}: {e}")
        return "system"


# Cache global pour les propriétaires de processus
_owner_cache = {}
_cache_lock = threading.Lock()
_cache_expire_time = 60  # Cache 1 minute


def get_owner_for_pid_cached(pid):
    """🎯 Version avec cache pour éviter les requêtes répétées"""
    now = time.time()

    with _cache_lock:
        # Vérifier le cache
        if pid in _owner_cache:
            cached_time, owner = _owner_cache[pid]
            if now - cached_time < _cache_expire_time:
                return owner

        # Récupérer et mettre en cache
        owner = get_owner_for_pid_fast(pid)
        _owner_cache[pid] = (now, owner)

        # Nettoyage périodique du cache
        if len(_owner_cache) > 500:
            # Supprimer entrées expirées
            expired = [
                k for k, (t, _) in _owner_cache.items() if now - t > _cache_expire_time
            ]
            for k in expired[:100]:  # Limiter le nettoyage
                _owner_cache.pop(k, None)

        return owner


def get_owner_for_pid_with_timeout(pid, timeout=3):
    """🛡️ Version avec timeout - maintenant utilise psutil (rapide)"""
    try:
        # Version rapide - plus besoin de timeout généralement
        return get_owner_for_pid_fast(pid)
    except Exception as e:
        logger.debug(f"Fallback WMI pour PID {pid}: {e}")

        # Fallback WMI uniquement en cas d'échec psutil
        result = {"owner": None, "error": None}

        def worker():
            try:
                c = get_wmi_connection()
                if c:
                    for p in c.Win32_Process(ProcessId=pid):
                        try:
                            result["owner"] = p.GetOwner()[2]
                            break
                        except:
                            pass
            except Exception as e:
                result["error"] = str(e)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            logger.warning(f"Timeout WMI pour PID {pid} après {timeout}s")
            return "system"

        if result["error"]:
            logger.debug(f"Erreur WMI PID {pid}: {result['error']}")
            return "system"

        return result["owner"] or "system"


# 3️⃣ Signataire d'un fichier
def get_file_signer(path):
    """Version originale - peut être lente"""
    if not path or not os.path.exists(path):
        return None

    try:
        ps_command = f'''
        $sig = Get-AuthenticodeSignature "{path}"
        if ($sig.Status -eq 'Valid') {{
            $subject = $sig.SignerCertificate.Subject
            $thumb = $sig.SignerCertificate.Thumbprint
            $ev = ($sig.SignerCertificate.ExtendedKeyUsageList | Where-Object {{ $_.FriendlyName -eq 'Code Signing' }}) -ne $null
            Write-Output "$subject|$thumb|$ev"
        }}
        '''

        # 🔧 Essai avec UTF-8 d'abord (plus courant maintenant)
        try:
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )

            if (
                result.returncode == 0
                and result.stdout.strip()
                and not _is_garbled_text(result.stdout)
            ):
                return _parse_signature_output(result.stdout)

        except Exception:
            pass

        # 🔧 Fallback UTF-16-LE si UTF-8 échoue
        try:
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                encoding="utf-16-le",
                errors="replace",
                timeout=5,
            )

            if (
                result.returncode == 0
                and result.stdout.strip()
                and not _is_garbled_text(result.stdout)
            ):
                return _parse_signature_output(result.stdout)

        except Exception:
            pass

        # 🔧 Fallback avec détection auto d'encodage
        try:
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                timeout=5,
            )

            if result.returncode == 0 and result.stdout:
                # Essayer de détecter l'encodage
                output = _decode_powershell_output(result.stdout)
                if output and not _is_garbled_text(output):
                    return _parse_signature_output(output)

        except Exception:
            pass

    except Exception:
        pass  # Ignore silencieusement les erreurs de signature

    return None


def _is_garbled_text(text):
    """Détecte si le texte est mal encodé"""
    if not text:
        return True

    # Caractères typiques d'un mauvais encodage
    garbled_chars = ["乃", "䴽", "捩", "潲", "潳", "瑦", "圠", "湩", "潤", "獷"]
    return any(char in text for char in garbled_chars)


def _decode_powershell_output(raw_bytes):
    """Essaie plusieurs encodages pour décoder la sortie PowerShell"""
    encodings = ["utf-8", "utf-16-le", "utf-16-be", "cp1252", "latin1"]

    for encoding in encodings:
        try:
            decoded = raw_bytes.decode(encoding, errors="replace")
            if not _is_garbled_text(decoded):
                return decoded
        except Exception:
            continue

    return None


def _parse_signature_output(output):
    """Parse la sortie de la signature"""
    if not output or not output.strip():
        return None

    parts = output.strip().split("|")
    return {
        "subject": parts[0] if len(parts) > 0 else "",
        "thumbprint": parts[1] if len(parts) > 1 else "",
        "is_ev": parts[2].lower() == "true" if len(parts) > 2 else False,
    }


def get_file_signer_simple(path):
    """🎯 Version simple avec encodage forcé"""
    if not path or not os.path.exists(path):
        return None

    try:
        # Force PowerShell à utiliser UTF-8
        ps_command = f'''
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        $sig = Get-AuthenticodeSignature "{path}"
        if ($sig.Status -eq 'Valid') {{
            $subject = $sig.SignerCertificate.Subject
            $thumb = $sig.SignerCertificate.Thumbprint
            $ev = ($sig.SignerCertificate.ExtendedKeyUsageList | Where-Object {{ $_.FriendlyName -eq 'Code Signing' }}) -ne $null
            Write-Output "$subject|$thumb|$ev"
        }}
        '''

        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )

        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split("|")
            return {
                "subject": parts[0] if len(parts) > 0 else "",
                "thumbprint": parts[1] if len(parts) > 1 else "",
                "is_ev": parts[2].lower() == "true" if len(parts) > 2 else False,
            }

    except Exception as e:
        logger.debug(f"Erreur signature {path}: {e}")

    return None


def get_file_signer_with_timeout(path, timeout=3):
    """🛡️ Version avec timeout pour éviter les blocages"""
    if not path or not os.path.exists(path):
        return None

    result = {"signer": None, "error": None}

    def worker():
        try:
            result["signer"] = get_file_signer_simple(path)  # Utilise la version simple
        except Exception as e:
            result["error"] = str(e)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        logger.warning(f"Timeout signature pour {path} après {timeout}s")
        return None

    if result["error"]:
        logger.debug(f"Erreur signature {path}: {result['error']}")
        return None

    return result["signer"]


# 🎯 Détection des chemins suspects
# chemin d'accès "bizarre" : souvent les malwares se cachent dans des dossiers temporaires, de téléchargement ou sur le bureau
def is_weird_path(path: str):

    if not path:
        return False

    p = path.lower()
    keywords = [
        "\\downloads\\",
        "\\desktop\\",
        "\\temp\\",
        "\\tmp\\",
        "\\appdata\\roaming\\",
        "\\appdata\\local\\temp\\",
        "\\users\\public\\",
        "\\programdata\\",
        "\\windows\\temp\\",
        "\\perflogs\\",
        "\\$recycle.bin\\",
        "\\recycler\\",
        "\\system volume information\\",
        "\\inetpub\\",
        "\\music\\",
        "\\videos\\",
        "\\pictures\\",
        "\\documents\\downloads\\",
        "\\onedrive\\",
        "\\dropbox\\",
        "\\google drive\\",
        "\\startup\\",
        "\\start menu\\programs\\startup\\",
    ]
    return any(k in p for k in keywords)
