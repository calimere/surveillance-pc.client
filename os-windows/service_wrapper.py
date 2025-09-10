import configparser
import threading
import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import os
import time

config = configparser.ConfigParser()
config.read("config.ini")

class MyService(win32serviceutil.ServiceFramework):

    _svc_name_ = config.get("win-deploy", "service_name", fallback="SurveillancePCService")
    _svc_display_name_ = config.get("win-deploy", "service_display_name", fallback="Surveillance PC Service")
    _svc_description_ = config.get("win-deploy", "service_description", fallback="Service de surveillance PC")

    def __init__(self, args):
        super().__init__(args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.process = None
        self.running = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.running = False

        # Arrêter le sous-processus si encore actif
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass

        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        t = threading.Thread(target=self.main)
        t.start()

        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, "")
        )

        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)


    def main(self):
        exe_path = os.path.join(os.path.dirname(__file__), "dist", "surveillance_pc", "surveillance_pc.exe")

        while self.running:
            try:
                self.process = subprocess.Popen([exe_path], shell=False)
                servicemanager.LogInfoMsg(f"{self._svc_name_}: Process lancé (pid={self.process.pid})")

                # Vérification régulière
                while self.running and self.process.poll() is None:
                    # Pause de 2 sec max (évite blocage)
                    rc = win32event.WaitForSingleObject(self.hWaitStop, 2000)
                    if rc == win32event.WAIT_OBJECT_0:
                        break

            except Exception as e:
                servicemanager.LogErrorMsg(f"Erreur lors du lancement du process : {e}")

            if self.running:
                servicemanager.LogInfoMsg(f"{self._svc_name_}: redémarrage du process dans 5s")
                time.sleep(5)


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(MyService)
