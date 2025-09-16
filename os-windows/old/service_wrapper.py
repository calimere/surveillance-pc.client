import configparser
import threading
import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import os
import sys
import time
import traceback

# === Redirection stdout/stderr vers un fichier ===
LOG_PATH = r"C:\temp\surveillance_service.log"
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
sys.stdout = open(LOG_PATH, "a", buffering=1, encoding="utf-8")
sys.stderr = open(LOG_PATH, "a", buffering=1, encoding="utf-8")

print("\n--- Lancement du service_wrapper ---")

config = configparser.ConfigParser()
config.read("config.ini")

class MyService(win32serviceutil.ServiceFramework):

    _svc_name_ = config.get("win-deploy", "service_name", fallback="SurveillancePCService")
    _svc_display_name_ = config.get("win-deploy", "service_display_name", fallback="Surveillance PC Service")
    _svc_description_ = config.get("win-deploy", "service_description", fallback="Service de surveillance PC")

    def __init__(self, args):
        try:
            super().__init__(args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
            self.process = None
            self.running = True
            servicemanager.LogInfoMsg(f"{self._svc_name_}: Initialisation réussie")
            print("10")
            print("Service initialisé correctement")
        except Exception as e:
            msg = f"Erreur __init__ : {e}\n{traceback.format_exc()}"
            servicemanager.LogErrorMsg(msg)
            print("9")
            print(msg)
            raise

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.running = False

        # Arrêter le sous-processus si encore actif
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                servicemanager.LogInfoMsg(f"{self._svc_name_}: Process terminé manuellement")
                print("8")
                print("Sous-processus terminé manuellement")
            except Exception as e:
                msg = f"Erreur arrêt process : {e}"
                servicemanager.LogErrorMsg(msg)
                print("7")
                print(msg)

        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        try:
            servicemanager.LogInfoMsg(f"{self._svc_name_}: Démarrage en cours")
            print("SvcDoRun démarré")
            print("6")
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)

            t = threading.Thread(target=self.main)
            t.start()

            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, "")
            )

            servicemanager.LogInfoMsg(f"{self._svc_name_}: Service marqué comme RUNNING")
            print("5")
            print("Service marqué comme RUNNING")

            win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
        except Exception as e:
            msg = f"Erreur SvcDoRun : {e}\n{traceback.format_exc()}"
            servicemanager.LogErrorMsg(msg)
            print("4")
            print(msg)
            raise

    def main(self):
        exe_path = os.path.join(os.path.dirname(__file__), "dist", "surveillance_pc", "surveillance_pc.exe")
        print(f"Chemin de l'exécutable : {exe_path}")

        while self.running:
            try:
                self.process = subprocess.Popen([exe_path], shell=False)
                servicemanager.LogInfoMsg(f"{self._svc_name_}: Process lancé (pid={self.process.pid})")
                print("3")
                print(f"Process lancé (pid={self.process.pid})")

                # Vérification régulière
                while self.running and self.process.poll() is None:
                    rc = win32event.WaitForSingleObject(self.hWaitStop, 2000)
                    if rc == win32event.WAIT_OBJECT_0:
                        break

            except Exception as e:
                msg = f"Erreur lors du lancement du process : {e}\n{traceback.format_exc()}"
                servicemanager.LogErrorMsg(msg)
                print("1")
                print(msg)

            if self.running:
                servicemanager.LogInfoMsg(f"{self._svc_name_}: redémarrage du process dans 5s")
                print("Redémarrage du process dans 5s...")
                print("2")
                time.sleep(5)


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(MyService)