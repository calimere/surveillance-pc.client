import win32gui
import win32process
import wmi
import os
import subprocess

c = wmi.WMI()


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
    info = {}
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
    return info


def get_owner_for_pid(pid):
    for p in c.Win32_Process(ProcessId=pid):
        try:
            return p.GetOwner()[2]
        except:
            return None


# 3️⃣ Signataire d'un fichier
def get_file_signer(path):
    if not path or not os.path.exists(path):
        return None

    try:
        ps_command = f"""
        $sig = Get-AuthenticodeSignature "{path}"
        if ($sig.Status -eq 'Valid') {{
            $subject = $sig.SignerCertificate.Subject
            $thumb = $sig.SignerCertificate.Thumbprint
            $ev = ($sig.SignerCertificate.ExtendedKeyUsageList | Where-Object {{ $_.FriendlyName -eq 'Code Signing' }}) -ne $null
            Write-Output "$subject|$thumb|$ev"
        }}
        """

        result = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            text=True,
            encoding="utf-16-le",  # ✅ important
            errors="replace",
            timeout=5,
        )

        out = result.stdout.strip()
        if out:
            subject, thumbprint, is_ev = out.split("|")
            return {
                "subject": subject,
                "thumbprint": thumbprint,
                "is_ev": is_ev == "True",
            }

        return None

    except Exception:
        return None


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
