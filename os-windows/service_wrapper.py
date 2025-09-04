# Étape 2 : Créer un wrapper pour le service Windows
# Un service Windows nécessite une structure spécifique. Nous allons créer un script Python qui encapsule run.py en tant que service.

import configparser
import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import os

config = configparser.ConfigParser()
config.read("config.ini")

class MyService(win32serviceutil.ServiceFramework):
    _svc_name_ = config.get("win-deploy", "service_name", fallback="MyPythonService")
    _svc_display_name_ = config.get("win-deploy", "service_display_name", fallback="My Python Service")
    _svc_description_ = config.get("win-deploy", "service_description", fallback="This service runs the executable generated from run.py.")

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.running = False

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE, servicemanager.PYS_SERVICE_STARTED, (self._svc_name_, ""))
        self.main()

    def main(self):
        # Chemin vers l'exécutable généré
        exe_path = os.path.join(os.path.dirname(__file__), "dist", "surveillance-pc.exe")
        process = subprocess.Popen([exe_path], shell=False)
        process.wait()

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(MyService)