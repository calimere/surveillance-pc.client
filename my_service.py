import win32serviceutil
import win32service
import win32event
import servicemanager
import time

class MyPythonService(win32serviceutil.ServiceFramework):
    _svc_name_ = "MonServicePython"
    _svc_display_name_ = "Service Python Exemple"
    _svc_description_ = "Un service Windows qui exécute un script Python en continu"

    def __init__(self, args):
        super().__init__(args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.running = False

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        self.main()

    def main(self):
        while self.running:
            # Ici tu mets ton code ou tu appelles ton script principal
            with open("C:\\temp\\service_log.txt", "a") as f:
                f.write("Service en cours d'exécution...\n")
            time.sleep(10)

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(MyPythonService)
