# Étape 2 : Créer un wrapper pour le service Windows
# Un service Windows nécessite une structure spécifique. Nous allons créer un script Python qui encapsule run.py en tant que service.

# Créez un fichier service_wrapper.py avec le contenu suivant :
import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import os

class MyService(win32serviceutil.ServiceFramework):
    _svc_name_ = "MyPythonService"
    _svc_display_name_ = "My Python Service"
    _svc_description_ = "This service runs the executable generated from run.py."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.running = False

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ""))
        self.main()

    def main(self):
        # Chemin vers l'exécutable généré
        exe_path = os.path.join(os.path.dirname(__file__), "dist", "MyService.exe")
        process = subprocess.Popen([exe_path], shell=False)
        process.wait()

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(MyService)
    
    
# Générez un exécutable pour service_wrapper.py :
# pyinstaller --onefile --hidden-import=win32timezone --name "ServiceInstaller" service_wrapper.py
# Cela génère un exécutable ServiceInstaller.exe dans le dossier dist.

